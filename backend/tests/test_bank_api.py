"""Problem bank through the API: level choice, next problem, twin as the final problem."""
import pytest
from fastapi.testclient import TestClient

from thinktrace.api import create_app
from thinktrace.bank import BANK


@pytest.fixture
def c(tmp_path):
    return TestClient(create_app(str(tmp_path / "t.sqlite3"), static_dir=str(tmp_path / "none")))


def start(c):
    return c.post("/api/sessions", json={"nickname": "bank_user"}).json()["session_id"]


def step(c, sid, pid, text):
    return c.post(f"/api/sessions/{sid}/problems/{pid}/steps", json={"text": text, "confidence": "high"}).json()


def test_default_problem_is_unchanged_and_from_the_bank(c):
    sid = start(c)
    p = c.post(f"/api/sessions/{sid}/problems", json={"demo": True}).json()
    assert p["text"] == "2(x + 3) = 14" and p["bank_id"] == "B1" and p["level"] == "B"


def test_generated_problem_has_no_bank_fields(c):
    sid = start(c)
    p = c.post(f"/api/sessions/{sid}/problems", json={}).json()
    assert p["bank_id"] is None and p["level"] is None


@pytest.mark.parametrize("level", ["A", "B", "C"])
def test_level_choice_and_next_problem(c, level):
    sid = start(c)
    seen = []
    after = None
    for _ in range(6):
        body = {"level": level} | ({"after": after} if after else {})
        p = c.post(f"/api/sessions/{sid}/problems", json=body).json()
        assert p["level"] == level and BANK[p["bank_id"]].role == "main"
        seen.append(p["bank_id"])
        after = p["bank_id"]
    assert seen == [f"{level}{i}" for i in (1, 2, 3, 4, 5, 1)]   # cyclic


def test_final_problem_is_the_twin(c):
    sid = start(c)
    p = c.post(f"/api/sessions/{sid}/problems", json={"level": "A"}).json()   # A1: 3x + 5 = 20
    for s in ("3x = 15", "x = 5"):
        assert step(c, sid, p["id"], s)["status"] in ("correct", "solved")
    t = c.post(f"/api/sessions/{sid}/transfer").json()
    assert t["kind"] == "transfer" and t["bank_id"] == "A1T" and t["text"] == BANK["A1T"].text
    assert not t["hints_enabled"]


def test_fractional_problem_full_flow(c):
    sid = start(c)
    p = c.post(f"/api/sessions/{sid}/problems", json={"level": "C", "after": "C4"}).json()
    assert p["bank_id"] == "C5" and p["text"] == "2(x + 1) = -(x - 6)"
    r = step(c, sid, p["id"], "2x + 2 = -x - 6")            # sign error in -(x - 6)
    assert r["status"] == "error" and r["diagnosis"]["candidates"][0]["bug_id"] == "DIST_SIGN"
    for s in ("2x + 2 = -x + 6", "3x = 4", "x = 4/3"):
        r = step(c, sid, p["id"], s)
    assert r["status"] == "solved"
    t = c.post(f"/api/sessions/{sid}/transfer").json()
    assert t["bank_id"] == "C5T"
    rep = c.get(f"/api/sessions/{sid}/report").json()
    assert rep["problems"][0]["solved"]


def test_validation(c):
    sid = start(c)
    assert c.post(f"/api/sessions/{sid}/problems", json={"level": "D"}).status_code == 422
    assert c.post(f"/api/sessions/{sid}/problems", json={"level": "A", "after": "ZZ"}).status_code == 400
