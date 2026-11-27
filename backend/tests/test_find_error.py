"""Mode 'find the error': deterministic generator checked by the core, API flow, ladder, report."""
import random

import pytest
from fastapi.testclient import TestClient

from thinktrace.api import create_app
from thinktrace.bugs.catalog import CATALOG
from thinktrace.diagnose import diagnose
from thinktrace.find_error import BUGS, generate
from thinktrace.parser import parse_equation as p
from thinktrace.verifier import equivalent, is_solved


@pytest.mark.parametrize("bug", BUGS)
def test_generated_solution_has_exactly_one_error_of_that_bug(bug):
    rng = random.Random(11)
    for _ in range(40):
        t = generate(rng, bug)
        assert 4 <= len(t.steps) <= 5
        chain = [p(t.problem), *[p(s) for s in t.steps]]
        wrong = [i for i in range(1, len(chain)) if not equivalent(chain[i - 1], chain[i])]
        assert wrong == [t.error_index + 1]
        d = diagnose(chain[t.error_index], chain[t.error_index + 1])
        assert d.bug_ids == [bug] and d.matches[0].level == "exact"
        assert is_solved(chain[-1])
        assert "1x" not in t.problem and all("1x" not in s.replace("11x", "") for s in t.steps)


def test_options_correct_plus_distractors_from_catalog():
    for seed in range(30):
        t = generate(random.Random(seed))
        assert t.bug_id in t.options and len(set(t.options)) == len(t.options)
        assert set(t.options) <= set(CATALOG) and 3 <= len(t.options) <= 4


def test_generator_is_deterministic_for_a_seed():
    assert generate(random.Random(42)) == generate(random.Random(42))


@pytest.fixture
def c(tmp_path):
    return TestClient(create_app(str(tmp_path / "t.sqlite3"), static_dir=str(tmp_path / "none")))


def start(c):
    sid = c.post("/api/sessions", json={"nickname": "finder"}).json()["session_id"]
    return sid, c.post(f"/api/sessions/{sid}/find-error").json()


def answer(c, sid, pid, i, bug):
    return c.post(f"/api/sessions/{sid}/find-error/{pid}/answer", json={"step_index": i, "bug_id": bug})


def find_truth(c, sid, task):
    """Brute force through the API is not allowed in tests; recompute with the core instead."""
    chain = [p(task["text"]), *[p(s["text"]) for s in task["steps"]]]
    i = next(k for k in range(len(chain) - 1) if not equivalent(chain[k], chain[k + 1]))
    return i, diagnose(chain[i], chain[i + 1]).bug_ids[0]


def test_view_does_not_reveal_the_answer(c):
    sid, task = start(c)
    assert "error_index" not in task and "bug_id" not in task
    assert len(task["options"]) >= 3 and all(o["name"] for o in task["options"])


def test_answer_flow_and_report(c):
    sid, task = start(c)
    pid = task["id"]
    i, bug = find_truth(c, sid, task)
    wrong_step = (i + 1) % len(task["steps"])
    wrong_bug = next(o["bug_id"] for o in task["options"] if o["bug_id"] != bug)

    r = answer(c, sid, pid, wrong_step, bug).json()
    assert (r["step_correct"], r["type_correct"], r["solved"]) == (False, True, False)
    r = answer(c, sid, pid, i, wrong_bug).json()
    assert (r["step_correct"], r["type_correct"], r["solved"]) == (True, False, False)
    r = answer(c, sid, pid, i, bug).json()
    assert r["solved"] and r["problem"]["error_index"] == i and r["problem"]["bug_id"] == bug
    assert answer(c, sid, pid, i, bug).status_code == 409

    rep = c.get(f"/api/sessions/{sid}/report").json()
    fe = next(x for x in rep["problems"] if x["kind"] == "find_error")
    assert fe["solved"] and [a["step_correct"] for a in fe["answers"]] == [False, True, True]
    assert any(e["type"] == "find_error_answer" for e in rep["timeline"])


def test_hint_ladder(c):
    sid, task = start(c)
    pid = task["id"]
    i, bug = find_truth(c, sid, task)
    url = f"/api/sessions/{sid}/find-error/{pid}/hint"
    h1, h2, h3 = (c.post(url).json() for _ in range(3))
    assert [h1["level"], h2["level"], h3["level"]] == [1, 2, 3]
    assert CATALOG[bug].name["ru"] not in h1["text"]              # level 1 does not give the type away
    assert task["steps"][i]["text"] in h2["text"]                  # level 2 points to the step
    assert c.post(url).json()["level"] == 3                        # level 4 needs >= 2 wrong answers
    other = (i + 1) % len(task["steps"])
    answer(c, sid, pid, other, bug)
    answer(c, sid, pid, other, bug)
    assert c.post(url).json()["level"] == 4


def test_validation_and_mode_separation(c):
    sid, task = start(c)
    pid = task["id"]
    assert answer(c, sid, pid, 99, task["options"][0]["bug_id"]).status_code == 400
    assert answer(c, sid, pid, 0, "NOT_A_BUG").status_code == 400
    r = c.post(f"/api/sessions/{sid}/problems/{pid}/steps", json={"text": "x=1", "confidence": "low"})
    assert r.status_code == 409
    main = c.post(f"/api/sessions/{sid}/problems", json={"demo": True}).json()["id"]
    assert c.post(f"/api/sessions/{sid}/find-error/{main}/hint").status_code == 409
