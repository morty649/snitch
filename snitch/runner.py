"""Run the test suite against each mutant in an isolated temp copy of the repo.

Never mutates the user's real files. Each mutant gets its own copy (fast for small repos;
see PLAN.md 'Known limits' for big repos).
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .models import Mutant, MutantResult, Status
from .mutate import apply_mutant

IGNORE = shutil.ignore_patterns(".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", ".snitch", "*.egg-info")
DEFAULT_TEST_CMD = f"{shlex.quote(sys.executable)} -m pytest -q -x -p no:cacheprovider"


def copy_repo(repo: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="snitch-"))
    dst = tmp / "repo"
    shutil.copytree(repo, dst, ignore=IGNORE)
    return dst


def run_tests(workdir: Path, test_cmd: str = DEFAULT_TEST_CMD, timeout: float = 60.0) -> tuple[Status, str, float]:
    env = dict(os.environ)
    # Put the MUTATED copy first on the path (and its src/ for src-layout repos), so tests import
    # the mutant and not an installed/editable copy of the original package.
    paths = [str(workdir)] + ([str(workdir / "src")] if (workdir / "src").is_dir() else [])
    env["PYTHONPATH"] = os.pathsep.join(paths + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    start = time.time()
    try:
        proc = subprocess.run(shlex.split(test_cmd), cwd=workdir, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return Status.TIMEOUT, "timed out", time.time() - start
    dur = time.time() - start
    out = (proc.stdout + "\n" + proc.stderr).strip()
    tail = "\n".join(out.splitlines()[-15:])
    # pytest exit codes: 0 all passed, 1 some failed, 2 interrupted (e.g. import/collection error),
    # 3 internal error, 4 usage error, 5 no tests collected
    if proc.returncode == 0:
        return Status.SURVIVED, tail, dur
    if proc.returncode in (1, 2):
        return Status.KILLED, tail, dur
    return Status.ERROR, tail, dur


def baseline(repo: Path, test_cmd: str = DEFAULT_TEST_CMD, timeout: float = 120.0) -> tuple[bool, str]:
    """Tests must pass on the unmodified code, otherwise every mutant looks 'killed'."""
    work = copy_repo(repo)
    try:
        status, tail, _ = run_tests(work, test_cmd, timeout)
        return status == Status.SURVIVED, tail
    finally:
        shutil.rmtree(work.parent, ignore_errors=True)


def run_one(repo: Path, m: Mutant, test_cmd: str, timeout: float) -> MutantResult:
    work = copy_repo(repo)
    try:
        target = work / m.file
        try:
            target.write_text(apply_mutant(target.read_text(encoding="utf-8"), m), encoding="utf-8")
        except ValueError as e:
            return MutantResult(m, Status.INVALID, 0.0, str(e))
        status, tail, dur = run_tests(work, test_cmd, timeout)
        return MutantResult(m, status, dur, tail)
    finally:
        shutil.rmtree(work.parent, ignore_errors=True)


def run_all(repo: Path, mutants: list[Mutant], test_cmd: str = DEFAULT_TEST_CMD, timeout: float = 60.0,
            jobs: int = 4, on_result=None) -> list[MutantResult]:
    results: list[MutantResult] = []
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        futs = [ex.submit(run_one, repo, m, test_cmd, timeout) for m in mutants]
        for f in futs:
            r = f.result()
            results.append(r)
            if on_result:
                on_result(r)
    return results
