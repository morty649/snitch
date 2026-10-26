# 🐀 Snitch

**Finds the bugs your tests would let through.**

Your PR is green. Coverage is 94%. But would your tests catch an off-by-one in the code you just changed?
Snitch plants **realistic, agent-style bugs** (using an open-source code LLM) in the lines your PR changed, runs your tests against each one, and shows you exactly which bugs would have shipped. With `--kill`, it writes a test for each survivor and **verifies** that the test fails on the bug and passes on your code.

> AI agents write more of our code every week, and "tests pass" is the gate before shipping. Snitch measures whether passing means anything.

```
SNITCH  Test trust: 50%  (5 of 10 realistic bugs slipped through)

[SURVIVED] shopcalc/pricing.py:11  (boundary)
   - if quantity >= 10:
   + if quantity > 10:
```
*(offline classic-mutator run on `examples/shopcalc`; LLM results: TODO, see PLAN.md Phase 7)*

## Install
```bash
pip install -e .
```

## Configure a model
Any OpenAI-compatible endpoint with an open-source code model:
```bash
cp .env.example .env   # fill SNITCH_BASE_URL, SNITCH_API_KEY, SNITCH_MODEL
```

## Quickstart
```bash
# offline, no model: classic mutation operators
snitch run --repo examples/shopcalc --files shopcalc/pricing.py --mutator classic

# LLM mutants on lines changed vs main, write killer tests, gate the merge
snitch run --diff main --kill --md snitch.md --json snitch.json --fail-under 0.7
```

## How it works
1. `git diff -U0 <base>` → changed lines in non-test `.py` files
2. LLM proposes realistic single-line bugs → validated (original line matches, still parses, not a docstring)
3. Each mutant runs in an isolated temp copy → `killed` / `survived` / `timeout`
4. Likely-equivalent survivors are flagged and excluded from the score
5. `--kill`: LLM writes a test per survivor; kept only if it **passes on the original and fails on the mutant**

## GitHub Action
See `.github/workflows/snitch-pr.yml`. *(demo PR link: TODO)*

## Benchmark
*(TODO: bench/RESULTS.md)*

## Built with Alan
*(TODO: screenshots of the Alan workflow / execution trace)*

## Limitations
Python + pytest only · single-line mutants · one repo copy per mutant · equivalence detection is an LLM heuristic.

## License
MIT
