# 🐀 Snitch

**Finds the bugs your tests would let through.**

Your PR is green. Coverage is high. But would your tests catch an off-by-one in the code you just changed?
Snitch plants **realistic, agent-style bugs** (using an open-source code LLM) in the lines your PR changed, runs your tests against each one, and shows you exactly which bugs would have shipped. With `--kill`, it writes a test for each survivor and **verifies** that the test fails on the bug and passes on your code.

> AI agents write more of our code every week, and "tests pass" is the gate before shipping. Snitch measures whether passing means anything.

```
SNITCH  Test trust: 50%  (5 of 10 realistic bugs slipped through)

[SURVIVED] shopcalc/pricing.py:11  (boundary)
   - if quantity >= 10:
   + if quantity > 10:
```
*(classic-mutator run: `snitch run --repo examples/shopcalc --files shopcalc/pricing.py --mutator classic --per-file 40` → trust 0.50, 5 killed / 5 survived of 10)*

With the LLM mutator (`glm-5.3-flash` via IndieRouter), the bugs get sneakier — trust **0.20** on the same file: 8 of 10 realistic bugs slipped through.

## Install
```bash
pip install -e .
```

## Configure a model
Any OpenAI-compatible endpoint with an open-source code model:
```bash
cp .env.example .env   # fill SNITCH_BASE_URL, SNITCH_MODEL; key via SNITCH_API_KEY or SNITCH_API_KEY_ENV
```
Tested with `glm-5.3-flash` at `https://api.indierouter.ai/v1`.

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

## --kill: verified tests, not suggestions

On a copy of `examples/shopcalc` (classic, `--per-file 40`), the score went from **0.50 → 0.80** after adding the 3 verified killer tests (`--kill --write-tests`):

```python
from shopcalc.pricing import bulk_discount


def test_bulk_discount_boundary():
    """Exactly 50 items must get the 20% tier (>= boundary, not >)."""
    assert bulk_discount(50) == 0.20
```
Each kept test is verified: passes on your code, fails on the bug. Unverified ones are thrown away.

## GitHub Action
See `.github/workflows/snitch-pr.yml`. Demo: [snitch-demo#1](https://github.com/morty649/snitch-demo/pull/1) — a "fully tested" store-credit PR; Snitch [commented](https://github.com/morty649/snitch-demo/pull/1#issuecomment-6413622196) with trust 50% (1 of 2 realistic bugs slipped through: the day-7 full-refund boundary).

## Benchmark
See `bench/RESULTS.md` — 4 real merged copilot-swe-agent PRs: mean LLM trust **0.72** vs classic **0.84**; ≥1 LLM mutant survived in **3 of 4** PRs (33 mutants, 12 survivors).

## Built with Alan
*(TODO: screenshots of the Alan workflow / execution trace — see FLAGS.md)*

## Limitations
Python + pytest only · single-line mutants · one repo copy per mutant · equivalence detection is an LLM heuristic.

## License
MIT
