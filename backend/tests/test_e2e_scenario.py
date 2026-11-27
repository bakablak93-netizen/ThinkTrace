"""Stage 1 end-to-end scenario through the HTTP API:
2(x+3)=14 -> wrong step 2x+3=14 -> DIST_FIRST_ONLY + guiding question -> correction ->
solution -> report -> transfer problem (no hints)."""
import pytest
from fastapi.testclient import TestClient

from thinktrace.api import create_app


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(str(tmp_path / "t.sqlite3")))


def step(client, sid, pid, text, conf="medium"):
    r = client.post(f"/api/sessions/{sid}/problems/{pid}/steps", json={"text": text, "confidence": conf})
    assert r.status_code == 200, r.text
    return r.json()


def test_demo_scenario(client):
    sid = client.post("/api/sessions", json={"nickname": "student_1"}).json()["session_id"]
    prob = client.post(f"/api/sessions/{sid}/problems", json={"demo": True}).json()
    pid = prob["id"]
    assert prob["text"] == "2(x + 3) = 14"

    # wrong step -> diagnosis + automatic guiding question (smart_tutor)
    r = step(client, sid, pid, "2x+3=14", "high")
    assert r["status"] == "error"
    assert [c["bug_id"] for c in r["diagnosis"]["candidates"]] == ["DIST_FIRST_ONLY"]
    assert r["diagnosis"]["pattern"] == "first"
    assert r["hint"]["level"] == 1
    assert "4" not in r["hint"]["text"]  # the root (x = 4) is not revealed

    # next hint request goes up the ladder
    h = client.post(f"/api/sessions/{sid}/problems/{pid}/hint").json()
    assert h["level"] == 2 and "2(x + 3) = 14" in h["text"]

    # correction and solution; a wrong step never becomes the "previous" step
    assert step(client, sid, pid, "2x+6=14")["status"] == "correct"
    assert step(client, sid, pid, "2x=8")["status"] == "correct"
    r = step(client, sid, pid, "x=4", "high")
    assert r["status"] == "solved" and r["problem"]["solved"]

    # transfer problem: same rule (brackets), other form/numbers, hints disabled
    t = client.post(f"/api/sessions/{sid}/transfer").json()
    assert t["kind"] == "transfer" and not t["hints_enabled"]
    assert "(" in t["text"] and t["text"] != prob["text"]
    assert client.post(f"/api/sessions/{sid}/problems/{t['id']}/hint").status_code == 403

    client.post(f"/api/sessions/{sid}/finish")
    rep = client.get(f"/api/sessions/{sid}/report").json()
    main = rep["problems"][0]
    assert main["solved"]
    assert [s["status"] for s in main["steps"]] == ["error", "correct", "correct", "solved"]
    assert main["steps"][1]["corrected"] is True
    assert main["errors_by_bug"] == {"Скобки раскрыты не полностью": 1}
    assert [h["level"] for h in main["hints"]] == [1, 2]
    assert rep["totals"]["errors"] == 1
    assert rep["transfer"]["status"] == "unsolved"
    assert rep["note"]
    assert any(e["type"] == "hint_shown" for e in rep["timeline"])


def test_transfer_problem_hides_diagnosis_and_detects_repeat(client):
    sid = client.post("/api/sessions", json={"nickname": "student_2"}).json()["session_id"]
    pid = client.post(f"/api/sessions/{sid}/problems", json={"demo": True}).json()["id"]
    step(client, sid, pid, "2x+3=14")
    for s in ("2x+6=14", "2x=8", "x=4"):
        step(client, sid, pid, s)
    t = client.post(f"/api/sessions/{sid}/transfer").json()

    # find the bracket in the transfer problem and make the same error there
    from thinktrace.bugs.catalog import CATALOG
    from thinktrace.expr import eq_text
    from thinktrace.parser import parse_equation
    from thinktrace.verifier import equivalent
    eq = parse_equation(t["text"])
    cand = next(c for c in CATALOG["DIST_FIRST_ONLY"].transforms(eq) if not equivalent(eq, c.buggy))
    r = step(client, sid, t["id"], eq_text(cand.buggy))
    assert r["status"] == "error"
    assert "diagnosis" not in r and "hint" not in r   # analysis only in the report

    rep = client.get(f"/api/sessions/{sid}/report").json()
    assert rep["transfer"]["status"] == "repeat"
    tr_steps = rep["problems"][1]["steps"]
    assert tr_steps[0]["bugs"][0]["bug_id"] == "DIST_FIRST_ONLY"
    assert tr_steps[0]["pattern"] == "repeated"


def test_parse_error_and_disagree(client):
    sid = client.post("/api/sessions", json={"nickname": "student_3"}).json()["session_id"]
    pid = client.post(f"/api/sessions/{sid}/problems", json={"demo": True}).json()["id"]
    r = step(client, sid, pid, "2y=4")
    assert r["status"] == "parse_error" and "y" in r["message"]
    r = step(client, sid, pid, "2x+3=14")
    ok = client.post(f"/api/sessions/{sid}/disagree", json={"event_id": r["event_id"], "comment": "опечатка"})
    assert ok.status_code == 200
    rep = client.get(f"/api/sessions/{sid}/report").json()
    assert rep["totals"]["disagreements"] == 1
    assert rep["problems"][0]["steps"][0]["disagreed"] is True


def test_validation(client):
    assert client.post("/api/sessions", json={"nickname": "a b c"}).status_code == 400
    assert client.post("/api/sessions", json={"nickname": "ok_nick", "lang": "de"}).status_code == 422
    sid = client.post("/api/sessions", json={"nickname": "ok_nick"}).json()["session_id"]
    pid = client.post(f"/api/sessions/{sid}/problems", json={"demo": True}).json()["id"]
    # confidence must be chosen before checking
    r = client.post(f"/api/sessions/{sid}/problems/{pid}/steps", json={"text": "2x+6=14"})
    assert r.status_code == 422
    assert client.post(f"/api/sessions/{sid}/transfer").status_code == 409
    assert client.get("/api/sessions/nope/report").status_code == 404


def test_parse_preview(client):
    r = client.post("/api/parse", json={"text": "2(x+3)=14"}).json()
    assert r["ok"] and r["latex"] == r"2\left(x + 3\right) = 14"
    r = client.post("/api/parse", json={"text": "2x+"}).json()
    assert not r["ok"] and r["code"] == "no_equals"


def test_auto_hint_climbs_ladder_on_repeated_error_but_not_to_level4(client):
    sid = client.post("/api/sessions", json={"nickname": "student_4"}).json()["session_id"]
    pid = client.post(f"/api/sessions/{sid}/problems", json={"demo": True}).json()["id"]
    levels = [step(client, sid, pid, "2x+3=14")["hint"]["level"] for _ in range(4)]
    assert levels == [1, 2, 3, 3]
    # explicit request after >= 2 wrong attempts unlocks the detailed walkthrough
    h = client.post(f"/api/sessions/{sid}/problems/{pid}/hint").json()
    assert h["level"] == 4 and "2x + 6 = 14" in h["text"]


def test_stuck_hint_without_error(client):
    sid = client.post("/api/sessions", json={"nickname": "student_5"}).json()["session_id"]
    pid = client.post(f"/api/sessions/{sid}/problems", json={"demo": True}).json()["id"]
    hs = [client.post(f"/api/sessions/{sid}/problems/{pid}/hint").json() for _ in range(4)]
    assert [h["level"] for h in hs] == [1, 2, 3, 3] and all(h["kind"] == "stuck" for h in hs)
