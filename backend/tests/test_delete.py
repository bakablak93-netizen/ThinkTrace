"""Delete my data: only with the session's own token."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from thinktrace.api import create_app


@pytest.fixture
def env(tmp_path):
    path = str(tmp_path / "t.sqlite3")
    return TestClient(create_app(path, static_dir=str(tmp_path / "none"))), path


def start(c, nick):
    r = c.post("/api/sessions", json={"nickname": nick}).json()
    pid = c.post(f"/api/sessions/{r['session_id']}/problems", json={"demo": True}).json()["id"]
    c.post(f"/api/sessions/{r['session_id']}/problems/{pid}/steps", json={"text": "2x+3=14", "confidence": "low"})
    return r["session_id"], r["token"]


def count(path, sql, *args):
    with sqlite3.connect(path) as db:
        return db.execute(sql, args).fetchone()[0]


def test_delete_with_own_token_removes_everything(env):
    c, path = env
    sid, token = start(c, "alice")
    assert count(path, "SELECT COUNT(*) FROM events WHERE session_id = ?", sid) > 0
    r = c.delete(f"/api/sessions/{sid}", headers={"X-Session-Token": token})
    assert r.status_code == 200
    assert c.get(f"/api/sessions/{sid}/report").status_code == 404
    for table in ("events", "problems"):
        assert count(path, f"SELECT COUNT(*) FROM {table} WHERE session_id = ?", sid) == 0
    assert count(path, "SELECT COUNT(*) FROM users WHERE nickname = 'alice'") == 0


def test_cannot_delete_someone_elses_session(env):
    c, path = env
    victim, _ = start(c, "victim")
    _, attacker_token = start(c, "attacker")
    for headers in ({"X-Session-Token": attacker_token}, {"X-Session-Token": "guess"}, {}):
        r = c.delete(f"/api/sessions/{victim}", headers=headers)
        assert r.status_code == 403 and r.json() == {"error": "forbidden"}
    assert c.get(f"/api/sessions/{victim}/report").status_code == 200


def test_other_sessions_with_same_nickname_are_kept(env):
    c, path = env
    s1, t1 = start(c, "shared_nick")
    s2, _ = start(c, "shared_nick")
    assert c.delete(f"/api/sessions/{s1}", headers={"X-Session-Token": t1}).status_code == 200
    assert c.get(f"/api/sessions/{s2}/report").status_code == 200
    assert count(path, "SELECT COUNT(*) FROM users WHERE nickname = 'shared_nick'") == 1


def test_token_is_not_stored_in_plain_text(env):
    c, path = env
    sid, token = start(c, "bob")
    with sqlite3.connect(path) as db:
        dump = "\n".join(db.iterdump())
    assert token not in dump


def test_unknown_session(env):
    c, _ = env
    assert c.delete("/api/sessions/nope", headers={"X-Session-Token": "x"}).status_code == 404


def test_old_database_gets_token_column(tmp_path):
    path = str(tmp_path / "old.sqlite3")
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, user_id TEXT, mode TEXT, lang TEXT,"
                   " created_at REAL, finished_at REAL)")
    TestClient(create_app(path, static_dir=str(tmp_path / "none")))
    with sqlite3.connect(path) as db:
        assert "token_hash" in [r[1] for r in db.execute("PRAGMA table_info(sessions)")]
