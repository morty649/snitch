"""Phase 3: flag survivors that are probably *equivalent mutants* (changes no input can detect),
so they don't unfairly lower the score.
"""
from __future__ import annotations

from pathlib import Path

from .llm import LLM, extract_json
from .models import MutantResult, Status
from .prompts import EQUIV_SYSTEM, EQUIV_USER


def flag_equivalents(llm: LLM, repo: Path, results: list[MutantResult]) -> int:
    """For each SURVIVED result, ask the LLM (prompts.EQUIV_*) whether the change is equivalent.
    Set result.mutant.likely_equivalent = True when the model says equivalent=true.
    Only look at SURVIVED results. Return how many were flagged.
    """
    count = 0
    for r in results:
        if r.status != Status.SURVIVED:
            continue
        source = (repo / r.mutant.file).read_text(encoding="utf-8")
        line = r.mutant.line
        context = "\n".join(source.splitlines()[max(0, line - 16): line + 15])
        try:
            reply = llm.complete(EQUIV_SYSTEM, EQUIV_USER.format(context=context, line=r.mutant.line,
                                                                 original=r.mutant.original, mutated=r.mutant.mutated),
                                 temperature=0.0)
            data = extract_json(reply)
        except (ValueError, RuntimeError):
            continue                           # API error or unsure -> NOT equivalent (be conservative), never crash
        if isinstance(data, dict) and data.get("equivalent") is True:
            r.mutant.likely_equivalent = True
            count += 1
    return count
