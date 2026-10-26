# NOTES

## Phase 2: prompt tuning (Mon Oct 26, 2026, ~3 PM IST, model glm-5.3-flash via IndieRouter)

Commands (from snitch root):
```
rm -rf .snitch/debug && mkdir -p .snitch
SNITCH_DEBUG_DIR=.snitch/debug ./venv/bin/python -m snitch run --repo examples/shopcalc --files shopcalc/pricing.py --mutator llm --no-equiv --per-file 15 --json .snitch/llm.json
./venv/bin/python -m snitch run --repo examples/shopcalc --files shopcalc/pricing.py --mutator classic --per-file 15 --json .snitch/classic.json
# after editing snitch/prompts.py, same llm command with --json .snitch/llm_tuned.json
```

| run | proposed | valid | valid% | silly | realistic% | trust |
|---|---|---|---|---|---|---|
| baseline prompt (llm.json) | 10 | 10 | 100% | 0 | 100% | 0.30 |
| tuned prompt (llm_tuned.json) | 10 | 10 | 100% | 0 | 100% | 0.20 |
| classic baseline (classic.json) | — | 10 | — | — | — | 0.50 |

Tuning added: edge-case-only guidance, diversity across lines/categories, 3 short examples. Kept the tuned prompt (sneakier: trust 0.2 < 0.3 < classic 0.5). Both gates (valid% ≥ 70, realistic% ≥ 70) passed on the first try, so only 1 iteration used.
