"""Structure-preserving expression tree for linear equations in x.

We keep exactly what the student wrote (brackets, order of terms, written minus signs),
because diagnosis needs that structure: SymPy's own parser auto-distributes -(x+3) and
reorders terms even with evaluate=False. All math (expansion, solving) goes through SymPy
via `to_sympy`.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Iterator

import sympy

X = sympy.Symbol("x")


class Node:
    pass


@dataclass(frozen=True)
class Num(Node):
    value: Fraction


@dataclass(frozen=True)
class Var(Node):
    pass


@dataclass(frozen=True)
class Neg(Node):
    """Unary minus applied to a whole node, e.g. -(x+3) or a leading -2x."""
    arg: Node


@dataclass(frozen=True)
class Sum(Node):
    """Two or more items; each item is (sign, node) with sign +1 or -1 as written."""
    items: tuple[tuple[int, Node], ...]


@dataclass(frozen=True)
class Prod(Node):
    factors: tuple[Node, ...]


@dataclass(frozen=True)
class Div(Node):
    num: Node
    den: Node


@dataclass(frozen=True)
class Equation:
    lhs: Node
    rhs: Node


# ---------- construction helpers ----------

def num(v: int | Fraction) -> Num:
    return Num(Fraction(v))


def make_sum(items: list[tuple[int, Node]]) -> Node:
    """Build a Sum, collapsing trivial cases (1 item -> node or Neg(node), 0 -> 0)."""
    if not items:
        return num(0)
    if len(items) == 1:
        sign, node = items[0]
        return node if sign > 0 else Neg(node)
    return Sum(tuple(items))


def side_items(node: Node) -> list[tuple[int, Node]]:
    """Top-level additive items of a side, as written."""
    if isinstance(node, Sum):
        return list(node.items)
    if isinstance(node, Neg):
        return [(-1, node.arg)]
    return [(1, node)]


# ---------- math via SymPy ----------

def to_sympy(node: Node) -> sympy.Expr:
    if isinstance(node, Num):
        return sympy.Rational(node.value.numerator, node.value.denominator)
    if isinstance(node, Var):
        return X
    if isinstance(node, Neg):
        return -to_sympy(node.arg)
    if isinstance(node, Sum):
        return sympy.Add(*[s * to_sympy(n) for s, n in node.items])
    if isinstance(node, Prod):
        return sympy.Mul(*[to_sympy(f) for f in node.factors])
    if isinstance(node, Div):
        return to_sympy(node.num) / to_sympy(node.den)
    raise TypeError(node)


def linear_form(node: Node) -> tuple[sympy.Rational, sympy.Rational]:
    """(a, b) such that node == a*x + b. Assumes the node is linear (parser checks this)."""
    e = sympy.expand(to_sympy(node))
    return sympy.Rational(e.coeff(X, 1)), sympy.Rational(e.coeff(X, 0))


def x_coeff(node: Node) -> sympy.Rational:
    return linear_form(node)[0]


# ---------- tree rewriting ----------

def rewrites(node: Node, fn: Callable[[Node], Iterator[Node]]) -> Iterator[Node]:
    """Yield copies of `node` where exactly one sub-node n is replaced by each value of fn(n)."""
    yield from fn(node)
    if isinstance(node, Neg):
        for a in rewrites(node.arg, fn):
            yield Neg(a)
    elif isinstance(node, Sum):
        for i, (s, n) in enumerate(node.items):
            for r in rewrites(n, fn):
                items = list(node.items)
                items[i] = (s, r)
                yield Sum(tuple(items))
    elif isinstance(node, Prod):
        for i, f in enumerate(node.factors):
            for r in rewrites(f, fn):
                fs = list(node.factors)
                fs[i] = r
                yield Prod(tuple(fs))
    elif isinstance(node, Div):
        for r in rewrites(node.num, fn):
            yield Div(r, node.den)
        for r in rewrites(node.den, fn):
            yield Div(node.num, r)


# ---------- printing ----------

def _frac_text(v: Fraction) -> str:
    return str(v.numerator) if v.denominator == 1 else f"{v.numerator}/{v.denominator}"


def to_text(node: Node) -> str:
    if isinstance(node, Num):
        return _frac_text(node.value)
    if isinstance(node, Var):
        return "x"
    if isinstance(node, Neg):
        inner = to_text(node.arg)
        return f"-({inner})" if isinstance(node.arg, Sum) else f"-{inner}"
    if isinstance(node, Sum):
        out = ""
        for i, (s, n) in enumerate(node.items):
            t = to_text(n)
            if isinstance(n, (Sum, Neg)):
                t = f"({t})"
            if i == 0:
                out = t if s > 0 else f"-{t}"
            else:
                out += (" + " if s > 0 else " - ") + t
        return out
    if isinstance(node, Prod):
        parts = []
        for i, f in enumerate(node.factors):
            t = to_text(f)
            if isinstance(f, (Sum, Div)) or (isinstance(f, Neg) and i > 0) or (
                isinstance(f, Num) and f.value.denominator != 1
            ):
                t = f"({t})"
            if parts and isinstance(f, Num):
                parts.append("*")
            parts.append(t)
        return "".join(parts)
    if isinstance(node, Div):
        a, b = to_text(node.num), to_text(node.den)
        if isinstance(node.num, (Sum, Neg)):
            a = f"({a})"
        if not isinstance(node.den, (Num, Var)):
            b = f"({b})"
        return f"{a}/{b}"
    raise TypeError(node)


def eq_text(eq: Equation) -> str:
    return f"{to_text(eq.lhs)} = {to_text(eq.rhs)}"


def to_latex(node: Node) -> str:
    if isinstance(node, Num):
        v = node.value
        return str(v.numerator) if v.denominator == 1 else rf"\frac{{{v.numerator}}}{{{v.denominator}}}"
    if isinstance(node, Var):
        return "x"
    if isinstance(node, Neg):
        inner = to_latex(node.arg)
        return rf"-\left({inner}\right)" if isinstance(node.arg, Sum) else f"-{inner}"
    if isinstance(node, Sum):
        out = ""
        for i, (s, n) in enumerate(node.items):
            t = to_latex(n)
            if isinstance(n, (Sum, Neg)):
                t = rf"\left({t}\right)"
            out += (t if s > 0 else f"-{t}") if i == 0 else ((" + " if s > 0 else " - ") + t)
        return out
    if isinstance(node, Prod):
        parts = []
        for i, f in enumerate(node.factors):
            t = to_latex(f)
            if isinstance(f, Sum) or (isinstance(f, Neg) and i > 0):
                t = rf"\left({t}\right)"
            if parts and isinstance(f, Num):
                parts.append(r" \cdot ")
            parts.append(t)
        return "".join(parts)
    if isinstance(node, Div):
        return rf"\frac{{{to_latex(node.num)}}}{{{to_latex(node.den)}}}"
    raise TypeError(node)


def eq_latex(eq: Equation) -> str:
    return f"{to_latex(eq.lhs)} = {to_latex(eq.rhs)}"


def from_linear(a, b) -> Node:
    """Readable node for a*x + b with rational a, b (used to display correct steps)."""
    a, b = Fraction(str(a)), Fraction(str(b))
    items: list[tuple[int, Node]] = []
    if a != 0:
        xa = Var() if abs(a) == 1 else Prod((Num(abs(a)), Var()))
        items.append((1 if a > 0 else -1, xa))
    if b != 0 or not items:
        items.append((1 if b >= 0 else -1, Num(abs(b))))
    return make_sum(items)


def scaled(k: Fraction, sign: int, node: Node) -> tuple[int, Node]:
    """Return (sign, node) for k * (sign * node), merging k into a leading number."""
    k = Fraction(k) * sign
    s = 1 if k > 0 else -1
    k = abs(k)
    if isinstance(node, Num):
        return s, Num(k * node.value)
    if isinstance(node, Prod) and isinstance(node.factors[0], Num):
        return s, Prod((Num(k * node.factors[0].value),) + node.factors[1:])
    if k == 1:
        return s, node
    return s, Prod((Num(k), node))
