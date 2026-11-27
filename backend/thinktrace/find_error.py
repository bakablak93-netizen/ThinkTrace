"""Mode "Find the error": a worked solution with exactly one error from the catalog.

Deterministic, no LLM. Problem form a(x + b) = cx + d, whose correct solution has 5 steps:
  1 expand        ax + ab = cx + d          <- DIST_FIRST_ONLY is placed here
  2 move cx       ax - cx + ab = d          <- SIGN_ON_TRANSFER (step 2 or 3)
  3 move ab       ax - cx = d - ab
  4 combine       (a - c)x = d - ab
  5 divide        x = r                     <- DIVIDE_ONE_SIDE
After the error, the remaining steps are solved CORRECTLY from the wrong line, like a real
student would. Every generated solution is checked by the deterministic core: all
transitions except one are equivalent, and diagnose() of the wrong transition returns
exactly the chosen bug (exact match). Otherwise new numbers are drawn.

Answer options: the correct bug + up to 3 other catalog bugs as distractors (with the
current 3-bug catalog that is 2 distractors).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from fractions import Fraction

from .bugs.catalog import CATALOG
from .diagnose import diagnose
from .expr import Div, Equation, Neg, Node, Num, Prod, Sum, Var, eq_text, make_sum
from .parser import parse_equation
from .verifier import equivalent, is_solved

BUGS = ("DIST_FIRST_ONLY", "SIGN_ON_TRANSFER", "DIVIDE_ONE_SIDE")
MAX_DISTRACTORS = 3


@dataclass(frozen=True)
class FindErrorTask:
    problem: str
    steps: list[str]          # the worked solution, one line per step (problem excluded)
    error_index: int          # 0-based index into steps
    bug_id: str
    options: list[str]        # bug ids, shuffled
    root: int                 # root of the original problem


def _x(coef: Fraction) -> tuple[int, Node]:
    c = abs(Fraction(coef))
    node = Var() if c == 1 else Prod((Num(c), Var()))
    return (1 if coef > 0 else -1), node


def _n(v: Fraction) -> tuple[int, Node]:
    return (1 if v >= 0 else -1), Num(abs(Fraction(v)))


def _side(*items) -> Node:
    return make_sum([it for it in items if it is not None])


def _rest(A, B, C, D, sign_bug_at: int | None = None) -> list[Equation]:
    """Steps 2..5 for Ax + B = Cx + D. sign_bug_at = 2 or 3 keeps the moved term's sign."""
    keep_c = sign_bug_at == 2
    keep_b = sign_bug_at == 3
    c_moved = C if keep_c else -C
    b_moved = B if keep_b else -B
    s2 = Equation(_side(_x(A), _x(c_moved), _n(B)), _side(_n(D)))
    s3 = Equation(_side(_x(A), _x(c_moved)), _side(_n(D), _n(b_moved)))
    k, v = A + c_moved, D + b_moved
    s4 = Equation(_side(_x(k)), _side(_n(v)))
    return [s2, s3, s4], k, v


def _build(a, b, c, d, bug: str, rng: random.Random) -> tuple[str, list[Equation], int]:
    a, b, c, d = map(Fraction, (a, b, c, d))
    problem = Equation(Prod((Num(a), Sum(((1, Var()), _n(b))))), _side(_x(c), _n(d)))
    if bug == "DIST_FIRST_ONLY":
        s1 = Equation(_side(_x(a), _n(b)), _side(_x(c), _n(d)))          # only ax multiplied
        mid, k, v = _rest(a, b, c, d)
        err = 0
    else:
        s1 = Equation(_side(_x(a), _n(a * b)), _side(_x(c), _n(d)))
        if bug == "SIGN_ON_TRANSFER":
            at = rng.choice((2, 3))
            mid, k, v = _rest(a, a * b, c, d, sign_bug_at=at)
            err = at - 1
        else:
            mid, k, v = _rest(a, a * b, c, d)
            err = 4
    if bug == "DIVIDE_ONE_SIDE":
        s5 = Equation(Var(), Num(v) if v >= 0 else make_sum([(-1, Num(-v))]))   # divided only the left side
    else:
        q = v / k
        s5 = Equation(Var(), _frac_node(q))
    if v == 0:
        return problem, [], -1            # "... = 0" lines look odd: draw new numbers
    return problem, [s1, *mid, s5], err


def _frac_node(q: Fraction) -> Node:
    node = Num(abs(q)) if q.denominator == 1 else Div(Num(abs(q.numerator)), Num(q.denominator))
    return node if q >= 0 else Neg(node)


def _valid(problem: Equation, steps: list[Equation], err: int, bug: str) -> bool:
    chain = [problem, *steps]
    for i in range(1, len(chain)):
        same = equivalent(chain[i - 1], chain[i])
        if (i - 1 == err) == same:
            return False
    d = diagnose(chain[err], chain[err + 1])
    return d.bug_ids == [bug] and d.matches[0].level == "exact" and is_solved(steps[-1])


def generate(rng: random.Random, bug: str | None = None) -> FindErrorTask:
    bug = bug or rng.choice(BUGS)
    for _ in range(200):
        c = rng.randint(1, 4)
        a = rng.randint(c + 2, c + 5)                  # a - c >= 2: the divide step exists
        r = rng.choice([v for v in range(-5, 9) if v != 0])
        b = rng.choice([v for v in range(-6, 8) if v != 0])
        d = a * (r + b) - c * r
        if d == 0 or a * b == d:
            continue
        problem, steps, err = _build(a, b, c, d, bug, rng)
        if not steps:
            continue
        # display texts must parse back to the same equations (what the student sees)
        steps = [parse_equation(eq_text(s)) for s in steps]
        if _valid(problem, steps, err, bug):
            others = [x for x in CATALOG if x != bug]
            rng.shuffle(others)
            options = [bug, *others[:MAX_DISTRACTORS]]
            rng.shuffle(options)
            return FindErrorTask(eq_text(problem), [eq_text(s) for s in steps], err, bug, options, r)
    raise RuntimeError("could not generate a find-the-error task")
