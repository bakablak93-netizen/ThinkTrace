"""Step verification (SymPy). No LLM here.

equivalent(prev, new): True if `new` has the same solution set over the reals as `prev`.
is_solved(eq): True if eq is written as x = <number> (or <number> = x), where the number
is an integer, a decimal, or a reduced fraction p/q -- i.e. nothing left to compute.
"""
from __future__ import annotations

from math import gcd

import sympy

from .expr import X, Div, Equation, Neg, Node, Num, Var, to_sympy


def solution_set(eq: Equation) -> sympy.Set:
    return sympy.solveset(sympy.expand(to_sympy(eq.lhs) - to_sympy(eq.rhs)), X, sympy.S.Reals)


def unique_root(eq: Equation) -> sympy.Rational | None:
    s = solution_set(eq)
    if isinstance(s, sympy.FiniteSet) and len(s) == 1:
        return next(iter(s))
    return None


def equivalent(prev: Equation, new: Equation) -> bool:
    return solution_set(prev) == solution_set(new)


def _is_number_literal(node: Node) -> bool:
    if isinstance(node, Neg):
        return _is_number_literal(node.arg)
    if isinstance(node, Num):
        return True
    if isinstance(node, Div) and isinstance(node.num, Num) and isinstance(node.den, Num):
        a, b = node.num.value, node.den.value
        if a.denominator != 1 or b.denominator != 1 or b == 1:
            return False
        return gcd(int(a), int(b)) == 1 and b > 0
    return False


def is_solved(eq: Equation) -> bool:
    return (isinstance(eq.lhs, Var) and _is_number_literal(eq.rhs)) or (
        isinstance(eq.rhs, Var) and _is_number_literal(eq.lhs)
    )

