"""Problem bank: every problem and twin is verified by the deterministic core."""
import re
from fractions import Fraction

import pytest
import sympy

from thinktrace.bank import BANK, DEFAULT_ID, LEVELS, main_problems, next_problem, twin_of
from thinktrace.bugs.catalog import CATALOG
from thinktrace.expr import X, eq_text, to_sympy
from thinktrace.hints import next_move
from thinktrace.parser import parse_equation
from thinktrace.verifier import equivalent, is_solved, unique_root

ALL = list(BANK.values())


def structure(text: str) -> str:
    """Operations, brackets and signs of the written equation with numbers replaced by n."""
    return re.sub(r"\d+", "n", eq_text(parse_equation(text)))


def x_sides(text: str) -> int:
    eq = parse_equation(text)
    return sum(1 for side in (eq.lhs, eq.rhs) if to_sympy(side).has(X))


def chain(text: str, limit: int = 8):
    """Canonical correct solution path (deterministic next_move), problem first."""
    eq = parse_equation(text)
    out = [eq]
    while not is_solved(eq) and len(out) < limit:
        eq = next_move(eq)[1]
        out.append(eq)
    return out


def test_counts():
    for level in LEVELS:
        assert len(main_problems(level)) == 5
    assert len(ALL) == 30  # 15 main + 15 twins


@pytest.mark.parametrize("p", ALL, ids=lambda p: p.id)
def test_sympy_confirms_unique_solution(p):
    eq = parse_equation(p.text)
    sols = sympy.solveset(sympy.expand(to_sympy(eq.lhs) - to_sympy(eq.rhs)), X, sympy.S.Reals)
    assert isinstance(sols, sympy.FiniteSet) and len(sols) == 1
    root = next(iter(sols))
    assert Fraction(int(root.p), int(root.q)) == p.root
    assert p.root != 0
    assert is_solved(parse_equation(p.solution))


@pytest.mark.parametrize("p", main_problems(), ids=lambda p: p.id)
def test_twin_same_structure_other_solution(p):
    t = twin_of(p.id)
    assert t.role == "twin" and t.twin_id == p.id and BANK[p.twin_id] is t
    assert t.level == p.level and t.tags == p.tags
    assert structure(t.text) == structure(p.text)
    assert t.text.count("(") == p.text.count("(")
    assert t.root != p.root and t.text != p.text


@pytest.mark.parametrize("p", ALL, ids=lambda p: p.id)
def test_level_definition(p):
    has_bracket = "(" in p.text
    if p.level == "A":
        assert not has_bracket and x_sides(p.text) == 1
        assert re.fullmatch(r"-?\d*x [+-] \d+ = -?\d+", p.text)
    elif p.level == "B":
        assert has_bracket and x_sides(p.text) == 1
    else:
        assert has_bracket and x_sides(p.text) == 2


def test_level_c_has_negative_factors_and_one_fractional_problem():
    c = main_problems("C")
    assert sum(1 for p in c if p.root.denominator != 1) == 1
    assert any(re.search(r"(^|[=(] ?)-\d*\(|- \(", p.text) for p in c)


@pytest.mark.parametrize("p", ALL, ids=lambda p: p.id)
def test_tags_are_catalog_errors_that_can_happen_in_this_problem(p):
    steps = chain(p.text)
    assert is_solved(steps[-1]) and equivalent(steps[0], steps[-1])
    for tag in p.tags:
        assert tag in CATALOG
        applicable = any(not equivalent(eq, c.buggy) for eq in steps[:-1] for c in CATALOG[tag].transforms(eq))
        assert applicable, f"{p.id}: {tag} cannot occur on the solution path"


def test_default_and_navigation():
    assert BANK[DEFAULT_ID].text == "2(x + 3) = 14"
    assert next_problem("A").id == "A1"
    assert next_problem("A", "A1").id == "A2"
    assert next_problem("A", "A5").id == "A1"           # cyclic
    assert next_problem("C", "B2").id == "C1"           # other level -> first
    assert all(p.role == "main" for p in main_problems())
