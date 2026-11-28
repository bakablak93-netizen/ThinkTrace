"""Pilot mode: cohort link, consent, pre-test -> practice -> post-test, anonymous export.

Link: /?pilot=CODE, CODE must match COHORT_RE, otherwise it is ignored (normal session).
A pilot session stores only: the cohort code, that consent was given and when. No
nickname is asked (an anonymous one is generated), and free-text features are off
("explain in your own words", disagreement comments).

Phases (every event of a problem carries payload.phase via events.log_event):
  pre       PRE_IDS: one bank problem per level A, B, C ("set A"), exam mode
  practice  free work with the tutor (as usual)
  post      the twins of PRE_IDS ("set B", same structure, other numbers), exam mode

Exam mode: no hints, no feedback on correctness. Every step is compared with the
student's PREVIOUS line (not with the last correct one), so one error is counted once.
A problem ends when the student writes a line of the form x = number (right or wrong:
ending reveals nothing) or presses "Submit".

Export (GET /api/pilot/{cohort}/export.csv) and summary: see export_rows / summary.
Deleted sessions are gone from the database (cascade), so they never appear.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone

from .bank import BANK, twin_of
from .diagnose import diagnose
from .events import list_events, log_event
from .expr import eq_text
from .parser import ParseError, parse_equation
from .problems import from_bank
from .verifier import equivalent, is_solved

COHORT_RE = re.compile(r"^[A-Za-z0-9_-]{1,24}$")
PRE_IDS = ("A3", "B4", "C3")                      # set A: one per level (not the default B1)
POST_IDS = tuple(twin_of(i).id for i in PRE_IDS)  # set B: their twins
EXAM_KIND = "exam"
SUMMARY_MIN_N = 5

CSV_COLUMNS = ["anon_session", "cohort", "phase", "problem_id", "steps", "errors", "hints_used",
               "error_types", "solved_without_hints", "time_sec", "confidence_vs_correct"]


class PilotError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


def valid_cohort(code: str | None) -> str | None:
    """The cohort code if it matches COHORT_RE, else None (the code is ignored)."""
    return code if code and COHORT_RE.match(code) else None


def anonymous_nickname() -> str:
    return "pilot-" + secrets.token_hex(6)


def is_pilot(sess: sqlite3.Row) -> bool:
    return bool(sess["cohort"])


# ---------------- phases ----------------

def _exam_problems(conn, sid: str, phase: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM problems WHERE session_id = ? AND kind = ? AND phase = ? ORDER BY created_at",
                        (sid, EXAM_KIND, phase)).fetchall()


def is_finished(conn, sid: str, pid: str) -> bool:
    return _finished(conn, sid, pid)


def _finished(conn, sid: str, pid: str) -> bool:
    return conn.execute("SELECT 1 FROM events WHERE session_id = ? AND problem_id = ? AND type = 'problem_finished'",
                        (sid, pid)).fetchone() is not None


def current_phase(conn, sess: sqlite3.Row) -> str | None:
    """pre -> practice -> post -> done for a pilot session, None otherwise."""
    if not is_pilot(sess):
        return None
    sid = sess["id"]
    pre = _exam_problems(conn, sid, "pre")
    if len(pre) < len(PRE_IDS) or not all(_finished(conn, sid, p["id"]) for p in pre):
        return "pre"
    post = _exam_problems(conn, sid, "post")
    if not post:
        return "practice"
    if len(post) < len(POST_IDS) or not all(_finished(conn, sid, p["id"]) for p in post):
        return "post"
    return "done"


def practice_phase(conn, sess: sqlite3.Row) -> str | None:
    """Phase label for a practice problem; practice is open only between pre and post."""
    if not is_pilot(sess):
        return None
    if current_phase(conn, sess) != "practice":
        raise PilotError("pilot_wrong_phase", 409)
    return "practice"


def next_exam(conn, sess: sqlite3.Row, insert_problem, view, go_post: bool = False) -> dict:
    """Next step of the pilot: the open exam problem, a new one, or the phase."""
    if not is_pilot(sess):
        raise PilotError("not_pilot", 409)
    sid = sess["id"]
    phase = current_phase(conn, sess)
    if phase == "practice" and go_post:
        phase = "post"
        log_event(conn, sid, "phase_started", {"phase": "post"})
    if phase == "practice" and not conn.execute(
            "SELECT 1 FROM events WHERE session_id = ? AND type = 'phase_started' AND payload LIKE '%practice%'",
            (sid,)).fetchone():
        log_event(conn, sid, "phase_started", {"phase": "practice"})
    if phase not in ("pre", "post"):
        return {"phase": phase, "problem": None}
    ids = PRE_IDS if phase == "pre" else POST_IDS
    existing = _exam_problems(conn, sid, phase)
    for row in existing:
        if not _finished(conn, sid, row["id"]):
            return {"phase": phase, "index": existing.index(row) + 1, "total": len(ids), "problem": view(row["id"])}
    if not existing and phase == "pre":
        log_event(conn, sid, "phase_started", {"phase": "pre"})
    bank_id = ids[len(existing)]
    pid = insert_problem(from_bank(BANK[bank_id]), EXAM_KIND, phase)
    return {"phase": phase, "index": len(existing) + 1, "total": len(ids), "problem": view(pid)}


# ---------------- exam steps: no hints, no feedback ----------------

def exam_step(conn, sid: str, pid: str, problem_text: str, text: str, confidence: str) -> dict:
    """Record a step without telling the student whether it is right."""
    if _finished(conn, sid, pid):
        raise PilotError("already_finished", 409)
    try:
        step = parse_equation(text)
    except ParseError as err:
        # a parse error is about the input, not about correctness
        log_event(conn, sid, "parse_error", {"text": text, "code": err.code}, problem_id=pid)
        return {"status": "parse_error", "code": err.code}
    original = parse_equation(problem_text)
    prev = original
    for e in list_events(conn, sid, pid):
        if e["type"] == "step_checked":
            prev = parse_equation(e["payload"]["text"])
    final = is_solved(step)
    if equivalent(prev, step):
        status = "solved" if final and equivalent(original, step) else "correct"
        matches, unknown = [], False
    else:
        status = "error"
        d = diagnose(prev, step)
        matches = [{"bug_id": m.bug_id, "confidence": m.confidence, "level": m.level} for m in d.matches]
        unknown = d.is_unknown
    eid = log_event(conn, sid, "step_checked", {
        "text": eq_text(step), "status": status, "self_confidence": confidence, "corrected": False,
        "matches": matches, "pattern": None, "unknown": unknown, "exam": True,
    }, problem_id=pid)
    if final:
        finish_exam(conn, sid, pid, problem_text)
    # deliberately no status / diagnosis / hint in the response
    return {"status": "recorded", "event_id": eid, "finished": final}


def finish_exam(conn, sid: str, pid: str, problem_text: str) -> None:
    if _finished(conn, sid, pid):
        return
    steps = [e for e in list_events(conn, sid, pid) if e["type"] == "step_checked"]
    solved = bool(steps) and is_solved(parse_equation(steps[-1]["payload"]["text"])) and equivalent(
        parse_equation(problem_text), parse_equation(steps[-1]["payload"]["text"]))
    log_event(conn, sid, "problem_finished", {"solved": solved}, problem_id=pid)
    if solved:
        conn.execute("UPDATE problems SET solved_at = ? WHERE id = ?", (time.time(), pid))
        conn.commit()


# ---------------- export ----------------

def anon_id(sid: str) -> str:
    """Stable pseudonym. The session id itself is an access key to the API: never exported."""
    return "s_" + hashlib.sha256(("thinktrace-pilot:" + sid).encode()).hexdigest()[:12]


def _problem_row(conn, sess, prob) -> dict:
    events = list_events(conn, sess["id"], prob["id"])
    if prob["kind"] == "find_error":
        answers = [e["payload"] for e in events if e["type"] == "find_error_answer"]
        steps = len(answers)
        errors = sum(1 for a in answers if not (a["step_correct"] and a["type_correct"]))
        types: list[str] = []
        conf = ""
    else:
        checked = [e["payload"] for e in events if e["type"] == "step_checked"]
        steps = len(checked)
        errors = sum(1 for s in checked if s["status"] == "error")
        types = sorted({m["bug_id"] for s in checked if s["status"] == "error" for m in s["matches"]}
                       | ({"UNKNOWN"} if any(s["status"] == "error" and s["unknown"] for s in checked) else set()))
        by: dict[str, list[int]] = {}
        for s in checked:
            ok, tot = by.setdefault(s["self_confidence"], [0, 0])
            by[s["self_confidence"]] = [ok + (s["status"] != "error"), tot + 1]
        conf = ";".join(f"{k}:{v[0]}/{v[1]}" for k, v in sorted(by.items()))
    hints = sum(1 for e in events if e["type"] == "hint_shown")
    end = prob["solved_at"] or (events[-1]["ts"] if events else prob["created_at"])
    form = prob["form"]
    problem_id = form[5:] if form.startswith("bank:") else ("find_error" if prob["kind"] == "find_error" else "generated")
    return {
        "anon_session": anon_id(sess["id"]), "cohort": sess["cohort"], "phase": prob["phase"] or "",
        "problem_id": problem_id, "steps": steps, "errors": errors, "hints_used": hints,
        "error_types": ";".join(types), "solved_without_hints": bool(prob["solved_at"]) and hints == 0,
        "time_sec": round(end - prob["created_at"], 1), "confidence_vs_correct": conf,
    }


def export_rows(conn, cohort: str) -> list[dict]:
    """One row per problem of every consented session of the cohort (deleted sessions are
    gone from the database). No nickname, session id, timestamps or free text.

    solved_without_hints = the final answer is correct AND no hint was shown. "Correct"
    means solved_at is set, which happens only when the last line is x = number and SymPy
    confirms it is equivalent to the problem (exam and practice), or, in "find the error",
    when both the step and the error type are right. A finished problem with a wrong answer
    (or "Submit" without an answer) is not solved."""
    rows = []
    for sess in conn.execute("SELECT * FROM sessions WHERE cohort = ? AND consent_at IS NOT NULL ORDER BY created_at",
                             (cohort,)):
        for prob in conn.execute("SELECT * FROM problems WHERE session_id = ? ORDER BY created_at", (sess["id"],)):
            rows.append(_problem_row(conn, sess, prob))
    return rows


def export_csv(conn, cohort: str) -> str:
    buf = io.StringIO()
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    buf.write(f"# generated_at={generated}\n")
    w = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, lineterminator="\n")
    w.writeheader()
    for r in export_rows(conn, cohort):
        w.writerow({**r, "solved_without_hints": str(r["solved_without_hints"]).lower()})
    return buf.getvalue()


def summary(conn, cohort: str) -> dict:
    """N = sessions with at least one finished pre AND one finished post problem.
    Rates: share of pre / post problems solved without hints. Practice: mean hints per
    session. With N < SUMMARY_MIN_N only N and a message (small groups: no averages)."""
    rows = export_rows(conn, cohort)
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["anon_session"], []).append(r)
    complete = {s: rs for s, rs in by.items()
                if any(r["phase"] == "pre" for r in rs) and any(r["phase"] == "post" for r in rs)}
    n = len(complete)
    if n < SUMMARY_MIN_N:
        return {"N": n, "message": f"Fewer than {SUMMARY_MIN_N} complete sessions: averages are not shown."}

    def rate(phase: str) -> float:
        items = [r for rs in complete.values() for r in rs if r["phase"] == phase]
        return round(sum(r["solved_without_hints"] for r in items) / len(items), 3) if items else 0.0

    practice_hints = [sum(r["hints_used"] for r in rs if r["phase"] == "practice") for rs in complete.values()]
    return {
        "N": n,
        "solved_without_hints_pre": rate("pre"),
        "solved_without_hints_post": rate("post"),
        "mean_hints_practice": round(sum(practice_hints) / n, 2),
    }
