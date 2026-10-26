"""Phase 6 benchmark: do agent-written PRs' tests catch realistic bugs? And are LLM bugs sneakier than classic ones?

Usage:  python bench/run_bench.py bench/prs.csv --out bench/results.csv
Then:   python bench/make_table.py bench/results.csv > bench/RESULTS.md

For each row in prs.csv:
  1. git clone repo_url into bench/.work/<name>, checkout head_sha
  2. create a venv-free install: `pip install -e .` (if fails, `pip install -r requirements.txt`); skip row on failure
  3. run `python -m snitch run --diff <base_sha> --mutator llm   --json llm.json`
  4. run `python -m snitch run --diff <base_sha> --mutator classic --json classic.json`
  5. append a row: repo, pr, agent, n_llm, llm_trust, n_classic, classic_trust, n_equiv, status
Rows that fail (clone/install/baseline) are written with status=<reason> and NOT dropped silently.

STATUS: stub. TODO(Phase 6).
"""
import sys

if __name__ == "__main__":
    print("TODO(Phase 6): implement per the docstring above.", file=sys.stderr)
    sys.exit(2)
