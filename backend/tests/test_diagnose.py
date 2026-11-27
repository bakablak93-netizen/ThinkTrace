"""Diagnosis tests: at least 5 wrong steps per bug, plus slips that must stay UNKNOWN."""
import pytest

from thinktrace.diagnose import UNKNOWN, diagnose
from thinktrace.expr import eq_text
from thinktrace.parser import parse_equation as p
from thinktrace.verifier import equivalent

DIST_FIRST_ONLY = [
    ("2(x+3)=14", "2x+3=14", "exact"),
    ("3(x-2)=9", "3x-2=9", "exact"),
    ("4(x+5)=36", "4x+5=36", "exact"),
    ("5(2x+1)=35", "10x+1=35", "exact"),
    ("2(x+3)=14", "x+6=14", "exact"),          # the other term multiplied
    ("7-2(x+1)=1", "7-2x-1=1", "exact"),       # bracket inside a sum
    ("3(x+4)=2x+5", "3x+4=2x+5", "exact"),
    ("2(x+3)=14", "2x=11", "solution"),        # bug + moving 3 in one line
]
SIGN_ON_TRANSFER = [
    ("2x+3=11", "2x=11+3", "exact"),
    ("5x-4=11", "5x=11-4", "exact"),
    ("5x+3=2x+9", "5x+2x=9-3", "exact"),
    ("5x+3=2x+9", "5x+2x=9+3", "exact"),       # both terms moved wrong
    ("x+7=2", "x=2+7", "exact"),
    ("3x=x+8", "3x+x=8", "exact"),
    ("2x+3=11", "2x=14", "exact"),             # bug + simplifying the side
    ("2x+3=11", "x=7", "solution"),            # bug + dividing in one line
]
DIVIDE_ONE_SIDE = [
    ("3x=12", "x=12", "exact"),
    ("3x=12", "3x=4", "exact"),
    ("2(x+3)=14", "x+3=14", "exact"),
    ("-4x=20", "x=20", "exact"),
    ("2x+4=10", "x+2=10", "exact"),
    ("6x=18", "x=18", "exact"),
    ("14=7x", "2=7x", "exact"),
]


def _check(prev, step, bug_id, level):
    a, b = p(prev), p(step)
    assert not equivalent(a, b), "test step must be wrong"
    d = diagnose(a, b)
    assert d.bug_ids == [bug_id], (prev, step, d.bug_ids)
    assert d.matches[0].level == level
    assert d.pattern == "first"


@pytest.mark.parametrize("prev, step, level", DIST_FIRST_ONLY)
def test_dist_first_only(prev, step, level):
    _check(prev, step, "DIST_FIRST_ONLY", level)


@pytest.mark.parametrize("prev, step, level", SIGN_ON_TRANSFER)
def test_sign_on_transfer(prev, step, level):
    _check(prev, step, "SIGN_ON_TRANSFER", level)


@pytest.mark.parametrize("prev, step, level", DIVIDE_ONE_SIDE)
def test_divide_one_side(prev, step, level):
    _check(prev, step, "DIVIDE_ONE_SIDE", level)


@pytest.mark.parametrize("prev, step", [
    ("2x+6=14", "2x=7"),      # arithmetic slip
    ("2x=8", "x=3"),
    ("3x+5=20", "3x=16"),
    ("2x=8", "x=6"),
    ("4x-3=9", "4x=11"),
    ("5x=35", "x=8"),
])
def test_arithmetic_slips_are_unknown(prev, step):
    d = diagnose(p(prev), p(step))
    assert d.is_unknown and d.bug_ids == [UNKNOWN]


def test_exact_confidence_higher_than_solution():
    exact = diagnose(p("2(x+3)=14"), p("2x+3=14")).matches[0]
    sol = diagnose(p("2(x+3)=14"), p("2x=11")).matches[0]
    assert exact.confidence > sol.confidence


def test_ambiguous_root_gives_several_candidates_with_split_confidence():
    # x=3 fits DIVIDE_ONE_SIDE (x+1=4) and SIGN_ON_TRANSFER (2x=4+2)
    d = diagnose(p("2x+2=4"), p("x=3"))
    assert set(d.bug_ids) == {"DIVIDE_ONE_SIDE", "SIGN_ON_TRANSFER"}
    assert d.is_ambiguous
    assert all(m.confidence < diagnose(p("2x+3=11"), p("x=7")).matches[0].confidence
               for m in d.matches)


def test_repeated_pattern_from_history():
    d = diagnose(p("3(x-2)=9"), p("3x-2=9"), history=["DIST_FIRST_ONLY"])
    assert d.pattern == "repeated"
    d = diagnose(p("3(x-2)=9"), p("3x-2=9"), history=["SIGN_ON_TRANSFER"])
    assert d.pattern == "first"


def test_correct_version_is_provided_for_level4():
    m = diagnose(p("2(x+3)=14"), p("2x+3=14")).matches[0]
    assert eq_text(m.correct) == "2x + 6 = 14"
    m = diagnose(p("3x=12"), p("x=12")).matches[0]
    assert equivalent(m.correct, p("3x=12"))
