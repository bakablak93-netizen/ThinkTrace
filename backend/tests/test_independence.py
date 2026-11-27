"""Independence Index: formula from report.py docstring, checked on real API sessions."""
import json

import pytest
from fastapi.testclient import TestClient

from thinktrace.api import create_app
from thinktrace.bugs.catalog import CATALOG
from thinktrace.expr import eq_text
from thinktrace.llm import ProviderClient
from thinktrace.parser import parse_equation


class Fake(ProviderClient):
    def _complete(self, system, user, schema_name=None, schema=None):
        if schema_name == "feedback":
            return json.dumps({"correct": "Верно замечено.", "attention": "Проверь скобки."})
        return '{"hint": "Посмотри на скобки."}'


@pytest.fixture
def c(tmp_path):
    return TestClient(create_app(str(tmp_path / "t.sqlite3"), static_dir=str(tmp_path / "none"), llm=Fake()))


def session(c):
    sid = c.post("/api/sessions", json={"nickname": "index_nick"}).json()["session_id"]
    pid = c.post(f"/api/sessions/{sid}/problems", json={"demo": True}).json()["id"]
    return sid, pid


def step(c, sid, pid, text):
    return c.post(f"/api/sessions/{sid}/problems/{pid}/steps", json={"text": text, "confidence": "low"}).json()


def index(c, sid):
    return c.get(f"/api/sessions/{sid}/report").json()["independence"]


def solve_transfer(c, sid, with_error=False):
    t = c.post(f"/api/sessions/{sid}/transfer").json()
    eq = parse_equation(t["text"])
    if with_error:
        from thinktrace.verifier import equivalent
        cand = next(cand for b in CATALOG.values() for cand in b.transforms(eq) if not equivalent(eq, cand.buggy))
        assert step(c, sid, t["id"], eq_text(cand.buggy))["status"] == "error"
    from thinktrace.verifier import unique_root
    step(c, sid, t["id"], f"x={unique_root(eq)}")


def test_no_steps_no_index(c):
    sid, _ = session(c)
    assert index(c, sid) is None


def test_perfect_session_is_100(c):
    sid, pid = session(c)
    for s in ("2x+6=14", "2x=8", "x=4"):
        step(c, sid, pid, s)
    solve_transfer(c, sid)
    ix = index(c, sid)
    assert ix["value"] == 100 and not ix["partial"] and ix["transfer_component"] == 1.0


def test_demo_scenario_by_hand(c):
    sid, pid = session(c)
    step(c, sid, pid, "2x+3=14")                                   # error -> automatic hint (not counted)
    c.post(f"/api/sessions/{sid}/problems/{pid}/hint")             # requested hint: H = 1
    for s in ("2x+6=14", "2x=8", "x=4"):
        step(c, sid, pid, s)
    ix = index(c, sid)
    # A = 1 - 1/4 = 0.75, B = 3/4 = 0.75, no transfer: 100 * (0.4*0.75 + 0.3*0.75) / 0.7 = 75
    assert (ix["hints_requested"], ix["hints_component"], ix["attempts_component"]) == (1, 0.75, 0.75)
    assert ix["value"] == 75 and ix["partial"] and ix["transfer_component"] is None
    solve_transfer(c, sid, with_error=True)                        # C = 0.5
    ix = index(c, sid)
    # 100 * (0.4*0.75 + 0.3*0.75 + 0.3*0.5) = 67.5 -> 68
    assert ix["value"] == 68 and not ix["partial"] and ix["transfer_component"] == 0.5


def test_unsolved_transfer_counts_zero(c):
    sid, pid = session(c)
    for s in ("2x+6=14", "2x=8", "x=4"):
        step(c, sid, pid, s)
    c.post(f"/api/sessions/{sid}/transfer")
    assert index(c, sid)["value"] == 70                            # 100 * (0.4 + 0.3 + 0)


def test_many_hints_floor_at_zero_component(c):
    sid, pid = session(c)
    for _ in range(6):
        c.post(f"/api/sessions/{sid}/problems/{pid}/hint")
    step(c, sid, pid, "2x+6=14")
    assert index(c, sid)["hints_component"] == 0.0


def test_explanation_does_not_change_index(c):
    sid, pid = session(c)
    step(c, sid, pid, "2x+3=14")
    eid = step(c, sid, pid, "2x+6=14")["event_id"]
    before = index(c, sid)
    r = c.post(f"/api/sessions/{sid}/problems/{pid}/explain", json={"step_event_id": eid, "text": "забыл умножить 3"})
    assert r.status_code == 200
    assert index(c, sid) == before


def test_find_error_mode_does_not_change_index(c):
    sid, pid = session(c)
    step(c, sid, pid, "2x+6=14")
    before = index(c, sid)
    t = c.post(f"/api/sessions/{sid}/find-error").json()
    c.post(f"/api/sessions/{sid}/find-error/{t['id']}/hint")
    c.post(f"/api/sessions/{sid}/find-error/{t['id']}/answer", json={"step_index": 0, "bug_id": t["options"][0]["bug_id"]})
    assert index(c, sid) == before
