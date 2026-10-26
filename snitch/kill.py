"""Phase 4: for each survivor, have the LLM write a pytest test, then VERIFY it:
  1. it PASSES on the original code, and
  2. it FAILS on the mutated code.
Only tests passing both checks are kept (result.killer_test = code). This is the verify loop.

STATUS: stub. See PLAN.md Phase 4. Must keep this signature.
"""
from __future__ import annotations

from pathlib import Path

from .llm import LLM
from .models import MutantResult


def write_killer_tests(llm: LLM, repo: Path, results: list[MutantResult], test_cmd: str, timeout: float,
                       attempts: int = 2) -> int:
    """Return number of survivors that got a verified killer test.

    TODO(Phase 4): implement. Until then, writes nothing.
    """
    return 0
