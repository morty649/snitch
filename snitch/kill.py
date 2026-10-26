"""Phase 4: for each survivor, have the LLM write a pytest test, then VERIFY it:
  1. it PASSES on the original code, and
  2. it FAILS on the mutated code.
Only tests passing both checks are kept (result.killer_test = code). This is the verify loop.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from .llm import LLM
from .models import Status, MutantResult
from .mutate import apply_mutant
from .prompts import KILL_SYSTEM, KILL_USER
from .runner import copy_repo, run_tests


def _extract_code(reply: str) -> str:
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", reply, re.S)
    if m:
        return m.group(1).strip() + "\n"
    if "def test_" not in reply:
        return ""
    return reply.strip() + "\n"


def _find_example_test(repo: Path) -> str:
    for p in sorted(repo.rglob("test_*.py")):
        if p.name.startswith("test_snitch_") or ".snitch" in p.parts:
            continue
        return "\n".join(p.read_text(encoding="utf-8").splitlines()[:60])
    return ""


def _test_dir(work: Path) -> Path:
    return work / "tests" if (work / "tests").is_dir() else work


def write_killer_tests(llm: LLM, repo: Path, results: list[MutantResult], test_cmd: str, timeout: float,
                       attempts: int = 2) -> int:
    """Return number of survivors that got a verified killer test."""
    made = 0
    example_test = _find_example_test(repo)
    for r in results:
        if r.status != Status.SURVIVED or r.mutant.likely_equivalent:
            continue
        src = (repo / r.mutant.file).read_text(encoding="utf-8")
        line = r.mutant.line
        context = "\n".join(src.splitlines()[max(0, line - 21): line + 20])
        feedback = ""
        for _attempt in range(attempts):
            prompt = KILL_USER.format(example_test=example_test, file=r.mutant.file, context=context,
                                      line=r.mutant.line, original=r.mutant.original, mutated=r.mutant.mutated,
                                      description=r.mutant.description) + feedback
            try:
                code = _extract_code(llm.complete(KILL_SYSTEM, prompt, temperature=0.2))
            except RuntimeError:
                continue  # API error -> failed attempt, never crash
            if "def test_" not in code:
                feedback = "\n\nYour reply had no pytest test function. Try again."
                continue
            test_name = f"test_snitch_{r.mutant.id}.py"

            # (a) must PASS on ORIGINAL code (SURVIVED from run_tests means all tests passed)
            work = copy_repo(repo)
            try:
                (_test_dir(work) / test_name).write_text(code, encoding="utf-8")
                st_orig, out_orig, _ = run_tests(work, test_cmd, timeout)
            finally:
                shutil.rmtree(work.parent, ignore_errors=True)
            if st_orig != Status.SURVIVED:
                feedback = f"\n\nYour test FAILED on the correct code. Output:\n{out_orig[-1500:]}\nFix it."
                continue

            # (b) must FAIL on MUTATED code
            work = copy_repo(repo)
            try:
                (_test_dir(work) / test_name).write_text(code, encoding="utf-8")
                f = work / r.mutant.file
                try:
                    f.write_text(apply_mutant(f.read_text(encoding="utf-8"), r.mutant), encoding="utf-8")
                except ValueError:
                    break  # mutant no longer applies -> give up on this one
                st_mut, _out_mut, _ = run_tests(work, test_cmd, timeout)
            finally:
                shutil.rmtree(work.parent, ignore_errors=True)
            if st_mut == Status.KILLED:
                r.killer_test = code
                made += 1
                break
            feedback = "\n\nYour test PASSED on the buggy code, so it doesn't catch the bug. Make it check the exact edge case."
    return made
