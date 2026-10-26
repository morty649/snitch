# Agent instructions

1. Read `PLAN.md` fully before doing anything. It is the single source of truth.
2. Work phase by phase. After every change: `python -m pytest tests -q`.
3. Anything only the human (Morty) can do → append to `FLAGS.md` in the format shown there, then keep going on whatever isn't blocked.
4. Never rewrite modules marked "done" in PLAN.md §1. Never edit `examples/shopcalc/`. Never commit `.env`.
