import pytest
import sympy

from thinktrace.parser import parse_equation as p
from thinktrace.verifier import equivalent, is_solved, unique_root


@pytest.mark.parametrize("prev, new", [
    ("2(x+3)=14", "2x+6=14"),
    ("2x+6=14", "2x=8"),
    ("2x=8", "x=4"),
    ("2x=8", "4=x"),
    ("5x+3=2x+9", "3x=6"),
    ("x/2+1=3", "x+2=6"),
])
def test_equivalent_steps(prev, new):
    assert equivalent(p(prev), p(new))


@pytest.mark.parametrize("prev, new", [
    ("2(x+3)=14", "2x+3=14"),
    ("2x=8", "x=6"),
    ("2x+3=11", "2x=14"),
    ("x+1=3", "0=0"),          # identity is not equivalent to a single root
])
def test_non_equivalent_steps(prev, new):
    assert not equivalent(p(prev), p(new))


@pytest.mark.parametrize("text, solved", [
    ("x=4", True), ("4=x", True), ("x=-3", True), ("x=7/2", True), ("x=3.5", True),
    ("x=8/2", False), ("x=2+2", False), ("2x=8", False), ("x+0=4", False), ("x=x", False),
])
def test_is_solved(text, solved):
    assert is_solved(p(text)) is solved


def test_unique_root():
    assert unique_root(p("2x+3=14")) == sympy.Rational(11, 2)
    assert unique_root(p("x+1=x")) is None
