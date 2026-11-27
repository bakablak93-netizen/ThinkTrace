import pytest

from thinktrace.expr import eq_text
from thinktrace.parser import ParseError, parse_equation


@pytest.mark.parametrize("text, expected", [
    ("2(x+3)=14", "2(x + 3) = 14"),
    ("2x+3=14", "2x + 3 = 14"),
    ("-(x+3)=5", "-(x + 3) = 5"),
    ("5-2(x+3)=1", "5 - 2(x + 3) = 1"),
    ("x/2+1=3", "x/2 + 1 = 3"),
    ("2 · (x − 1) = 6", "2(x - 1) = 6"),     # unicode operators
    ("3,5x = 7", "(7/2)x = 7"),              # decimal comma
    ("2Х+1=5", "2x + 1 = 5"),                # Cyrillic Х typed instead of x
    ("7/2 = x", "7/2 = x"),
])
def test_parse_keeps_written_structure(text, expected):
    assert eq_text(parse_equation(text)) == expected


@pytest.mark.parametrize("text, code", [
    ("", "empty"),
    ("abc", "bad_char"),
    ("2y=4", "bad_char"),
    ("2x+3", "no_equals"),
    ("x=1=2", "many_equals"),
    ("2x=", "empty_side"),
    ("((x)=1", "unbalanced"),
    ("x)=1", "unbalanced"),
    ("x+=1", "incomplete"),
    ("x(x+1)=2", "not_linear"),
    ("x/x=1", "not_linear"),
    ("x/0=1", "div_zero"),
    ("1234567x=1", "bad_number"),
    ("x=" + "1+" * 50 + "1", "too_long"),
    ("__import__('os')=1", "bad_char"),
])
def test_parse_errors(text, code):
    with pytest.raises(ParseError) as e:
        parse_equation(text)
    assert e.value.code == code
