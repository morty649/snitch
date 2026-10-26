# Benchmark RESULTS

Question: do PRs written by AI coding agents ship with tests that catch realistic bugs? And are LLM-generated bugs sneakier than classic mutation operators?

Model: `glm-5.3-flash` via IndieRouter. Command per row: `python bench/run_bench.py bench/prs.csv --out bench/results.csv` (per-file 6, both mutators, real runs).

| repo | pr | n_llm | llm_trust | n_classic | classic_trust | n_equiv | status |
|---|---|---|---|---|---|---|---|
| refrain | 14 | 4 | 1.0 | 6 | 1.0 | 0 | ok |
| refrain | 12 | 13 | 0.3846 | 8 | 0.375 | 1 | ok |
| refrain | 10 | 8 | 0.625 | 3 | 1.0 | 0 | ok |
| refrain | 8 | 8 | 0.875 | 6 | 1.0 | 4 | ok |
| JVRWall | 3 | 0 |  | 0 |  | 0 | install_failed |

- mean LLM trust vs mean classic trust (over 4 ok rows): 0.72 vs 0.84
- % of PRs where >= 1 LLM mutant survived: 75% (3/4)
- total mutants: 33, total survivors: 12, total likely-equivalent: 5

Reading: agent-written tests catch most classic operator flips (mean 0.84) but let more LLM-style realistic bugs through (mean 0.72); 3 of 4 PRs shipped at least one survivor. The JVRWall row failed at install (repo venv issue) and is reported honestly, not dropped.

## Limitations

- Small N (4 ok rows), all from one repo (ControlForgeHQ/refrain, all copilot-swe-agent PRs) — selection bias toward small pure-Python libs whose suites install cleanly.
- Equivalent-mutant judge is an LLM heuristic, not a proof.
- Single-line bugs only; real PR bugs can span lines.
- Row shortlist favored repos that install offline-friendly deps (Django/DB/GUI rows failed and were excluded).
