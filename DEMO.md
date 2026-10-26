# DEMO.md: 90-second Snitch script

- **0:00** — Green repo, high coverage. `examples/shopcalc`: 4 tests pass, every function covered. Looks safe.
- **0:15** — `snitch run --repo examples/shopcalc --files shopcalc/pricing.py --mutator llm`. Live dots: each dot is your whole test suite running against one planted bug.
- **0:35** — The score: **Test trust 20%** — 8 of 10 realistic bugs slipped through. One survivor diff: `if quantity >= 10:` → `if quantity > 10:`. "An off-by-one in bulk discounts nobody caught — exactly-10 orders silently lose 10%."
- **0:55** — `--kill`: each survivor now shows a verified test (fails on the bug, passes on real code). Then switch to the classic run to show the measured effect: on a copy of shopcalc, adding the 3 verified killer tests took classic trust from **0.50 → 0.80** (say "classic" out loud; the 20% above is the LLM run).
- **1:15** — PR comment: [snitch-demo#1](https://github.com/morty649/snitch-demo/pull/1) shows the same Snitch comment on a "fully tested" PR. Benchmark headline: see `bench/RESULTS.md`.
- **1:25** — "Tests pass. But do they mean anything? Snitch tells you."
