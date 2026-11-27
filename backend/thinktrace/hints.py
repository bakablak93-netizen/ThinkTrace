"""Hint Ladder (deterministic templates; LLM wording comes in stage 2).

Levels:
  1 - guiding question
  2 - points at the problematic step
  3 - explains the rule
  4 - detailed walkthrough: shows the correct version of the action. Unlocked only
      after at least LEVEL4_MIN_ATTEMPTS wrong attempts in the current episode.
Levels 1-3 never contain the answer: they are fixed templates plus the student's own
previous/current lines. (Stage 2 adds a guard for LLM-written texts on levels 1-3.)

Ambiguous diagnosis (several bug candidates) or UNKNOWN: levels 1-2 are generic
("check this step again"), they never name a specific error the student may not
have made. Level 3 lists the rules of the candidates.

"Episode" = everything since the last accepted step. The ladder restarts when the
diagnosed bug set changes within an episode.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .bugs.catalog import CATALOG
from .diagnose import Diagnosis
from .expr import Equation, Prod, Sum, eq_text, from_linear, linear_form
from .i18n import pick, tr

LEVEL4_MIN_ATTEMPTS = 2
MAX_LEVEL = 4


@dataclass(frozen=True)
class Hint:
    level: int
    text: str
    kind: Literal["error", "stuck"]


def next_level(levels_shown: list[int], wrong_attempts: int) -> int:
    """Next ladder level given the levels already shown in this episode."""
    last = max(levels_shown, default=0)
    if last < 3:
        return last + 1
    return 4 if wrong_attempts >= LEVEL4_MIN_ATTEMPTS else 3


# ---------- "what is the next move" (used for stuck hints and generic level 4) ----------

def _has_bracket(node) -> bool:
    if isinstance(node, Prod):
        return any(isinstance(f, Sum) for f in node.factors) or any(_has_bracket(f) for f in node.factors)
    if isinstance(node, Sum):
        return any(_has_bracket(n) for _, n in node.items)
    if hasattr(node, "arg"):
        return _has_bracket(node.arg)
    if hasattr(node, "num"):
        return _has_bracket(node.num) or _has_bracket(node.den)
    return False


def next_move(eq: Equation) -> tuple[str, Equation]:
    """Deterministic suggestion of the next correct move and its result."""
    la, lb = linear_form(eq.lhs)
    ra, rb = linear_form(eq.rhs)
    if _has_bracket(eq.lhs) or _has_bracket(eq.rhs):
        return "expand", Equation(from_linear(la, lb), from_linear(ra, rb))
    if la != 0 and ra != 0:
        return "collect", Equation(from_linear(la - ra, 0), from_linear(0, rb - lb))
    # orient: x side first
    if la == 0:
        a, b, c = ra, rb, lb
        flip = True
    else:
        a, b, c = la, lb, rb
        flip = False
    if b != 0:
        res = (from_linear(a, 0), from_linear(0, c - b))
        kind = "move"
    elif a != 1:
        res = (from_linear(1, 0), from_linear(0, c / a))
        kind = "divide"
    else:
        res = (from_linear(1, 0), from_linear(0, c))
        kind = "simplify"
    return kind, Equation(*(reversed(res) if flip else res))


def stuck_hint(eq: Equation, level: int, lang: str) -> Hint:
    kind, correct = next_move(eq)
    if level >= 4:
        rule = tr(f"stuck.{kind}.3", lang)
        return Hint(4, tr("hint.level4.next", lang, rule=rule, prev=eq_text(eq), correct=eq_text(correct)), "stuck")
    return Hint(level, tr(f"stuck.{kind}.{level}", lang), "stuck")


def error_hint(diag: Diagnosis, level: int, prev: Equation, step_text: str, lang: str) -> Hint:
    prev_text = eq_text(prev)
    specific = len(diag.matches) == 1
    bug = CATALOG[diag.matches[0].bug_id] if specific else None

    if level == 1:
        text = pick(bug.hints[1], lang) if bug else tr("hint.general.1", lang)
    elif level == 2:
        if bug:
            text = tr("hint.focus.2", lang, prev=prev_text, step=step_text, focus_hint=pick(bug.hints[2], lang))
        else:
            text = tr("hint.general.2", lang, prev=prev_text, step=step_text)
    elif level == 3:
        if diag.matches:
            text = " ".join(pick(CATALOG[m.bug_id].hints[3], lang) for m in diag.matches[:2])
        else:
            text = tr("hint.general.3", lang)
    else:
        if bug:
            text = tr("hint.level4", lang, rule=pick(bug.hints[3], lang), prev=prev_text,
                      correct=eq_text(diag.matches[0].correct))
        else:
            _, correct = next_move(prev)
            text = tr("hint.level4.next", lang, rule=tr("hint.general.3", lang), prev=prev_text,
                      correct=eq_text(correct))
    return Hint(level, text, "error")
