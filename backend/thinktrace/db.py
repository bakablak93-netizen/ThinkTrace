"""SQLite storage (stdlib sqlite3).

Privacy: we store only an anonymous nickname. No names, emails, IPs or device data.
Deleting a user cascades to sessions, problems and events.
"""
from __future__ import annotations

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    nickname TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mode TEXT NOT NULL,
    lang TEXT NOT NULL,
    created_at REAL NOT NULL,
    finished_at REAL,
    token_hash TEXT,               -- sha256 of the deletion token; the token itself is not stored
    cohort TEXT,                   -- pilot cohort code (/?pilot=CODE), NULL outside the pilot
    consent_at REAL                -- pilot: when consent was given (nothing else is stored)
);
CREATE TABLE IF NOT EXISTS problems (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,            -- 'main' | 'transfer' | 'find_error' | 'exam' (pilot pre/post)
    text TEXT NOT NULL,
    form TEXT NOT NULL,
    root INTEGER NOT NULL,
    source_bug_id TEXT,            -- for transfer problems
    created_at REAL NOT NULL,
    solved_at REAL,
    data TEXT,                     -- JSON for 'find_error': steps, error index, bug, options
    phase TEXT                     -- pilot: pre | practice | post (NULL outside the pilot)
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    problem_id TEXT REFERENCES problems(id) ON DELETE CASCADE,
    ts REAL NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id, id);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init(path: str) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(sessions)")}
        if "token_hash" not in cols:  # databases created before the delete feature
            conn.execute("ALTER TABLE sessions ADD COLUMN token_hash TEXT")
        for col in ("cohort TEXT", "consent_at REAL"):  # before the pilot mode
            if col.split()[0] not in cols:
                conn.execute(f"ALTER TABLE sessions ADD COLUMN {col}")
        pcols = {r["name"] for r in conn.execute("PRAGMA table_info(problems)")}
        if "data" not in pcols:       # databases created before "find the error"
            conn.execute("ALTER TABLE problems ADD COLUMN data TEXT")
        if "phase" not in pcols:      # before the pilot mode
            conn.execute("ALTER TABLE problems ADD COLUMN phase TEXT")
