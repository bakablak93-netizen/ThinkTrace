import pytest

from thinktrace.diagnose import diagnose
from thinktrace.expr import eq_text
from thinktrace.hints import error_hint, next_level, next_move, stuck_hint
from thinktrace.parser import parse_equation as p
from thinktrace.verifier import unique_root

WRONG = [
    ("2(x+3)=14", "2x+3=14"), ("3(x-2)=9", "3x-2=9"), ("2x+3=11", "2x=11+3"),
    ("5x+3=2x+9", "5x+2x=9+3"), ("3x=12", "x=12"), ("2x+4=10", "x+2=10"),
    ("-2(x-4)=6", "-2x-8=6"), ("7-(x-3)=3x+2", "7-x-3=3x+2"),      # DIST_SIGN
    ("3x+2=11", "5x=11"), ("2x-7=5", "-5x=5"),                     # COMBINE_UNLIKE
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


@pytest.mark.parametrize("bug_id", ["DIST_FIRST_ONLY", "SIGN_ON_TRANSFER", "DIVIDE_ONE_SIDE", "DIST_SIGN", "COMBINE_UNLIKE"])
@pytest.mark.parametrize("lang", ["ru", "en"])
def test_catalog_templates_levels_1_3_pass_the_guard_on_bank_problems(bug_id, lang):
    """Every template of levels 1-3, filled with real bank problems, passes leaks_answer()."""
    from thinktrace.bank import BANK
    from thinktrace.bugs.catalog import CATALOG
    from thinktrace.diagnose import Diagnosis, BugMatch
    from thinktrace.hints import leaks_answer
    checked = 0
    for bp in BANK.values():
        eq = p(bp.text)
        for cand in CATALOG[bug_id].transforms(eq):
            d = Diagnosis((BugMatch(bug_id, 0.9, "exact", cand.correct),), "first")
            for level in (1, 2, 3):
                text = error_hint(d, level, eq, eq_text(cand.buggy), lang).text
                assert not leaks_answer(text, unique_root(eq), [bp.text, eq_text(cand.buggy)]), (bp.id, level, text)
                checked += 1
    assert checked > 0


@pytest.mark.parametrize("prev, step, correct", [
    ("-2(x-4)=6", "-2x-8=6", "-2x + 8 = 6"),
    ("3x+2=11", "5x=11", "3x = 9"),
])
def test_level4_of_new_bugs_uses_their_own_template(prev, step, correct):
    d = diagnose(p(prev), p(step))
    text = error_hint(d, 4, p(prev), eq_text(p(step)), "ru").text
    assert correct in text and "Разберём подробно" in text
