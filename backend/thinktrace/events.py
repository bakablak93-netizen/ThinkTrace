"""Event log (Thinking Trace).

Event types and payloads:
  session_started   {mode, lang}
  problem_started   {kind, text}
  step_checked      {text, status: correct|solved|error, self_confidence: low|medium|high,
                     corrected: bool (correct step right after an error),
                     matches: [{bug_id, confidence, level}], pattern, unknown: bool}
  parse_error       {text, code}
  hint_shown        {level, kind: error|stuck, bug_ids, auto: bool,
                     source: llm|template, fallback_reason: str|None}
  explanation       {step_event_id, length, source: llm|template, fallback_reason}
                    (the explanation text itself is not stored)
  find_error_answer {step_index, bug_id, step_correct, type_correct}   (mode "find the error")
  disagree          {event_id, comment}
  session_finished  {}
  phase_started     {phase}                               (pilot)
  problem_finished  {solved: bool}                        (pilot exam problems)
Pilot: every event of a problem with a phase also gets payload.phase (pre|practice|post).
"""
from __future__ import annotations

import json
import sqlite3
import time


def log_event(conn: sqlite3.Connection, session_id: str, type_: str, payload: dict,
              problem_id: str | None = None, ts: float | None = None) -> int:
    if problem_id is not None and "phase" not in payload:
        row = conn.execute("SELECT phase FROM problems WHERE id = ?", (problem_id,)).fetchone()
        if row and row["phase"]:
            payload = {**payload, "phase": row["phase"]}
    cur = conn.execute(
        "INSERT INTO events (session_id, problem_id, ts, type, payload) VALUES (?, ?, ?, ?, ?)",
        (session_id, problem_id, ts if ts is not None else time.time(), type_,
         json.dumps(payload, ensure_ascii=False)),
    )
    conn.commit()
    return cur.lastrowid


def list_events(conn: sqlite3.Connection, session_id: str, problem_id: str | None = None) -> list[dict]:
    sql, args = "SELECT * FROM events WHERE session_id = ?", [session_id]
    if problem_id is not None:
        sql += " AND problem_id = ?"
        args.append(problem_id)
    rows = conn.execute(sql + " ORDER BY id", args).fetchall()
    return [
        {"id": r["id"], "problem_id": r["problem_id"], "ts": r["ts"], "type": r["type"],
         "payload": json.loads(r["payload"])}
        for r in rows
    ]
