import random

import pytest

from thinktrace.bugs.catalog import CATALOG
from thinktrace.parser import parse_equation
from thinktrace.problems import FORMS, TRANSFER_FORMS, demo_problem, generate, transfer_problem
from thinktrace.verifier import unique_root


@pytest.mark.parametrize("form", list(FORMS))
def test_generated_problems_have_integer_roots(form):
    rng = random.Random(42)
    for _ in range(100):
        prob = generate(form, rng)
        root = unique_root(parse_equation(prob.text))
        assert root == prob.root and root.is_integer


def test_every_bug_has_transfer_family():
    for bug in CATALOG.values():
        assert bug.transfer_tag in TRANSFER_FORMS


@pytest.mark.parametrize("bug_id", list(CATALOG) + [None])
def test_transfer_differs_from_original(bug_id):
    rng = random.Random(7)
    orig = demo_problem()
    for _ in range(30):
        t = transfer_problem(bug_id, orig, rng)
        assert t.form != orig.form and t.text != orig.text and t.root != orig.root
        if bug_id:
            assert t.form in TRANSFER_FORMS[CATALOG[bug_id].transfer_tag]


def test_transfer_for_dist_bug_contains_brackets_the_bug_applies_to():
    rng = random.Random(3)
    for _ in range(20):
        t = transfer_problem("DIST_FIRST_ONLY", demo_problem(), rng)
        assert CATALOG["DIST_FIRST_ONLY"].transforms(parse_equation(t.text))
