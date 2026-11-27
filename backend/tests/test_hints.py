import pytest

from thinktrace.diagnose import diagnose
from thinktrace.expr import eq_text
from thinktrace.hints import error_hint, next_level, next_move, stuck_hint
from thinktrace.parser import parse_equation as p
from thinktrace.verifier import unique_root

WRONG = [
    ("2(x+3)=14", "2x+3=14"), ("3(x-2)=9", "3x-2=9"), ("2x+3=11", "2x=11+3"),
    ("5x+3=2x+9", "5x+2x=9+3"), ("3x=12", "x=12"), ("2x+4=10", "x+2=10"),
    ("2x+2=4", "x=3"),          # ambiguous
    ("2x+6=14", "2x=7"),        # unknown
]


@pytest.mark.parametrize("prev, step", WRONG)
@pytest.mark.parametrize("lang", ["ru", "en"])
def test_levels_1_to_3_never_contain_the_answer(prev, step, lang):
    root = unique_root(p(prev))
    d = diagnose(p(prev), p(step))
    for level in (1, 2, 3):
        text = error_hint(d, level, p(prev), eq_text(p(step)), lang).text
        assert f"x = {root}" not in text and f"x={root}" not in text
        if str(root) not in prev and str(root) not in step:
            assert str(root) not in text


def test_ambiguous_and_unknown_first_hint_is_generic():
    generic = error_hint(diagnose(p("2x+6=14"), p("2x=7")), 1, p("2x+6=14"), "2x = 7", "ru").text
    amb = error_hint(diagnose(p("2x+2=4"), p("x=3")), 1, p("2x+2=4"), "x = 3", "ru").text
    specific = error_hint(diagnose(p("3x=12"), p("x=12")), 1, p("3x=12"), "x = 12", "ru").text
    assert amb == generic
    assert specific != generic


def test_level4_shows_correct_version_of_the_action():
    d = diagnose(p("2(x+3)=14"), p("2x+3=14"))
    text = error_hint(d, 4, p("2(x+3)=14"), "2x + 3 = 14", "ru").text
    assert "2x + 6 = 14" in text


def test_ladder_policy():
    assert next_level([], 1) == 1
    assert next_level([1], 1) == 2
    assert next_level([1, 2], 1) == 3
    assert next_level([1, 2, 3], 1) == 3   # level 4 needs >= 2 wrong attempts
    assert next_level([1, 2, 3], 2) == 4


@pytest.mark.parametrize("eq, kind, result", [
    ("2(x+3)=14", "expand", "2x + 6 = 14"),
    ("5x+3=2x+9", "collect", "3x = 6"),
    ("2x+6=14", "move", "2x = 8"),
    ("2x=8", "divide", "x = 4"),
    ("14=2x", "divide", "7 = x"),
])
def test_next_move(eq, kind, result):
    k, e = next_move(p(eq))
    assert k == kind and eq_text(e) == result


def test_stuck_hints_levels_1_3_do_not_give_result():
    for level in (1, 2, 3):
        assert "x = 4" not in stuck_hint(p("2x=8"), level, "ru").text
