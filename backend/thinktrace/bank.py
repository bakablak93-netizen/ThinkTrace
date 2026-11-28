"""Problem bank: 15 linear equations for grades 8-9 in three levels, each with a twin.

  A  ax + b = c
  B  brackets, x on one side
  C  x on both sides, brackets, negative factors; C5 has a fractional solution

Every main problem has a twin (role "twin") with the same structure and difficulty but
other numbers and another solution: used as the final problem without hints (and as a
pre/post-test pair). Tags = typical errors (bug ids from the catalog) for this problem.

The data is written by the team and VERIFIED by the deterministic core in tests
(SymPy: unique solution equal to `solution`, twins with the same structure). The LLM never
creates problems or answers. No root is 0: with x = 0 some wrong steps keep the solution
set and would be accepted as correct.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

Level = Literal["A", "B", "C"]
LEVELS: tuple[Level, ...] = ("A", "B", "C")
DEFAULT_ID = "B1"      # 2(x + 3) = 14: the start problem used so far


@dataclass(frozen=True)
class BankProblem:
    id: str
    text: str
    solution: str          # e.g. "x = 4" or "x = 4/3"
    level: Level
    tags: tuple[str, ...]  # typical errors (catalog bug ids)
    twin_id: str
    role: Literal["main", "twin"] = "main"

    @property
    def root(self) -> Fraction:
        return Fraction(self.solution.split("=")[1].strip())


_A = ("SIGN_ON_TRANSFER", "COMBINE_UNLIKE", "DIVIDE_ONE_SIDE")
_B = ("DIST_FIRST_ONLY", "SIGN_ON_TRANSFER", "DIVIDE_ONE_SIDE")
_B_NEG = ("DIST_SIGN", "SIGN_ON_TRANSFER", "DIVIDE_ONE_SIDE")
_C = ("DIST_FIRST_ONLY", "SIGN_ON_TRANSFER", "DIVIDE_ONE_SIDE")
_C_NEG = ("DIST_SIGN", "SIGN_ON_TRANSFER", "DIVIDE_ONE_SIDE")
_C_MINUS = ("DIST_SIGN", "SIGN_ON_TRANSFER", "COMBINE_UNLIKE")
_C_FRAC = ("DIST_FIRST_ONLY", "DIST_SIGN", "SIGN_ON_TRANSFER", "DIVIDE_ONE_SIDE")

# (id, text, solution, tags, twin text, twin solution)
_DATA: list[tuple[str, str, str, tuple[str, ...], str, str]] = [
    ("A1", "3x + 5 = 20", "x = 5", _A, "4x + 7 = 31", "x = 6"),
    ("A2", "5x - 4 = 21", "x = 5", _A, "6x - 5 = 31", "x = 6"),
    ("A3", "-2x + 7 = 1", "x = 3", _A, "-3x + 8 = 2", "x = 2"),
    ("A4", "7x + 12 = -2", "x = -2", _A, "6x + 15 = -3", "x = -3"),
    ("A5", "-4x - 9 = 11", "x = -5", _A, "-5x - 8 = 12", "x = -4"),
    ("B1", "2(x + 3) = 14", "x = 4", _B, "3(x + 2) = 21", "x = 5"),
    ("B2", "4(x - 2) = 12", "x = 5", _B, "5(x - 3) = 15", "x = 6"),
    ("B3", "3(2x + 1) = 27", "x = 4", _B, "4(2x + 1) = 44", "x = 5"),
    ("B4", "5(x + 1) - 7 = 18", "x = 4", _B, "3(x + 4) - 5 = 16", "x = 3"),
    ("B5", "-2(x - 4) = 6", "x = 1", _B_NEG, "-3(x - 5) = 9", "x = 2"),
    ("C1", "3(x + 2) = x + 14", "x = 4", _C, "4(x + 1) = x + 19", "x = 5"),
    ("C2", "2(x - 5) = 5x + 2", "x = -4", _C, "3(x - 4) = 6x + 3", "x = -5"),
    ("C3", "-2(x + 1) = x - 11", "x = 3", _C_NEG, "-3(x + 2) = x - 14", "x = 2"),
    ("C4", "7 - (x - 3) = 3x + 2", "x = 2", _C_MINUS, "9 - (x - 4) = 2x + 1", "x = 4"),
    ("C5", "2(x + 1) = -(x - 6)", "x = 4/3", _C_FRAC, "3(x + 1) = -(x - 8)", "x = 5/4"),
]


def _build() -> dict[str, BankProblem]:
    out: dict[str, BankProblem] = {}
    for pid, text, sol, tags, ttext, tsol in _DATA:
        tid = f"{pid}T"
        level: Level = pid[0]  # type: ignore[assignment]
        out[pid] = BankProblem(pid, text, sol, level, tags, tid, "main")
        out[tid] = BankProblem(tid, ttext, tsol, level, tags, pid, "twin")
    return out


BANK: dict[str, BankProblem] = _build()


def main_problems(level: Level | None = None) -> list[BankProblem]:
    return [p for p in BANK.values() if p.role == "main" and (level is None or p.level == level)]


def next_problem(level: Level, after_id: str | None = None) -> BankProblem:
    """The next main problem of this level after `after_id` (cyclic); the first one if None."""
    items = main_problems(level)
    ids = [p.id for p in items]
    if after_id in ids:
        return items[(ids.index(after_id) + 1) % len(items)]
    return items[0]


def twin_of(pid: str) -> BankProblem:
    return BANK[BANK[pid].twin_id]
