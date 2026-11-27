"""Parse a student's text step (e.g. "2x+3=14", "2(x+3) = 14") into a SymPy Eq.

Supports implicit multiplication and parentheses. Raises ParseError with a
user-readable message key (i18n) on invalid input. No LLM here.
"""
