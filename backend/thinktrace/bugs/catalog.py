"""Catalog of typical errors (bugs) in solving linear equations.

Each Bug has:
  id, name / description (ru/kk/en), hints for levels 1-3 (ru/kk/en), transfer_tag (which problem family checks understanding of this bug), and
  transforms(prev_eq) -> list[Candidate]: every way this error could be applied to the
  previous step. Each Candidate carries the buggy result AND the correct version of the
  same action (shown only on hint level 4).

kk texts: added in stage 2 (missing keys fall back to ru).
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
    if k is None or k in (0, 1):
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
