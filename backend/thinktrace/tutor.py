"""Session logic between the HTTP layer and the deterministic core.

State is reconstructed from the event log, so the log is the single source of truth:
  * the chain of accepted steps (a wrong step never becomes "previous");
  * the current episode = events after the last accepted step;
  * hint levels already shown in the episode.

Modes: stage 1 implements smart_tutor (after a wrong step the system itself shows the
level-1 question). Stage 2: independent (verdict only, hints on request) and exam.
Transfer problems: no hints and no diagnosis shown to the student; analysis in the report.

LLM (llm.py) only re-words error hints of levels 1-3: a known single bug ("hint") or an
error outside the catalog ("unknown_error"). Ambiguous diagnoses, level 4 and "stuck" hints
stay deterministic templates. Every hint event records its source: llm | template.
"""
from __future__ import annotations

import random
import re
import sqlite3
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field

from .bugs.catalog import CATALOG
from .diagnose import Diagnosis, diagnose
from .events import list_events, log_event
from .expr import Equation, eq_latex, eq_text
from .hints import Hint, error_hint, next_level, stuck_hint
from .llm import HintRequest, HintResult, LLMClient, TemplateClient
from .i18n import LANGS, pick, tr
from .parser import ParseError, parse_equation
from .problems import Problem, demo_problem, main_problem, transfer_problem
from .verifier import equivalent, is_solved, unique_root

MODES = ("smart_tutor",)
CONFIDENCE = ("low", "medium", "high")
AUTO_MAX_LEVEL = 3
NICK_RE = re.compile(r"^[\w\-]{2,24}$")


class TutorError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


# ---------------- sessions ----------------

def create_session(conn: sqlite3.Connection, nickname: str, lang: str = "ru",
                   mode: str = "smart_tutor") -> dict:
    nickname = (nickname or "").strip()
    if not NICK_RE.match(nickname):
        raise TutorError("bad_nickname")
    if lang not in LANGS:
        raise TutorError("bad_lang")
    if mode not in MODES:
        raise TutorError("bad_mode")
    now = time.time()
    row = conn.execute("SELECT id FROM users WHERE nickname = ?", (nickname,)).fetchone()
    user_id = row["id"] if row else uuid.uuid4().hex
    if not row:
        conn.execute("INSERT INTO users (id, nickname, created_at) VALUES (?, ?, ?)", (user_id, nickname, now))
    sid = uuid.uuid4().hex
    conn.execute("INSERT INTO sessions (id, user_id, mode, lang, created_at) VALUES (?, ?, ?, ?, ?)",
                 (sid, user_id, mode, lang, now))
    conn.commit()
    log_event(conn, sid, "session_started", {"mode": mode, "lang": lang})
    return {"session_id": sid, "nickname": nickname, "mode": mode, "lang": lang}


def get_session(conn: sqlite3.Connection, sid: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
    if not row:
        raise TutorError("session_not_found", 404)
    return row


def finish(conn: sqlite3.Connection, sid: str) -> None:
    get_session(conn, sid)
    conn.execute("UPDATE sessions SET finished_at = ? WHERE id = ? AND finished_at IS NULL", (time.time(), sid))
    conn.commit()
    log_event(conn, sid, "session_finished", {})


# ---------------- problems ----------------

def _insert_problem(conn, sid: str, p: Problem, kind: str, source_bug_id: str | None) -> str:
    pid = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO problems (id, session_id, kind, text, form, root, source_bug_id, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (pid, sid, kind, p.text, p.form, p.root, source_bug_id, time.time()),
    )
    conn.commit()
    log_event(conn, sid, "problem_started", {"kind": kind, "text": p.text}, problem_id=pid)
    return pid


def _get_problem(conn, sid: str, pid: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM problems WHERE id = ? AND session_id = ?", (pid, sid)).fetchone()
    if not row:
        raise TutorError("problem_not_found", 404)
    return row


def new_problem(conn, sid: str, demo: bool = False, seed: int | None = None) -> dict:
    get_session(conn, sid)
    p = demo_problem() if demo else main_problem(random.Random(seed))
    pid = _insert_problem(conn, sid, p, "main", None)
    return problem_view(conn, sid, pid)


def session_error_bugs(conn, sid: str, kind: str | None = "main") -> list[str]:
    """Bug ids diagnosed in this session (one per wrong step; ambiguous steps excluded)."""
    kinds = {r["id"]: r["kind"] for r in conn.execute("SELECT id, kind FROM problems WHERE session_id = ?", (sid,))}
    out = []
    for e in list_events(conn, sid):
        if e["type"] == "step_checked" and e["payload"]["status"] == "error":
            if kind and kinds.get(e["problem_id"]) != kind:
                continue
            m = e["payload"]["matches"]
            if len(m) == 1:
                out.append(m[0]["bug_id"])
    return out


def new_transfer(conn, sid: str, seed: int | None = None) -> dict:
    get_session(conn, sid)
    solved = conn.execute(
        "SELECT * FROM problems WHERE session_id = ? AND kind = 'main' AND solved_at IS NOT NULL"
        " ORDER BY solved_at DESC LIMIT 1", (sid,)).fetchone()
    if not solved:
        raise TutorError("no_solved_problem", 409)
    bugs = session_error_bugs(conn, sid)
    # most frequent bug; ties -> the most recent one
    bug_id = None
    if bugs:
        counts = Counter(bugs)
        top = max(counts.values())
        bug_id = next(b for b in reversed(bugs) if counts[b] == top)
    original = Problem(solved["text"], solved["form"], solved["root"])
    p = transfer_problem(bug_id, original, random.Random(seed))
    pid = _insert_problem(conn, sid, p, "transfer", bug_id)
    return problem_view(conn, sid, pid)


# ---------------- state ----------------

@dataclass
class State:
    problem: sqlite3.Row
    original: Equation
    current: Equation
    accepted: list[dict] = field(default_factory=list)   # step_checked events correct/solved
    episode: list[dict] = field(default_factory=list)    # events after last accepted step
    all_steps: list[dict] = field(default_factory=list)

    @property
    def solved(self) -> bool:
        return self.problem["solved_at"] is not None

    @property
    def wrong_attempts(self) -> int:
        return sum(1 for e in self.episode if e["type"] == "step_checked")

    @property
    def last_error(self) -> dict | None:
        errs = [e for e in self.episode if e["type"] == "step_checked"]
        return errs[-1] if errs else None


def load_state(conn, sid: str, pid: str) -> State:
    prob = _get_problem(conn, sid, pid)
    original = parse_equation(prob["text"])
    st = State(prob, original, original)
    for e in list_events(conn, sid, pid):
        if e["type"] == "step_checked":
            st.all_steps.append(e)
            if e["payload"]["status"] in ("correct", "solved"):
                st.accepted.append(e)
                st.current = parse_equation(e["payload"]["text"])
                st.episode = []
                continue
        if e["type"] in ("step_checked", "hint_shown"):
            st.episode.append(e)
    return st


def problem_view(conn, sid: str, pid: str) -> dict:
    st = load_state(conn, sid, pid)
    p = st.problem
    steps = []
    for e in st.all_steps:
        eq = parse_equation(e["payload"]["text"])
        steps.append({"event_id": e["id"], "text": eq_text(eq), "latex": eq_latex(eq),
                      "status": e["payload"]["status"]})
    return {
        "id": p["id"], "kind": p["kind"], "text": eq_text(st.original), "latex": eq_latex(st.original),
        "current": eq_text(st.current), "solved": st.solved, "hints_enabled": p["kind"] == "main",
        "steps": steps,
    }


# ---------------- steps ----------------

def _diag_payload(d: Diagnosis, lang: str) -> dict:
    return {
        "unknown": d.is_unknown,
        "ambiguous": d.is_ambiguous,
        "pattern": d.pattern,
        "candidates": [
            {"bug_id": m.bug_id, "name": pick(CATALOG[m.bug_id].name, lang),
             "confidence": m.confidence, "level": m.level}
            for m in d.matches
        ],
    }


def submit_step(conn, sid: str, pid: str, text: str, self_confidence: str, lang: str = "ru",
                llm: LLMClient | None = None) -> dict:
    sess = get_session(conn, sid)
    if self_confidence not in CONFIDENCE:
        raise TutorError("bad_confidence")
    st = load_state(conn, sid, pid)
    if st.solved:
        raise TutorError("already_solved", 409)
    try:
        step = parse_equation(text)
    except ParseError as err:
        log_event(conn, sid, "parse_error", {"text": text, "code": err.code}, problem_id=pid)
        return {"status": "parse_error", "code": err.code, "message": tr(f"parse.{err.code}", lang, **err.params)}

    base = {"text": eq_text(step), "self_confidence": self_confidence}
    if equivalent(st.current, step):
        solved = is_solved(step)
        status = "solved" if solved else "correct"
        eid = log_event(conn, sid, "step_checked",
                        {**base, "status": status, "corrected": st.wrong_attempts > 0,
                         "matches": [], "pattern": None, "unknown": False}, problem_id=pid)
        if solved:
            conn.execute("UPDATE problems SET solved_at = ? WHERE id = ?", (time.time(), pid))
            conn.commit()
        return {"status": status, "event_id": eid, "problem": problem_view(conn, sid, pid)}

    history = session_error_bugs(conn, sid, kind=None)
    d = diagnose(st.current, step, history)
    eid = log_event(conn, sid, "step_checked", {
        **base, "status": "error", "corrected": False,
        "matches": [{"bug_id": m.bug_id, "confidence": m.confidence, "level": m.level} for m in d.matches],
        "pattern": d.pattern, "unknown": d.is_unknown,
    }, problem_id=pid)
    resp = {"status": "error", "event_id": eid}
    if st.problem["kind"] == "main":
        resp["diagnosis"] = _diag_payload(d, lang)
        if sess["mode"] == "smart_tutor":
            # automatic hint climbs the ladder for a repeated error, but never above
            # AUTO_MAX_LEVEL: the detailed walkthrough (4) is shown only on request
            level = min(next_level(_levels(st.episode, "error", d.bug_ids), st.wrong_attempts + 1),
                        AUTO_MAX_LEVEL)
            h = error_hint(d, level, st.current, eq_text(step), lang)
            res = _phrase(llm, st, d, h, eq_text(step), lang)
            log_event(conn, sid, "hint_shown",
                      {"level": h.level, "kind": "error", "bug_ids": d.bug_ids, "auto": True,
                       "source": res.source, "fallback_reason": res.fallback_reason}, problem_id=pid)
            resp["hint"] = {"level": h.level, "text": res.text, "source": res.source}
    resp["problem"] = problem_view(conn, sid, pid)
    return resp


# ---------------- hints ----------------

def _levels(episode: list[dict], kind: str, bug_ids: list[str] | None = None) -> list[int]:
    """Hint levels already shown in the episode for this kind (and the same bug set)."""
    return [e["payload"]["level"] for e in episode
            if e["type"] == "hint_shown" and e["payload"]["kind"] == kind
            and (bug_ids is None or e["payload"]["bug_ids"] == bug_ids)]


def _phrase(llm: LLMClient | None, st: State, d: Diagnosis | None, h: Hint, step_text: str,
            lang: str) -> HintResult:
    """Ask the LLM to word an error hint of level 1-3; template for everything else.
    Only problem text, the student's lines, level, language and the error id/description
    are passed on -- never nickname or session id."""
    if d is None or h.level > 3 or d.is_ambiguous:
        return HintResult(h.text, "template", "not_applicable")
    error = None
    if d.matches:
        bug = CATALOG[d.matches[0].bug_id]
        error = {"id": bug.id, "name": pick(bug.name, lang), "description": pick(bug.description, lang)}
    req = HintRequest(
        task="hint" if error else "unknown_error",
        language=lang,
        level=h.level,
        problem=eq_text(st.original),
        accepted_steps=[e["payload"]["text"] for e in st.accepted],
        previous_step=eq_text(st.current),
        student_step=step_text,
        template_hint=h.text,
        error=error,
        root=unique_root(st.original),
    )
    return (llm or TemplateClient()).write_hint(req)


def request_hint(conn, sid: str, pid: str, lang: str = "ru", llm: LLMClient | None = None) -> dict:
    get_session(conn, sid)
    st = load_state(conn, sid, pid)
    if st.problem["kind"] != "main":
        raise TutorError("hints_disabled", 403)
    if st.solved:
        raise TutorError("already_solved", 409)

    err = st.last_error
    if err is None:
        levels = _levels(st.episode, "stuck")
        level = next_level(levels, 0)
        h = stuck_hint(st.current, level, lang)
        bug_ids: list[str] = []
        d, step_text = None, ""
    else:
        step = parse_equation(err["payload"]["text"])
        d = diagnose(st.current, step)  # deterministic: same result as when the step was checked
        bug_ids = d.bug_ids
        levels = _levels(st.episode, "error", bug_ids)
        level = next_level(levels, st.wrong_attempts)
        step_text = eq_text(step)
        h = error_hint(d, level, st.current, step_text, lang)
    res = _phrase(llm, st, d, h, step_text, lang)
    log_event(conn, sid, "hint_shown",
              {"level": h.level, "kind": h.kind, "bug_ids": bug_ids, "auto": False,
               "source": res.source, "fallback_reason": res.fallback_reason}, problem_id=pid)
    return {"level": h.level, "text": res.text, "kind": h.kind, "source": res.source}


def disagree(conn, sid: str, event_id: int, comment: str = "") -> None:
    get_session(conn, sid)
    row = conn.execute("SELECT problem_id FROM events WHERE id = ? AND session_id = ? AND type = 'step_checked'",
                       (event_id, sid)).fetchone()
    if not row:
        raise TutorError("event_not_found", 404)
    log_event(conn, sid, "disagree", {"event_id": event_id, "comment": (comment or "")[:500]},
              problem_id=row["problem_id"])
