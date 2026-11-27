"""Parametrized problem generators with guaranteed integer roots.

Every form picks the root r first and derives the free term from it, so the root is an
integer by construction; generate() then re-checks it with SymPy (verifier.unique_root).

Transfer problems: for a bug id we pick a form from that bug's transfer family that
differs from the original problem's form (other numbers AND other shape), so the student
has to apply the rule, not repeat a memorised sequence.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .bugs.catalog import CATALOG
from .parser import parse_equation
from .verifier import unique_root

DEMO_TEXT = "2(x + 3) = 14"


@dataclass(frozen=True)
class Problem:
    text: str
    form: str
    root: int


def _nz(rng: random.Random, lo: int, hi: int, exclude=(0,)) -> int:
    while True:
        v = rng.randint(lo, hi)
        if v not in exclude:
            return v


def _signed(v: int) -> str:
    """'+ 3' / '- 3' for use after another term."""
    return f"+ {v}" if v >= 0 else f"- {-v}"


def _coef(a: int) -> str:
    return {1: "", -1: "-"}.get(a, str(a))


def _f_dist(rng):            # a(x ± b) = c
    r, a, b = rng.randint(-6, 9), rng.randint(2, 6), _nz(rng, -7, 9)
    return f"{a}(x {_signed(b)}) = {a * (r + b)}", r


def _f_dist_plus(rng):       # a(x ± b) ± d = c
    r, a, b, d = rng.randint(-5, 8), rng.randint(2, 5), _nz(rng, -6, 8), _nz(rng, -9, 9)
    return f"{a}(x {_signed(b)}) {_signed(d)} = {a * (r + b) + d}", r


def _f_dist_right(rng):      # c = a(b ± x)  -- bracket on the right, x second
    r, a, b = rng.randint(-5, 8), rng.randint(2, 6), _nz(rng, 1, 9)
    return f"{a * (b + r)} = {a}({b} + x)", r


def _f_linear(rng):          # a x ± b = c
    r, a, b = rng.randint(-6, 9), _nz(rng, -6, 7, (0, 1, -1)), _nz(rng, -9, 12)
    return f"{_coef(a)}x {_signed(b)} = {a * r + b}", r


def _f_both(rng):            # a x ± b = c x ± d
    r, a = rng.randint(-5, 8), rng.randint(2, 8)
    c, b = _nz(rng, 1, 7, (0, a)), _nz(rng, -9, 9)
    d = (a - c) * r + b
    if d == 0:
        b += 1
        d = (a - c) * r + b
    return f"{_coef(a)}x {_signed(b)} = {_coef(c)}x {_signed(d)}", r


def _f_const_first(rng):     # b - a x = c
    r, a, b = _nz(rng, -6, 8), rng.randint(2, 7), rng.randint(1, 15)
    return f"{b} - {_coef(a)}x = {b - a * r}", r


def _f_div(rng):             # a x = c, a may be negative
    r, a = _nz(rng, -9, 9), _nz(rng, -9, 9, (0, 1, -1))
    return f"{_coef(a)}x = {a * r}", r


def _f_div_right(rng):       # c = a x
    r, a = _nz(rng, -9, 9), _nz(rng, -9, 9, (0, 1, -1))
    return f"{a * r} = {_coef(a)}x", r


FORMS = {
    "dist": _f_dist,
    "dist_plus": _f_dist_plus,
    "dist_right": _f_dist_right,
    "linear": _f_linear,
    "both": _f_both,
    "const_first": _f_const_first,
    "div": _f_div,
    "div_right": _f_div_right,
}

MAIN_FORMS = ["dist", "linear", "both"]

# transfer_tag (from the bug catalog) -> problem forms that exercise the same rule
TRANSFER_FORMS = {
    "brackets": ["dist_plus", "dist_right", "dist"],
    "transfer": ["both", "const_first", "linear"],
    "divide": ["div", "div_right", "linear"],
}


def generate(form: str, rng: random.Random) -> Problem:
    for _ in range(50):
        text, r = FORMS[form](rng)
        eq = parse_equation(text)
        if unique_root(eq) == r:
            return Problem(text, form, r)
    raise RuntimeError(f"could not generate a valid problem for form {form}")


def demo_problem() -> Problem:
    return Problem(DEMO_TEXT, "dist", 4)


def main_problem(rng: random.Random) -> Problem:
    return generate(rng.choice(MAIN_FORMS), rng)


def transfer_problem(bug_id: str | None, original: Problem, rng: random.Random) -> Problem:
    """Similar problem without hints. bug_id None -> any form different from the original."""
    if bug_id and bug_id in CATALOG:
        forms = TRANSFER_FORMS[CATALOG[bug_id].transfer_tag]
    else:
        forms = list(FORMS)
    candidates = [f for f in forms if f != original.form] or forms
    for _ in range(50):
        p = generate(rng.choice(candidates), rng)
        if p.text != original.text and p.root != original.root:
            return p
    raise RuntimeError("could not generate a transfer problem")
