"""Parse a student's text step (e.g. "2x+3=14", "2(x+3) = 14") into an Equation tree.

Own recursive-descent parser instead of sympy.parse_expr:
  * parse_expr uses eval() on input -- not acceptable for text typed by strangers;
  * it loses the written structure (-(x+3) is auto-distributed, terms reordered),
    which the bug diagnosis depends on.

Supports: integers/decimals, x, + - * /, brackets, implicit multiplication (2x, 2(x+1),
x(x+1) is rejected as non-linear). Only linear equations in x are accepted.
Errors are raised as ParseError(code, **params); codes map to i18n messages.

Grammar:
  equation := expr '=' expr
  expr     := ['+'|'-'] term (('+'|'-') term)*
  term     := unary (('*'|'/') unary | <implicit> unary)*   implicit before 'x' or '('
  unary    := ('-'|'+') unary | atom
  atom     := NUMBER | 'x' | '(' expr ')'
"""
from __future__ import annotations

import re
from fractions import Fraction

import sympy

from .expr import X, Div, Equation, Neg, Node, Num, Prod, Sum, Var, make_sum, to_sympy  # noqa: F401

MAX_LEN = 80
MAX_DIGITS = 6

_NORMALIZE = {
    "−": "-", "–": "-", "—": "-",
    "×": "*", "·": "*", "∙": "*", "⋅": "*",
    "÷": "/", ":": "/",
    ",": ".", "X": "x", "х": "x", "Х": "x",  # Cyrillic kha typed by mistake
}
_ALLOWED = set("0123456789.x+-*/()=")


class ParseError(ValueError):
    def __init__(self, code: str, **params):
        super().__init__(code)
        self.code = code
        self.params = params


def normalize(text: str) -> str:
    out = "".join(_NORMALIZE.get(ch, ch) for ch in text)
    return re.sub(r"\s+", "", out)


def _tokenize(s: str) -> list[tuple[str, str]]:
    tokens = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch.isdigit() or ch == ".":
            m = re.match(r"\d+(\.\d+)?|\.\d+", s[i:])
            if not m:
                raise ParseError("bad_number", pos=i)
            digits = m.group(0).replace(".", "")
            if len(digits) > MAX_DIGITS:
                raise ParseError("bad_number", pos=i)
            tokens.append(("NUM", m.group(0)))
            i += len(m.group(0))
            continue
        if ch not in _ALLOWED:
            raise ParseError("bad_char", char=ch)
        kind = {"x": "X", "(": "LP", ")": "RP", "=": "EQ"}.get(ch, "OP")
        tokens.append((kind, ch))
        i += 1
    return tokens


class _Parser:
    def __init__(self, tokens):
        self.t = tokens
        self.i = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else ("EOF", "")

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def expr(self) -> Node:
        items: list[tuple[int, Node]] = []
        sign = 1
        if self.peek() in (("OP", "-"), ("OP", "+")):
            sign = -1 if self.take()[1] == "-" else 1
        items.append((sign, self.term()))
        while self.peek() in (("OP", "-"), ("OP", "+")):
            sign = -1 if self.take()[1] == "-" else 1
            items.append((sign, self.term()))
        return make_sum(items)

    def term(self) -> Node:
        factors = [self.unary()]
        while True:
            kind, val = self.peek()
            if (kind, val) == ("OP", "*"):
                self.take()
                factors.append(self.unary())
            elif (kind, val) == ("OP", "/"):
                self.take()
                left = factors[0] if len(factors) == 1 else Prod(tuple(factors))
                factors = [Div(left, self.unary())]
            elif kind in ("X", "LP"):
                factors.append(self.unary())
            else:
                break
        return factors[0] if len(factors) == 1 else Prod(tuple(factors))

    def unary(self) -> Node:
        if self.peek() == ("OP", "-"):
            self.take()
            return Neg(self.unary())
        if self.peek() == ("OP", "+"):
            self.take()
            return self.unary()
        return self.atom()

    def atom(self) -> Node:
        kind, val = self.take()
        if kind == "NUM":
            return Num(Fraction(val))
        if kind == "X":
            return Var()
        if kind == "LP":
            inner = self.expr()
            if self.take()[0] != "RP":
                raise ParseError("unbalanced")
            return inner
        if kind == "RP":
            raise ParseError("unbalanced")
        if kind == "EOF":
            raise ParseError("incomplete")
        raise ParseError("unexpected", char=val)


def _check_divisions(node: Node) -> None:
    """Denominators must be non-zero constants."""
    if isinstance(node, Div):
        den = to_sympy(node.den)
        if den.has(X):
            raise ParseError("not_linear")
        if den == 0:
            raise ParseError("div_zero")
        _check_divisions(node.num)
        _check_divisions(node.den)
    elif isinstance(node, Neg):
        _check_divisions(node.arg)
    elif isinstance(node, Sum):
        for _, n in node.items:
            _check_divisions(n)
    elif isinstance(node, Prod):
        for f in node.factors:
            _check_divisions(f)


def parse_side(text: str) -> Node:
    tokens = _tokenize(text)
    if not tokens:
        raise ParseError("empty_side")
    p = _Parser(tokens)
    node = p.expr()
    if p.peek()[0] != "EOF":
        kind, val = p.peek()
        raise ParseError("unbalanced" if kind == "RP" else "unexpected", char=val)
    return node


def parse_equation(text: str) -> Equation:
    s = normalize(text or "")
    if not s:
        raise ParseError("empty")
    if len(s) > MAX_LEN:
        raise ParseError("too_long", max=MAX_LEN)
    _tokenize(s)  # report bad characters before structural problems
    parts = s.split("=")
    if len(parts) == 1:
        raise ParseError("no_equals")
    if len(parts) > 2:
        raise ParseError("many_equals")
    if not parts[0] or not parts[1]:
        raise ParseError("empty_side")
    eq = Equation(parse_side(parts[0]), parse_side(parts[1]))
    for side in (eq.lhs, eq.rhs):
        _check_divisions(side)
        e = sympy.expand(to_sympy(side))
        if not e.is_polynomial(X) or sympy.degree(e, X) > 1:
            raise ParseError("not_linear")
    return eq
