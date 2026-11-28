"""Session report built only from the event log.

Contents: steps, errors, hints, corrections, transfer result, timeline, Independence Index.
The report never draws conclusions about a person's abilities; it describes the process.

Independence Index (0..100), computed only from the event log of this session:

    A (hints)    = max(0, 1 - H / 4)
                   H = hints the student REQUESTED on main problems. Automatic hints after an
                   error (smart_tutor) are not counted: the error itself is already in B.
    B (attempts) = correct steps / all checked steps on main problems
                   (input that could not be parsed is not a step and is not counted)
    C (transfer) = 1 if the transfer problem was solved without wrong steps,
                   0.5 if solved with wrong steps, 0 if started but not solved

    I = 100 * (0.4*A + 0.3*B + 0.3*C)
    If no transfer problem was started, C is left out and the weights are renormalised:
    I = 100 * (0.4*A + 0.3*B) / 0.7, and the index is marked partial.
    No main problem attempted -> no index.

Not included: "find the error" and "explain in your own words" (feedback only).
The index describes how independently THIS session went; it is not a grade.
"""
from __future__ import annotations

import sqlite3
from collections import Counter

from .bugs.catalog import CATALOG
from .events import list_events
from .i18n import pick, tr
from .tutor import get_session


def _bug_name(bug_id: str, lang: str) -> str:
    return pick(CATALOG[bug_id].name, lang) if bug_id in CATALOG else tr("report.unknown_error", lang)


def build_report(conn: sqlite3.Connection, sid: str, lang: str = "ru") -> dict:
    sess = get_session(conn, sid)
    events = list_events(conn, sid)
    t0 = sess["created_at"]
    problems = {
        r["id"]: {
            "id": r["id"], "kind": r["kind"], "text": r["text"], "solved": r["solved_at"] is not None,
            "source_bug_id": r["source_bug_id"],
            "duration_sec": round((r["solved_at"] or (events[-1]["ts"] if events else r["created_at"]))
                                  - r["created_at"], 1),
            "steps": [], "hints": [], "errors_by_bug": {}, "answers": [],
            "phase": r["phase"],   # pilot: pre | practice | post (None outside the pilot)
        }
        for r in conn.execute("SELECT * FROM problems WHERE session_id = ? ORDER BY created_at", (sid,))
    }
    disagreed = {e["payload"]["event_id"] for e in events if e["type"] == "disagree"}
    timeline = []
    for e in events:
        t = round(e["ts"] - t0, 1)
        p = problems.get(e["problem_id"])
        pl = e["payload"]
        item = {"t": t, "type": e["type"], "problem_kind": p["kind"] if p else None}
        if e["type"] == "step_checked":
            bugs = [{"bug_id": m["bug_id"], "name": _bug_name(m["bug_id"], lang),
                     "confidence": m["confidence"], "level": m["level"]} for m in pl["matches"]]
            p["steps"].append({
                "event_id": e["id"], "t": t, "text": pl["text"], "status": pl["status"],
                "self_confidence": pl["self_confidence"], "corrected": pl["corrected"],
                "bugs": bugs, "unknown": pl["unknown"], "pattern": pl["pattern"],
                "disagreed": e["id"] in disagreed,
            })
            item.update(text=pl["text"], status=pl["status"])
        elif e["type"] == "hint_shown":
            source = pl.get("source", "template")
            p["hints"].append({"t": t, "level": pl["level"], "kind": pl["kind"], "auto": pl["auto"],
                               "source": source})
            item.update(level=pl["level"], auto=pl["auto"], source=source)
        elif e["type"] == "find_error_answer":
            p["answers"].append({"t": t, **pl})
            item.update(step_correct=pl["step_correct"], type_correct=pl["type_correct"])
        elif e["type"] == "parse_error":
            item.update(text=pl["text"])
        timeline.append(item)

    for p in problems.values():
        c = Counter()
        for s in p["steps"]:
            if s["status"] == "error":
                if s["unknown"]:
                    c[tr("report.unknown_error", lang)] += 1
                for b in s["bugs"]:
                    c[b["name"]] += 1
        p["errors_by_bug"] = dict(c)

    main = [p for p in problems.values() if p["kind"] == "main"]
    transfer = [p for p in problems.values() if p["kind"] == "transfer"]
    all_steps = [s for p in problems.values() for s in p["steps"]]
    totals = {
        "steps": len(all_steps),
        "errors": sum(s["status"] == "error" for s in all_steps),
        "hints": sum(len(p["hints"]) for p in problems.values()),
        "corrections": sum(s["corrected"] for s in all_steps),
        "disagreements": len(disagreed),
    }

    if not transfer:
        tstatus, ttext = "none", tr("report.transfer.none", lang)
    else:
        tp = transfer[-1]
        errs = [s for s in tp["steps"] if s["status"] == "error"]
        repeated = tp["source_bug_id"] and any(
            b["bug_id"] == tp["source_bug_id"] for s in errs for b in s["bugs"])
        if repeated:
            tstatus, ttext = "repeat", tr("report.transfer.repeat", lang, name=_bug_name(tp["source_bug_id"], lang))
        elif not tp["solved"]:
            tstatus, ttext = "unsolved", tr("report.transfer.unsolved", lang)
        elif errs:
            tstatus, ttext = "errors", tr("report.transfer.errors", lang, errors=len(errs))
        else:
            tstatus, ttext = "ok", tr("report.transfer.ok", lang)

    index = independence_index(main, transfer[-1] if transfer else None)

    summary = tr("report.summary", lang, solved=sum(p["solved"] for p in main), total=len(main),
                 errors=sum(s["status"] == "error" for p in main for s in p["steps"]),
                 hints=sum(len(p["hints"]) for p in main))
    return {
        "session": {"mode": sess["mode"], "lang": sess["lang"], "finished": sess["finished_at"] is not None},
        "note": tr("report.note", lang),
        "summary": summary,
        "totals": totals,
        "problems": list(problems.values()),
        "transfer": {"status": tstatus, "text": ttext},
        "independence": index,
        "timeline": timeline,
    }


W_HINTS, W_ATTEMPTS, W_TRANSFER = 0.4, 0.3, 0.3
HINTS_TO_ZERO = 4


def independence_index(main: list[dict], transfer: dict | None) -> dict | None:
    """See the module docstring for the formula."""
    steps = [s for p in main for s in p["steps"]]
    if not steps:
        return None
    requested = sum(1 for p in main for h in p["hints"] if not h["auto"])
    a = max(0.0, 1 - requested / HINTS_TO_ZERO)
    b = sum(s["status"] != "error" for s in steps) / len(steps)
    if transfer is None:
        c, partial = None, True
        value = 100 * (W_HINTS * a + W_ATTEMPTS * b) / (W_HINTS + W_ATTEMPTS)
    else:
        errors = any(s["status"] == "error" for s in transfer["steps"])
        c = 0.0 if not transfer["solved"] else (0.5 if errors else 1.0)
        partial = False
        value = 100 * (W_HINTS * a + W_ATTEMPTS * b + W_TRANSFER * c)
    return {
        "value": round(value), "partial": partial,
        "hints_requested": requested, "hints_component": round(a, 2),
        "steps_correct": sum(s["status"] != "error" for s in steps), "steps_total": len(steps),
        "attempts_component": round(b, 2),
        "transfer_component": None if c is None else round(c, 2),
    }
