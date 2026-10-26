"""Phase 3: flag survivors that are probably *equivalent mutants* (changes no input can detect),
so they don't unfairly lower the score.

STATUS: stub. See PLAN.md Phase 3. Must keep this signature.
"""
from __future__ import annotations

from pathlib import Path

from .llm import LLM
from .models import MutantResult, Status


def flag_equivalents(llm: LLM, repo: Path, results: list[MutantResult]) -> int:
    """For each SURVIVED result, ask the LLM (prompts.EQUIV_*) whether the change is equivalent.
    Set result.mutant.likely_equivalent = True when the model says equivalent=true.
    Only look at SURVIVED results. Return how many were flagged.

    TODO(Phase 3): implement. Until then, flags nothing.
    """
    _ = [r for r in results if r.status == Status.SURVIVED]
    return 0
