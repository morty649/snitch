"""Core data types. Every other module passes these around.

DO NOT rename fields: report.py, the JSON report and the tests depend on them.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum


class Status(str, Enum):
    KILLED = "killed"        # tests failed on the mutant -> tests caught the bug (good)
    SURVIVED = "survived"    # tests passed on the mutant -> bug slipped through (bad)
    TIMEOUT = "timeout"      # tests hung; usually counts as killed-ish, reported separately
    ERROR = "error"          # pytest crashed / could not run (not counted in the score)
    INVALID = "invalid"      # mutant could not be applied or is not valid Python


@dataclass
class Mutant:
    """A single-line code change that plants a realistic bug.

    `line` is 1-based. `original` must equal the current text of that line
    (whitespace-stripped comparison). `mutated` is the full replacement line
    (indentation is restored automatically when applied).
    """
    id: str
    file: str            # path relative to the repo root, forward slashes
    line: int
    original: str
    mutated: str
    description: str = ""
    category: str = "other"
    likely_equivalent: bool = False   # set by equiv.py (Phase 3)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MutantResult:
    mutant: Mutant
    status: Status
    duration_s: float = 0.0
    output_tail: str = ""             # last lines of pytest output, for debugging
    killer_test: str | None = None    # set by kill.py (Phase 4) when a verified killer test exists

    def to_dict(self) -> dict:
        d = {
            "mutant": self.mutant.to_dict(),
            "status": self.status.value,
            "duration_s": round(self.duration_s, 2),
            "output_tail": self.output_tail,
            "killer_test": self.killer_test,
        }
        return d


@dataclass
class Report:
    repo: str
    base: str | None
    results: list[MutantResult] = field(default_factory=list)
    model: str = ""

    def counted(self) -> list[MutantResult]:
        """Results that count toward the score: killed / survived / timeout, excluding likely-equivalent survivors."""
        out = []
        for r in self.results:
            if r.status in (Status.KILLED, Status.TIMEOUT):
                out.append(r)
            elif r.status == Status.SURVIVED and not r.mutant.likely_equivalent:
                out.append(r)
        return out

    def survivors(self) -> list[MutantResult]:
        return [r for r in self.results if r.status == Status.SURVIVED and not r.mutant.likely_equivalent]

    def trust_score(self) -> float | None:
        """Fraction of (non-equivalent) realistic bugs the tests caught. None if nothing counted."""
        c = self.counted()
        if not c:
            return None
        caught = sum(1 for r in c if r.status in (Status.KILLED, Status.TIMEOUT))
        return caught / len(c)

    def to_dict(self) -> dict:
        score = self.trust_score()
        return {
            "repo": self.repo,
            "base": self.base,
            "model": self.model,
            "trust_score": None if score is None else round(score, 4),
            "counts": {s.value: sum(1 for r in self.results if r.status == s) for s in Status},
            "likely_equivalent": sum(1 for r in self.results if r.mutant.likely_equivalent),
            "results": [r.to_dict() for r in self.results],
        }
