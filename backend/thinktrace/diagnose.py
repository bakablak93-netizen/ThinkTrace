"""Diagnose a non-equivalent step against the bug catalog. No LLM in the decision.

Algorithm (call only when verifier.equivalent(prev, step) is False):
  1. For every bug in the catalog, generate all candidates buggy_transform(prev).
  2. EXACT match: each side of the student's step equals the matching side of a candidate
     after expansion (either orientation). Covers "bug + simplifying within a side".
  3. If no exact match -- SOLUTION match: the student's step has the same unique root
     as a candidate. Covers "bug + further correct steps in one line" (e.g. 2(x+3)=14 ->
     2x=11). Weaker evidence: different bugs may give the same root by coincidence.
  4. Nothing matched -> UNKNOWN (stage 2: optional LLM analysis, never a verdict).

Confidence is a heuristic weight, NOT a calibrated probability:
  EXACT_CONF / n or SOLUTION_CONF / n, where n = number of distinct bug ids matched at
  that level. Real accuracy is measured in eval/ (stage 3).

Pattern (one-off slip vs. repeated error) is a heuristic too: "repeated" if any matched
bug id already occurred earlier in this session, otherwise "first". A single error never
means a lack of understanding.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal

from .bugs.catalog import CATALOG
from .expr import Equation, linear_form
from .verifier import unique_root

EXACT_CONF = 0.9
SOLUTION_CONF = 0.5

UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class BugMatch:
    bug_id: str
    confidence: float
    level: Literal["exact", "solution"]
    correct: Equation  # correct version of the same action (for hint level 4)


@dataclass(frozen=True)
class Diagnosis:
    matches: tuple[BugMatch, ...] = ()
    pattern: Literal["first", "repeated"] | None = None
    extra: dict = field(default_factory=dict)

    @property
    def bug_ids(self) -> list[str]:
        return [m.bug_id for m in self.matches] or [UNKNOWN]

    @property
    def is_unknown(self) -> bool:
        return not self.matches

    @property
    def is_ambiguous(self) -> bool:
        return len(self.matches) > 1


def _sides(eq: Equation):
    return linear_form(eq.lhs), linear_form(eq.rhs)


def _same_solutions(s1, s2) -> bool:
    """Linear equations given by side forms ((a,b),(c,d)) have the same solution set."""
    (a1, b1), (c1, d1) = s1
    (a2, b2), (c2, d2) = s2
    u, v = (a1 - c1, b1 - d1), (a2 - c2, b2 - d2)
    if (u == (0, 0)) != (v == (0, 0)):
        return False
    return u[0] * v[1] == u[1] * v[0]


def diagnose(prev: Equation, step: Equation, history: Iterable[str] = ()) -> Diagnosis:
    student_sides = _sides(step)
    student_root = unique_root(step)
    prev_sides = _sides(prev)

    exact: dict[str, Equation] = {}
    solution: dict[str, Equation] = {}
    for bug_id, bug in CATALOG.items():
        for cand in bug.transforms(prev):
            cand_sides = _sides(cand.buggy)
            if _same_solutions(cand_sides, prev_sides):
                continue  # e.g. moving every term without changing signs = swapping sides
            l, r = cand_sides
            if bug_id not in exact and student_sides in ((l, r), (r, l)):
                exact[bug_id] = cand.correct
            elif (
                bug_id not in solution
                and student_root is not None
                and unique_root(cand.buggy) == student_root
            ):
                solution[bug_id] = cand.correct

    if exact:
        found, level, conf = exact, "exact", EXACT_CONF
    elif solution:
        found, level, conf = solution, "solution", SOLUTION_CONF
    else:
        return Diagnosis()

    n = len(found)
    matches = tuple(
        BugMatch(bug_id, round(conf / n, 3), level, correct) for bug_id, correct in found.items()
    )
    seen = set(history)
    pattern = "repeated" if any(m.bug_id in seen for m in matches) else "first"
    return Diagnosis(matches, pattern)
