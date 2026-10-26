"""snitch CLI.

Examples:
  snitch run --files shopcalc/pricing.py --mutator classic          # offline, no model needed
  snitch run --diff main                                            # LLM mutants on lines changed vs main
  snitch run --diff main --kill --md snitch.md --json snitch.json --fail-under 0.8
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import diff as diffmod
from .equiv import flag_equivalents
from .kill import write_killer_tests
from .models import Report, Status
from .mutate import ClassicMutator, LLMMutator, generate
from .report import headline, to_json, to_markdown, to_terminal
from .runner import DEFAULT_TEST_CMD, baseline, run_all


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="snitch", description="Finds the bugs your tests would let through.")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="plant realistic bugs and see which ones your tests miss")
    r.add_argument("--repo", default=".", help="repo root (default: .)")
    tgt = r.add_mutually_exclusive_group(required=True)
    tgt.add_argument("--diff", metavar="BASE", help="mutate only lines changed vs this git ref (e.g. main, origin/main)")
    tgt.add_argument("--files", nargs="+", help="mutate every line of these files (paths relative to --repo)")
    r.add_argument("--mutator", choices=["llm", "classic"], default="llm")
    r.add_argument("--per-file", type=int, default=12, help="max mutants per file")
    r.add_argument("--jobs", type=int, default=4)
    r.add_argument("--timeout", type=float, default=60.0, help="seconds per test run")
    r.add_argument("--test-cmd", default=DEFAULT_TEST_CMD)
    r.add_argument("--no-equiv", action="store_true", help="skip the likely-equivalent filter")
    r.add_argument("--kill", action="store_true", help="write + verify a killer test for each survivor")
    r.add_argument("--json", metavar="PATH", help="write JSON report")
    r.add_argument("--md", metavar="PATH", help="write Markdown report (PR comment)")
    r.add_argument("--fail-under", type=float, default=None, help="exit 1 if trust score < this (0..1); use as a merge gate")
    return p


def cmd_run(a: argparse.Namespace) -> int:
    repo = Path(a.repo).resolve()
    changed = diffmod.changed_lines(repo, a.diff) if a.diff else diffmod.all_source_lines(repo, a.files)
    if not changed:
        print("snitch: no changed non-test Python lines; nothing to do.")
        return 0

    ok, tail = baseline(repo, a.test_cmd, a.timeout * 2)
    if not ok:
        print("snitch: your tests FAIL (or don't run) on the unmodified code. Fix that first.\n" + tail, file=sys.stderr)
        return 2

    llm = None
    if a.mutator == "llm" or a.kill:  # classic mode without --kill runs fully offline
        from .llm import OpenAICompatLLM
        try:
            llm = OpenAICompatLLM()
        except RuntimeError as e:
            print(f"snitch: {e}", file=sys.stderr)
            return 2
    mutator = LLMMutator(llm, a.per_file) if a.mutator == "llm" else ClassicMutator(a.per_file)

    print(f"snitch: generating mutants for {len(changed)} file(s) with {a.mutator} mutator...")
    mutants = generate(mutator, repo, changed)
    if not mutants:
        print("snitch: no valid mutants generated.")
        return 0
    print(f"snitch: running tests against {len(mutants)} mutants ({a.jobs} parallel)...")

    def tick(r):
        sym = {Status.KILLED: ".", Status.SURVIVED: "S", Status.TIMEOUT: "T", Status.ERROR: "E", Status.INVALID: "x"}[r.status]
        print(sym, end="", flush=True)

    results = run_all(repo, mutants, a.test_cmd, a.timeout, a.jobs, on_result=tick)
    print()
    rep = Report(repo=str(repo), base=a.diff, results=results, model=getattr(llm, "name", "") if llm else "classic")

    if llm is not None and not a.no_equiv:
        n = flag_equivalents(llm, repo, results)
        if n:
            print(f"snitch: {n} survivor(s) look equivalent; excluded from score.")
    if a.kill and llm is not None:
        n = write_killer_tests(llm, repo, results, a.test_cmd, a.timeout)
        print(f"snitch: wrote {n} verified killer test(s).")

    print(to_terminal(rep))
    if a.json:
        Path(a.json).write_text(to_json(rep), encoding="utf-8")
    if a.md:
        Path(a.md).write_text(to_markdown(rep), encoding="utf-8")

    score = rep.trust_score()
    if a.fail_under is not None and score is not None and score < a.fail_under:
        print(f"snitch: FAIL, {headline(rep)} < required {a.fail_under:.0%}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    from .llm import load_dotenv
    load_dotenv()
    a = build_parser().parse_args(argv)
    if a.cmd == "run":
        return cmd_run(a)
    return 2


if __name__ == "__main__":
    sys.exit(main())
