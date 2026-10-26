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

## Phase 5: GitHub demo (Mon Oct 26, 2026)

- Main repo: https://github.com/morty649/snitch (pushed, public)
- Demo repo: https://github.com/morty649/snitch-demo (main = shopcalc at root + pyproject + snitch.yml workflow)
- Demo PR: https://github.com/morty649/snitch-demo/pull/1 (branch refund-store-credit, "fully tested" store-credit tier + weak test)
- Blocked on FLAG-2: SNITCH_API_KEY secret in snitch-demo settings. Will confirm the Snitch PR comment once it lands.
- CI check on PR #1 fails with exactly `Missing env vars: SNITCH_API_KEY` (workflow itself is fine).
- Snitch PR comment LIVE: https://github.com/morty649/snitch-demo/pull/1#issuecomment-6413622196 — trust 50%, 1 of 2 realistic bugs slipped through on the store-credit PR (boundary: day-7 full-refund edge).

## Phase 7 prep: kill-loop X→Y (Mon Oct 26, copy of shopcalc, classic --per-file 40)

- BEFORE: trust 0.50 (5 killed / 5 survived of 10) — command: `snitch run --repo /tmp/shopcalc_copy --files shopcalc/pricing.py --mutator classic --per-file 40`
- `--kill --write-tests` produced 3 verified killer tests (boundary day-30 refund, coupon $20 edge, bulk-discount exact-10)
- AFTER (tests added to the copy): trust 0.80 (8 killed / 2 survived of 10). Honest numbers for README/DEMO.
