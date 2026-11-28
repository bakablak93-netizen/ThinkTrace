"""Catalog of typical errors (bugs) in solving linear equations.

Each Bug has:
  id, name / description (ru/kk/en), hints for levels 1-3 (ru/kk/en), optional hint for
  level 4 (with {prev} and {correct} placeholders; without it level 4 is composed from the
  level-3 rule + the correct step), transfer_tag (which problem family checks understanding
  of this bug), and
  transforms(prev_eq) -> list[Candidate]: every way this error could be applied to the
  previous step. Each Candidate carries the buggy result AND the correct version of the
  same action (shown only on hint level 4).

kk texts: added in stage 2 (missing keys fall back to ru).
en texts of DIST_SIGN and COMBINE_UNLIKE: written by the team, need review by a native speaker.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from itertools import combinations, product
from typing import Callable

import sympy

from ..expr import (
    X, Div, Equation, Node, Prod, Sum, from_linear, linear_form, make_sum,
    scaled, side_items, to_sympy, x_coeff,
)


@dataclass(frozen=True)
class Candidate:
    buggy: Equation
    correct: Equation


@dataclass(frozen=True)
class Bug:
    id: str
    name: dict[str, str]
    description: dict[str, str]
    transforms: Callable[[Equation], list[Candidate]]
    hints: dict[int, dict[str, str]]
    transfer_tag: str
    extra: dict = field(default_factory=dict)


def _const(node: Node) -> Fraction | None:
    v = sympy.nsimplify(to_sympy(node))
    if v.has(X):
        return None
    return Fraction(int(v.p), int(v.q))


def _on_sides(eq: Equation, fn) -> list[Candidate]:
    """Apply a node-level transform fn(node) -> [(buggy_node, correct_node)] to every
    sub-node of either side; the rest of the equation is kept as written."""
    out = []
    for side in ("lhs", "rhs"):
        root = getattr(eq, side)
        for target, b, c in _tagged(root, fn):
            b_side, c_side = _replace(root, target, b), _replace(root, target, c)
            if side == "lhs":
                out.append(Candidate(Equation(b_side, eq.rhs), Equation(c_side, eq.rhs)))
            else:
                out.append(Candidate(Equation(eq.lhs, b_side), Equation(eq.lhs, c_side)))
    return out


def _tagged(root: Node, fn):
    """Yield (sub_node, buggy, correct) for every sub-node of root where fn applies."""
    stack = [root]
    while stack:
        n = stack.pop()
        for b, c in fn(n):
            yield n, b, c
        if hasattr(n, "arg"):
            stack.append(n.arg)
        elif isinstance(n, Sum):
            stack.extend(m for _, m in n.items)
        elif isinstance(n, Prod):
            stack.extend(n.factors)
        elif isinstance(n, Div):
            stack.extend([n.num, n.den])


def _replace(node: Node, target: Node, new: Node) -> Node:
    if node is target:
        return new
    if hasattr(node, "arg"):
        return type(node)(_replace(node.arg, target, new))
    if isinstance(node, Sum):
        return Sum(tuple((s, _replace(m, target, new)) for s, m in node.items))
    if isinstance(node, Prod):
        return Prod(tuple(_replace(f, target, new) for f in node.factors))
    if isinstance(node, Div):
        return Div(_replace(node.num, target, new), _replace(node.den, target, new))
    return node


# ---------------- DIST_FIRST_ONLY ----------------

def _dist_partial(node: Node):
    """k(a + b + ...) -> multiply only one term by k (buggy); all terms (correct)."""
    if not isinstance(node, Prod):
        return []
    sums = [i for i, f in enumerate(node.factors) if isinstance(f, Sum)]
    if len(sums) != 1:
        return []
    others = [f for i, f in enumerate(node.factors) if i != sums[0]]
    k = _const(others[0] if len(others) == 1 else Prod(tuple(others)))
    # k = -1: "multiply only the first term by -1" is a sign error -> DIST_SIGN, not this bug
    if k is None or k in (0, 1, -1):
        return []
    inner = node.factors[sums[0]].items
    correct = make_sum([scaled(k, s, n) for s, n in inner])
    out = []
    for i in range(len(inner)):
        buggy = make_sum([scaled(k, s, n) if j == i else (s, n) for j, (s, n) in enumerate(inner)])
        out.append((buggy, correct))
    return out


def dist_first_only(eq: Equation) -> list[Candidate]:
    return _on_sides(eq, _dist_partial)


# ---------------- DIST_SIGN ----------------

def _bracket(node: Node) -> tuple[Fraction, tuple] | None:
    """(k, inner items) if node is k·(a ± b ...) with a constant k, else None."""
    if isinstance(node, Sum):
        return Fraction(1), node.items
    if isinstance(node, Prod):
        sums = [i for i, f in enumerate(node.factors) if isinstance(f, Sum)]
        if len(sums) != 1:
            return None
        others = [f for i, f in enumerate(node.factors) if i != sums[0]]
        k = _const(others[0] if len(others) == 1 else Prod(tuple(others)))
        return (k, node.factors[sums[0]].items) if k not in (None, 0) else None
    return None


def _sign_variants(k: Fraction, inner) -> list[tuple[Node, Node]]:
    """Negative multiplier k: magnitudes are multiplied correctly by |k|, but the minus is
    applied only to a proper subset of the terms (e.g. only the first one, or none)."""
    correct_items = [scaled(k, s, n) for s, n in inner]
    out = []
    for mask in product([True, False], repeat=len(inner)):
        if all(mask):
            continue  # sign applied to every term = correct
        items = [scaled(k if flip else abs(k), s, n) for flip, (s, n) in zip(mask, inner)]
        out.append((make_sum(items), make_sum(correct_items)))
    return out


def _dist_sign(node: Node):
    # -(...) or -k(...): a Neg in front of a bracket
    if hasattr(node, "arg") and not isinstance(node, (Sum, Prod)):
        br = _bracket(node.arg)
        if br and br[0] > 0:
            return _sign_variants(-br[0], br[1])
        return []
    # k(...) with a negative constant k, e.g. (-2)(x - 4)
    if isinstance(node, Prod):
        br = _bracket(node)
        return _sign_variants(br[0], br[1]) if br and br[0] < 0 else []
    # a - (...) or a - k(...): the bracket is an item with a minus inside a sum; expand it
    # in place so the result is a flat sum (5 - 2(x + 3) -> 5 - 2x + 6)
    if isinstance(node, Sum):
        out = []
        for i, (s, n) in enumerate(node.items):
            br = _bracket(n) if s < 0 else None
            if not br or br[0] <= 0:
                continue
            for buggy, correct in _sign_variants(-br[0], br[1]):
                before, after = list(node.items[:i]), list(node.items[i + 1:])
                out.append((make_sum(before + side_items(buggy) + after),
                            make_sum(before + side_items(correct) + after)))
        return out
    return []


def dist_sign(eq: Equation) -> list[Candidate]:
    return _on_sides(eq, _dist_sign)


# ---------------- COMBINE_UNLIKE ----------------

def _simple_term(node: Node) -> tuple[Fraction, bool] | None:
    """(value, is_x_term) for 7, x, 3x (and their Neg); None for anything else."""
    from ..expr import Num, Var
    neg = 1
    if hasattr(node, "arg") and not isinstance(node, (Sum, Prod)):
        node, neg = node.arg, -1
    if isinstance(node, Num):
        return neg * node.value, False
    if isinstance(node, Var):
        return Fraction(neg), True
    if isinstance(node, Prod) and len(node.factors) == 2 and isinstance(node.factors[0], Num) \
            and isinstance(node.factors[1], Var):
        return neg * node.factors[0].value, True
    return None


def combine_unlike(eq: Equation) -> list[Candidate]:
    """An x-term and a number on the same side added as if they were like terms:
    3x + 2 -> 5x (or -> 5). Correct version of the step: the number moved across "="
    (x-terms and numbers stay separate)."""
    out = []
    for side in ("lhs", "rhs"):
        items = side_items(getattr(eq, side))
        other = eq.rhs if side == "lhs" else eq.lhs
        terms = [(i, _simple_term(n), s) for i, (s, n) in enumerate(items)]
        xs = [(i, s * v) for i, t, s in terms if t and t[1] for v in [t[0]]]
        cs = [(i, s * v) for i, t, s in terms if t and not t[1] for v in [t[0]]]
        for (ix, a), (ic, b) in product(xs, cs):
            rest = [it for j, it in enumerate(items) if j not in (ix, ic)]
            total = a + b
            # correct step: the number moves to the other side, nothing is "combined"
            oa, ob = linear_form(other)
            kept = make_sum(rest + [((1 if a > 0 else -1), from_linear(abs(a), 0))])
            correct_side = from_linear(*linear_form(kept))
            correct_other = from_linear(oa, ob - sympy.Rational(b.numerator, b.denominator))
            for merged in (from_linear(total, 0), from_linear(0, total)):   # 5x or 5
                if total == 0:
                    continue
                buggy_side = make_sum(rest + side_items(merged))
                buggy = Equation(buggy_side, other) if side == "lhs" else Equation(other, buggy_side)
                correct = (Equation(correct_side, correct_other) if side == "lhs"
                           else Equation(correct_other, correct_side))
                out.append(Candidate(buggy, correct))
    return out


# ---------------- SIGN_ON_TRANSFER ----------------

MAX_MOVED = 2


def sign_on_transfer(eq: Equation) -> list[Candidate]:
    """Move 1..MAX_MOVED top-level items across '='; at least one keeps its sign (bug)."""
    L, R = side_items(eq.lhs), side_items(eq.rhs)
    tagged = [("L", i) for i in range(len(L))] + [("R", i) for i in range(len(R))]
    out = []
    for k in range(1, MAX_MOVED + 1):
        for moved in combinations(tagged, k):
            for wrong_flags in product([False, True], repeat=k):
                if not any(wrong_flags):
                    continue
                res = {}
                for mode in ("buggy", "correct"):
                    newL = [it for j, it in enumerate(L) if ("L", j) not in moved]
                    newR = [it for j, it in enumerate(R) if ("R", j) not in moved]
                    for (side, j), wrong in zip(moved, wrong_flags):
                        s, n = (L if side == "L" else R)[j]
                        keep = mode == "buggy" and wrong
                        item = (s if keep else -s, n)
                        (newR if side == "L" else newL).append(item)
                    res[mode] = Equation(make_sum(newL), make_sum(newR))
                out.append(Candidate(res["buggy"], res["correct"]))
    return out


# ---------------- DIVIDE_ONE_SIDE ----------------

def divide_one_side(eq: Equation) -> list[Candidate]:
    """Divide only one side by d (bug) vs. both sides (correct).

    Plausibility limits (fewer candidates = fewer accidental matches): x occurs on one
    side only; d is that side's x-coefficient or the constant factor in front of its
    bracket; d not in {0, 1, -1}; the divided side gets integer coefficients.
    """
    sides = [s for s in (eq.lhs, eq.rhs) if x_coeff(s) != 0]
    if len(sides) != 1:
        return []
    side = sides[0]
    a, b = linear_form(side)
    divisors: list[Fraction] = [Fraction(int(a.p), int(a.q))]
    if isinstance(side, Prod):
        divisors += [c for c in (_const(f) for f in side.factors) if c is not None]
    divisors = [d for d in dict.fromkeys(divisors)
                if d not in (0, 1, -1) and (a / sympy.Rational(d.numerator, d.denominator)).is_integer
                and (b / sympy.Rational(d.numerator, d.denominator)).is_integer]
    la, lb = linear_form(eq.lhs)
    ra, rb = linear_form(eq.rhs)
    out = []
    for d in dict.fromkeys(divisors):
        d_s = sympy.Rational(d.numerator, d.denominator)
        left, right = from_linear(la / d_s, lb / d_s), from_linear(ra / d_s, rb / d_s)
        correct = Equation(left, right)
        out.append(Candidate(Equation(left, eq.rhs), correct))
        out.append(Candidate(Equation(eq.lhs, right), correct))
    return out


# ---------------- catalog ----------------

CATALOG: dict[str, Bug] = {}


def _register(bug: Bug) -> None:
    CATALOG[bug.id] = bug


_register(Bug(
    id="DIST_FIRST_ONLY",
    name={
        "ru": "Скобки раскрыты не полностью",
        "en": "Brackets expanded only partially",
    },
    description={
        "ru": "Множитель перед скобкой умножен только на одно слагаемое: k(a+b) → ka + b.",
        "en": "The factor in front of the bracket multiplies only one term: k(a+b) → ka + b.",
    },
    transforms=dist_first_only,
    hints={
        1: {
            "ru": "Когда ты раскрывал скобки, на что ты умножил число перед скобкой? На все слагаемые внутри?",
            "en": "When you expanded the brackets, what did you multiply the number in front by? Every term inside?",
        },
        2: {
            "ru": "Посмотри на раскрытие скобок в этом шаге.",
            "en": "Look at how the brackets were expanded in this step.",
        },
        3: {
            "ru": "Правило: k(a + b) = k·a + k·b. Множитель перед скобкой умножается на каждое слагаемое в скобках.",
            "en": "Rule: k(a + b) = k·a + k·b. The factor in front multiplies every term inside the brackets.",
        },
    },
    transfer_tag="brackets",
))

_register(Bug(
    id="SIGN_ON_TRANSFER",
    name={
        "ru": "Перенос без смены знака",
        "en": "Term moved without changing its sign",
    },
    description={
        "ru": "Слагаемое перенесено в другую часть уравнения, но его знак не изменён.",
        "en": "A term was moved to the other side of the equation but its sign was not changed.",
    },
    transforms=sign_on_transfer,
    hints={
        1: {
            "ru": "Какое слагаемое ты перенёс через знак «=»? Что при этом должно произойти с его знаком?",
            "en": "Which term did you move across the “=” sign? What should happen to its sign?",
        },
        2: {
            "ru": "Посмотри на слагаемые, которые сменили часть уравнения в этом шаге.",
            "en": "Look at the terms that moved to the other side in this step.",
        },
        3: {
            "ru": "Правило: при переносе через «=» знак слагаемого меняется на противоположный. Это то же самое, что вычесть (или прибавить) его в обеих частях.",
            "en": "Rule: a term moved across “=” changes its sign. It is the same as subtracting (or adding) it on both sides.",
        },
    },
    transfer_tag="transfer",
))

_register(Bug(
    id="DIVIDE_ONE_SIDE",
    name={
        "ru": "Деление только одной части",
        "en": "Only one side divided",
    },
    description={
        "ru": "Одна часть уравнения разделена на число, а другая — нет.",
        "en": "One side of the equation was divided by a number, the other was not.",
    },
    transforms=divide_one_side,
    hints={
        1: {
            "ru": "Ты разделил одну часть уравнения. Что стало с другой частью? Сохранится ли равенство?",
            "en": "You divided one side of the equation. What happened to the other side? Does the equality still hold?",
        },
        2: {
            "ru": "Посмотри на деление в этом шаге: обе ли части изменились?",
            "en": "Look at the division in this step: did both sides change?",
        },
        3: {
            "ru": "Правило: обе части уравнения делят на одно и то же ненулевое число.",
            "en": "Rule: both sides of an equation are divided by the same non-zero number.",
        },
    },
    transfer_tag="divide",
))

_register(Bug(
    id="DIST_SIGN",
    name={
        "ru": "Минус перед скобкой не на всех слагаемых",
        "en": "Minus in front of the bracket not applied to every term",
    },
    description={
        "ru": "Знак отрицательного множителя применён не ко всем слагаемым в скобках: -(x - 3) → -x - 3, -2(x - 4) → -2x - 8.",
        "en": "The sign of a negative factor was not applied to every term in the bracket: -(x - 3) → -x - 3, -2(x - 4) → -2x - 8.",
    },
    transforms=dist_sign,
    hints={
        1: {
            "ru": "Перед скобкой стоит минус. Какие знаки должны получиться у каждого слагаемого после раскрытия?",
            "en": "There is a minus in front of the bracket. What sign should each term get after expanding?",
        },
        2: {
            "ru": "Посмотри на знаки слагаемых после раскрытия скобки с минусом.",
            "en": "Look at the signs of the terms after expanding the bracket with a minus.",
        },
        3: {
            "ru": "Правило: -(a - b) = -a + b, а -k(a - b) = -ka + kb. Минус перед скобкой меняет знак каждого слагаемого в скобках.",
            "en": "Rule: -(a - b) = -a + b and -k(a - b) = -ka + kb. A minus in front of a bracket changes the sign of every term inside.",
        },
        4: {
            "ru": "Разберём подробно. Минус перед скобкой меняет знак каждого слагаемого, а не только первого. Верный вариант этого действия: «{prev}» → «{correct}». Дальше продолжи сам.",
            "en": "Let's go through it. A minus in front of a bracket changes the sign of every term, not only the first. The correct version of this step: “{prev}” → “{correct}”. Continue from there yourself.",
        },
    },
    transfer_tag="brackets_neg",
))

_register(Bug(
    id="COMBINE_UNLIKE",
    name={
        "ru": "Сложение неподобных слагаемых",
        "en": "Unlike terms combined",
    },
    description={
        "ru": "Слагаемое с x и число сложены как подобные: 3x + 2 → 5x или 5.",
        "en": "A term with x and a number were added as like terms: 3x + 2 → 5x or 5.",
    },
    transforms=combine_unlike,
    hints={
        1: {
            "ru": "Можно ли сложить слагаемое с x и число, у которого нет x? Чем они отличаются?",
            "en": "Can a term with x and a number without x be added together? How are they different?",
        },
        2: {
            "ru": "Посмотри, какие слагаемые ты сложил в этом шаге: у всех ли есть x?",
            "en": "Look at which terms you added in this step: do all of them contain x?",
        },
        3: {
            "ru": "Правило: складывать можно только подобные слагаемые — x с x, числа с числами. ax + b нельзя записать как (a + b)x.",
            "en": "Rule: only like terms can be added — x with x, numbers with numbers. ax + b cannot be written as (a + b)x.",
        },
        4: {
            "ru": "Разберём подробно. Слагаемое с x и число остаются разными слагаемыми; чтобы избавиться от числа, его переносят в другую часть. Верный следующий шаг: «{prev}» → «{correct}». Дальше продолжи сам.",
            "en": "Let's go through it. A term with x and a number stay separate terms; to get rid of the number, move it to the other side. A correct next step: “{prev}” → “{correct}”. Continue from there yourself.",
        },
    },
    transfer_tag="combine",
))
