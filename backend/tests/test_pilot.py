"""Pilot mode: consent, cohort code, phases, exam without feedback, anonymous export."""
import csv
import io
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from thinktrace.api import create_app
from thinktrace.bank import BANK
from thinktrace.pilot import CSV_COLUMNS, POST_IDS, PRE_IDS

TOKEN = "test-export-token-123456"
SOLUTIONS = {  # a correct line-by-line solution for each pilot problem
    "A3": ["-2x = -6", "x = 3"], "B4": ["5x + 5 - 7 = 18", "5x = 20", "x = 4"], "C3": ["-2x - 2 = x - 11", "-3x = -9", "x = 3"],
    "A3T": ["-3x = -6", "x = 2"], "B4T": ["3x + 12 - 5 = 16", "3x = 9", "x = 3"], "C3T": ["-3x - 6 = x - 14", "-4x = -8", "x = 2"],
}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PILOT_EXPORT_TOKEN", TOKEN)
    path = str(tmp_path / "t.sqlite3")
    return TestClient(create_app(path, static_dir=str(tmp_path / "none"))), path


def start(c, cohort="class7b", consent=True):
    return c.post("/api/sessions", json={"pilot": cohort, "consent": consent})


def step(c, sid, pid, text, conf="medium"):
    r = c.post(f"/api/sessions/{sid}/problems/{pid}/steps", json={"text": text, "confidence": conf})
    assert r.status_code == 200, r.text
    return r.json()


def nxt(c, sid, post=False):
    return c.post(f"/api/sessions/{sid}/pilot/next", json={"post": post}).json()


def run_exam(c, sid, ids, solve=True):
    for expected in ids:
        n = nxt(c, sid)
        prob = n["problem"]
        assert prob["bank_id"] == expected and prob["kind"] == "exam"
        if solve:
            for line in SOLUTIONS[expected]:
                step(c, sid, prob["id"], line)
        else:
            c.post(f"/api/sessions/{sid}/problems/{prob['id']}/finish")


def full_session(c, cohort="class7b", practice_hints=1, solve_post=True):
    sid = start(c, cohort).json()["session_id"]
    run_exam(c, sid, PRE_IDS, solve=False)                      # pre: submitted, not solved
    assert nxt(c, sid)["phase"] == "practice"
    pid = c.post(f"/api/sessions/{sid}/problems", json={"demo": True}).json()["id"]
    for _ in range(practice_hints):
        c.post(f"/api/sessions/{sid}/problems/{pid}/hint")
    for line in ("2x + 6 = 14", "2x = 8", "x = 4"):
        step(c, sid, pid, line)
    first_post = nxt(c, sid, post=True)
    assert first_post["phase"] == "post"
    for i, expected in enumerate(POST_IDS):
        prob = first_post["problem"] if i == 0 else nxt(c, sid)["problem"]
        assert prob["bank_id"] == expected
        if solve_post:
            for line in SOLUTIONS[expected]:
                step(c, sid, prob["id"], line)
        else:
            c.post(f"/api/sessions/{sid}/problems/{prob['id']}/finish")
    assert nxt(c, sid)["phase"] == "done"
    return sid


# ---------------- consent and cohort code ----------------

def test_consent_blocks_start(env):
    c, path = env
    r = start(c, consent=False)
    assert r.status_code == 400 and r.json() == {"error": "consent_required"}
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    ok = start(c).json()
    assert ok["pilot"] == {"cohort": "class7b", "phase": "pre"} and ok["nickname"] is None
    with sqlite3.connect(path) as db:
        cohort, consent_at = db.execute("SELECT cohort, consent_at FROM sessions").fetchone()
    assert cohort == "class7b" and consent_at > 0


@pytest.mark.parametrize("code", ["A", "class_7-B", "x" * 24, "2026"])
def test_valid_cohort_codes(env, code):
    c, _ = env
    assert start(c, code).json()["pilot"]["cohort"] == code


@pytest.mark.parametrize("code", ["", "x" * 25, "bad code", "a/b", "кириллица", "<script>", "a.b"])
def test_invalid_cohort_code_is_ignored(env, code):
    c, path = env
    r = c.post("/api/sessions", json={"pilot": code, "consent": True})
    assert r.status_code in (400, 422)                                  # normal session: nickname required
    r = c.post("/api/sessions", json={"pilot": code, "consent": True, "nickname": "normal_user"}).json()
    assert "pilot" not in r
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT cohort FROM sessions").fetchone()[0] is None


# ---------------- phases ----------------

def test_phases_are_written_to_the_event_log(env):
    c, path = env
    sid = full_session(c)
    with sqlite3.connect(path) as db:
        rows = db.execute("SELECT type, payload FROM events WHERE session_id = ? ORDER BY id", (sid,)).fetchall()
    events = [(t, json.loads(p)) for t, p in rows]
    started = [p["phase"] for t, p in events if t == "phase_started"]
    assert started == ["pre", "practice", "post"]
    by_phase = {}
    for t, p in events:
        if t in ("problem_started", "step_checked", "hint_shown", "problem_finished"):
            by_phase.setdefault(p["phase"], set()).add(t)
    assert by_phase["pre"] >= {"problem_started", "problem_finished"}
    assert by_phase["practice"] >= {"problem_started", "step_checked", "hint_shown"}
    assert by_phase["post"] >= {"problem_started", "step_checked", "problem_finished"}


def test_practice_only_between_pre_and_post(env):
    c, _ = env
    sid = start(c).json()["session_id"]
    assert c.post(f"/api/sessions/{sid}/problems", json={"demo": True}).status_code == 409   # pre first
    run_exam(c, sid, PRE_IDS, solve=False)
    assert c.post(f"/api/sessions/{sid}/problems", json={"demo": True}).status_code == 200
    nxt(c, sid, post=True)
    assert c.post(f"/api/sessions/{sid}/problems", json={"level": "A"}).status_code == 409   # post started
    assert c.post(f"/api/sessions/{sid}/find-error").status_code == 409


# ---------------- exam: no hints, no feedback ----------------

def test_pre_and_post_have_no_hints_and_no_feedback(env):
    c, _ = env
    sid = start(c).json()["session_id"]
    prob = nxt(c, sid)["problem"]                                   # A3: -2x + 7 = 1
    assert prob["hints_enabled"] is False
    assert c.post(f"/api/sessions/{sid}/problems/{prob['id']}/hint").status_code == 403
    wrong = step(c, sid, prob["id"], "-2x = 1 + 7")                 # SIGN_ON_TRANSFER error
    right = step(c, sid, prob["id"], "x = -4")                      # consistent with the wrong line
    for r in (wrong, right):
        assert set(r) <= {"status", "event_id", "finished", "problem"} and r["status"] == "recorded"
        assert "diagnosis" not in r and "hint" not in r and "explain" not in r
        assert all(s["status"] == "recorded" for s in r["problem"]["steps"])
        assert r["problem"]["solved"] is False
    assert right["finished"] is True                                # a line x = number ends the problem
    assert right["problem"]["current"] == "x = -4"                  # the last line, not the last correct one


def test_exam_counts_each_error_once_and_records_true_result(env):
    c, path = env
    sid = start(c).json()["session_id"]
    prob = nxt(c, sid)["problem"]
    step(c, sid, prob["id"], "-2x = 1 + 7")      # error
    step(c, sid, prob["id"], "-2x = 8")          # follows from the student's previous line
    step(c, sid, prob["id"], "x = -4")
    with sqlite3.connect(path) as db:
        st = [json.loads(p)["status"] for (p,) in db.execute(
            "SELECT payload FROM events WHERE type='step_checked' AND problem_id=?", (prob["id"],))]
        fin = json.loads(db.execute("SELECT payload FROM events WHERE type='problem_finished' AND problem_id=?",
                                    (prob["id"],)).fetchone()[0])
    assert st == ["error", "correct", "correct"] and fin["solved"] is False


def test_free_text_is_off_in_the_pilot(env):
    c, path = env
    sid = run_to_practice(c)
    pid = c.post(f"/api/sessions/{sid}/problems", json={"demo": True}).json()["id"]
    step(c, sid, pid, "2x + 3 = 14")
    eid = step(c, sid, pid, "2x + 6 = 14")["event_id"]
    assert c.post(f"/api/sessions/{sid}/problems/{pid}/explain", json={"step_event_id": eid, "text": "меня зовут Аня"}).status_code == 403
    err = step(c, sid, pid, "2x = 9")["event_id"]
    c.post(f"/api/sessions/{sid}/disagree", json={"event_id": err, "comment": "Аня, 7Б"})
    with sqlite3.connect(path) as db:
        dump = "\n".join(db.iterdump())
    assert "Аня" not in dump


def run_to_practice(c):
    sid = start(c).json()["session_id"]
    run_exam(c, sid, PRE_IDS, solve=False)
    return sid


# ---------------- export and summary ----------------

def get(c, url, token=TOKEN):
    return c.get(url, headers={"X-Export-Token": token} if token else {})


def test_export_access(env, monkeypatch):
    c, _ = env
    full_session(c)
    assert get(c, "/api/pilot/class7b/export.csv", token=None).status_code == 401
    assert get(c, "/api/pilot/class7b/export.csv", token="wrong").status_code == 401
    assert get(c, "/api/pilot/class7b/summary", token=None).status_code == 401
    assert get(c, "/api/pilot/class7b/export.csv").status_code == 200
    monkeypatch.setenv("PILOT_EXPORT_TOKEN", "")
    assert get(c, "/api/pilot/class7b/export.csv").status_code == 404
    assert get(c, "/api/pilot/class7b/summary").status_code == 404


def parse_csv(text):
    first, rest = text.split("\n", 1)
    return first, list(csv.DictReader(io.StringIO(rest)))


def test_csv_content_and_no_identifiers(env):
    c, path = env
    sid = full_session(c)
    text = get(c, "/api/pilot/class7b/export.csv").text
    first, rows = parse_csv(text)
    assert first.startswith("# generated_at=")
    assert list(rows[0].keys()) == CSV_COLUMNS
    assert [r["phase"] for r in rows] == ["pre"] * 3 + ["practice"] + ["post"] * 3
    assert [r["problem_id"] for r in rows] == [*PRE_IDS, "B1", *POST_IDS]
    pre, practice, post = rows[0], rows[3], rows[4]
    assert pre["solved_without_hints"] == "false" and pre["steps"] == "0"
    assert practice["hints_used"] == "1" and practice["solved_without_hints"] == "false"
    assert post["solved_without_hints"] == "true" and post["errors"] == "0"
    assert practice["confidence_vs_correct"] == "medium:3/3"
    # nothing that identifies a person or gives access
    with sqlite3.connect(path) as db:
        nick, = db.execute("SELECT nickname FROM users").fetchone()
        pids = [r[0] for r in db.execute("SELECT id FROM problems")]
    for secret in [sid, nick, *pids, "2x + 6 = 14", "x = 4"]:
        assert secret not in text
    assert all(r["anon_session"].startswith("s_") and r["anon_session"] != sid for r in rows)


def test_error_types_in_export(env):
    c, _ = env
    sid = run_to_practice(c)
    pid = c.post(f"/api/sessions/{sid}/problems", json={"demo": True}).json()["id"]
    step(c, sid, pid, "2x + 3 = 14")
    _, rows = parse_csv(get(c, "/api/pilot/class7b/export.csv").text)
    assert rows[-1]["error_types"] == "DIST_FIRST_ONLY" and rows[-1]["errors"] == "1"


def test_deleted_session_not_in_export_or_summary(env):
    c, _ = env
    from thinktrace.pilot import anon_id
    keep = [full_session(c) for _ in range(5)]
    victim = start(c).json()
    run_exam(c, victim["session_id"], PRE_IDS, solve=False)
    c.delete(f"/api/sessions/{victim['session_id']}", headers={"X-Session-Token": victim["token"]})
    _, rows = parse_csv(get(c, "/api/pilot/class7b/export.csv").text)
    assert {r["anon_session"] for r in rows} == {anon_id(s) for s in keep}
    assert anon_id(victim["session_id"]) not in {r["anon_session"] for r in rows}
    s = get(c, "/api/pilot/class7b/summary").json()
    assert s["N"] == 5 and "solved_without_hints_pre" in s


def test_deleting_a_complete_session_lowers_n_and_hides_averages(env, monkeypatch):
    c, _ = env
    tokens = {}
    real_start = start

    def tracking_start(c_, cohort="class7b", consent=True):
        r = real_start(c_, cohort, consent)
        tokens[r.json()["session_id"]] = r.json()["token"]
        return r

    monkeypatch.setitem(globals(), "start", tracking_start)
    sids = [full_session(c) for _ in range(5)]
    assert get(c, "/api/pilot/class7b/summary").json()["N"] == 5
    c.delete(f"/api/sessions/{sids[0]}", headers={"X-Session-Token": tokens[sids[0]]})
    s = get(c, "/api/pilot/class7b/summary").json()
    assert s["N"] == 4 and set(s) == {"N", "message"}


def test_summary_small_n_hides_averages(env):
    c, _ = env
    for _ in range(4):
        full_session(c)
    s = get(c, "/api/pilot/class7b/summary").json()
    assert set(s) == {"N", "message"} and s["N"] == 4


def test_summary_with_enough_sessions(env):
    c, _ = env
    for _ in range(5):
        full_session(c, practice_hints=2)
    s = get(c, "/api/pilot/class7b/summary").json()
    assert s == {"N": 5, "solved_without_hints_pre": 0.0, "solved_without_hints_post": 1.0, "mean_hints_practice": 2.0}


def test_other_cohort_and_non_pilot_sessions_are_not_exported(env):
    c, _ = env
    full_session(c, cohort="other")
    c.post("/api/sessions", json={"nickname": "regular"})
    _, rows = parse_csv(get(c, "/api/pilot/class7b/export.csv").text)
    assert rows == []
    assert get(c, "/api/pilot/bad code/export.csv").status_code == 404


def test_practice_never_reaches_post_test_problems(env):
    """Pre-test problems are skipped in practice, so their twins (the post-test) cannot
    show up as the 'similar problem' during practice."""
    c, _ = env
    sid = run_to_practice(c)
    for level in ("A", "B", "C"):
        after, seen = None, set()
        for _ in range(5):
            p = c.post(f"/api/sessions/{sid}/problems", json={"level": level, **({"after": after} if after else {})}).json()
            seen.add(p["bank_id"])
            after = p["bank_id"]
        assert not seen & set(PRE_IDS) and not seen & set(POST_IDS)
