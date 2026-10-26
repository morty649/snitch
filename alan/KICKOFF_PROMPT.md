# Paste this into Alan as the task (Muse Spark 1.3 as executor)

You are building "Snitch", an open-source CLI + GitHub Action, in this repository. Hard deadline: Tuesday Oct 27, 2026, 12:00 PM IST.

1. Read `AGENTS.md`, then read `PLAN.md` completely, before changing anything. PLAN.md is the single source of truth.
2. Execute PLAN.md phase by phase, starting at Phase 0. Follow every rule in its section 2, especially: run `python -m pytest tests -q` after every change, never weaken existing tests, never edit `examples/shopcalc/`, never commit `.env`.
3. The modules marked "done" in PLAN.md section 1 already work and are tested. Do not rewrite them; only fill in the stubs the plan names.
4. Anything only the human can do (API keys, creating GitHub repos, secrets, screenshots, picking PRs if search fails, recording the demo) → append a FLAG to `FLAGS.md` in the exact format shown there, then continue with whatever isn't blocked.
5. Run `TZ=Asia/Kolkata date` at the start of each phase and obey the plan's skip rules.
6. At the end of each phase, commit, then post a 3-line status: phase finished, test count, any new FLAG numbers.
