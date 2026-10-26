# PLAN.md: build Snitch end to end

You are the coding agent. Read this ENTIRE file before touching code. Then work phase by phase, in order.
Hard deadline: **Tuesday Oct 27, 2026, 12:00 PM IST** (submission closes 1:00 PM IST).

## 0. What we are building (read twice)

**Snitch** is a CLI + GitHub Action. It answers one question about a pull request:
*"If this PR's changed code had a realistic bug, would the tests catch it?"*

How it works:
1. Find the lines the PR changed (`git diff -U0 <base>`), only non-test `.py` files.
2. Ask an open-source code LLM for **realistic single-line bugs** ("mutants") on those lines: off-by-one, `<` vs `<=`, swapped args, missing None check...
3. For each mutant: copy the repo to a temp dir, apply the bug, run pytest.
   - tests fail → **killed** (good, tests caught it)
   - tests pass → **survived** (bad, the bug would ship)
4. **Trust score** = caught / total. Survivors are shown as diffs.
5. Optional `--kill`: for each survivor, the LLM writes a pytest test; we keep it **only if** it passes on the real code AND fails on the bug.
6. Output: terminal, Markdown (PR comment), JSON, and an exit code gate (`--fail-under 0.7`).

Pitch: *"AI agents write more and more of our code, and 'tests pass' is the only check before shipping. Snitch measures whether passing even means anything."*

## 1. What ALREADY works. Do NOT rewrite it.

| File | Status |
|---|---|
| `snitch/models.py` | done. Mutant, MutantResult, Status, Report, trust_score |
| `snitch/diff.py` | done. Changed-line parsing, test-file exclusion |
| `snitch/llm.py` | done. OpenAI-compatible client, FakeLLM, `extract_json`, `.env` loader, `SNITCH_DEBUG_DIR` dumps |
| `snitch/mutate.py` | done. LLMMutator, ClassicMutator, `apply_mutant`, `validate_mutant` (ast check), docstring skip |
| `snitch/runner.py` | done. Temp-copy isolation, pytest exit-code mapping, parallel runs, baseline check |
| `snitch/report.py` | done. Terminal, Markdown, JSON |
| `snitch/cli.py` | done. `snitch run ...` wiring for everything, including the stubs below |
| `snitch/prompts.py` | **tune** in Phase 2 |
| `snitch/equiv.py` | **STUB → implement** in Phase 3 |
| `snitch/kill.py` | **STUB → implement** in Phase 4 |
| `bench/run_bench.py` | **STUB → implement** in Phase 6 |
| `examples/shopcalc/` | demo repo: green tests that miss boundary bugs, on purpose. Do NOT "fix" its tests. |
| `tests/test_core.py` | 13 passing tests. Must stay green forever. |

## 2. Rules (follow every one)

1. **Run `python -m pytest tests -q` after EVERY change.** If anything that passed before now fails, fix your change. Never delete, skip, or weaken an existing test.
2. **Never edit `examples/shopcalc/`** (the weak tests are the demo).
3. **Do not change function signatures** in `equiv.py`, `kill.py`, `models.py`. `cli.py` already calls them.
4. **Do not add dependencies** beyond `openai` and `pytest` (use the standard library).
5. **No network in `tests/`.** Use `FakeLLM` from `snitch/llm.py` (see `test_llm_mutator_with_fake_llm_filters_garbage` for the pattern).
6. **Never invent numbers.** Every score in README or bench must come from a command you actually ran. Paste the command next to the number.
7. **Never commit `.env`** or any API key.
8. **Commit after each phase**: `git add -A && git commit -m "phase N: <what>"`. Do not commit if tests fail.
9. **When stuck for more than ~20 minutes or 3 failed attempts on the same error, write a FLAG** in `FLAGS.md` (format is in that file). If it's NON-BLOCKING, move to the next step. If it's BLOCKING, still do any later phase that doesn't depend on it.
   - You have no clock: run `TZ=Asia/Kolkata date` at the start of every phase and before applying any skip rule.
   - **Re-read `FLAGS.md` at the start of every phase and after every commit.** Act on any `Status: DONE <answer>` before continuing. When FLAG-0 becomes DONE, do Phase 1 then Phase 2 next, before resuming other work.
   - If every remaining step is blocked by OPEN flags: write what you finished and what's blocked into `NOTES.md`, then STOP. Do not loop re-checking.
10. Keep changes small. Prefer adding a new function over restructuring existing code.
11. If an instruction here seems wrong, don't silently deviate. Write a NON-BLOCKING FLAG explaining why and what you did instead.

## 3. Phases

Each phase has: **Do**, **Verify** (commands that must succeed), **Done when**. Do not start phase N+1 until phase N's "Done when" holds, unless the phase says it can be skipped.

---

### Phase 0: Setup + offline sanity (≈15 min, no API key needed)

**Do**
```bash
git init -b main 2>/dev/null
git config user.name "snitch-agent"; git config user.email "agent@example.com"
mkdir -p .snitch
git add -A; git commit -qm "skeleton" || true
python -m pip install -e .
python -m pytest tests -q
python -m snitch run --repo examples/shopcalc --files shopcalc/pricing.py --mutator classic --per-file 40
```
**Verify**: tests print `13 passed`. The snitch run prints a line starting `SNITCH  Test trust:` with a score between 30% and 70%, and at least 3 `[SURVIVED]` entries.
**Done when**: both hold. Commit `phase 0: setup verified`.
If `pip install -e .` fails: use `pip install --user -e .`, or set `PYTHONPATH=.` and keep going (NON-BLOCKING flag).

---

### Phase 1: Live LLM smoke test (≈30 min, needs FLAG-0 done)

**Do**
1. Check `.env` exists with SNITCH_BASE_URL / SNITCH_API_KEY / SNITCH_MODEL filled. If not, FLAG-0 is still OPEN. Skip ahead to Phase 3 and Phase 4 (both are testable with FakeLLM) and come back.
2. Run:
```bash
SNITCH_DEBUG_DIR=.snitch/debug python -m snitch run --repo examples/shopcalc --files shopcalc/pricing.py --mutator llm --no-equiv --json .snitch/llm1.json
```
3. Open `.snitch/debug/call_0000.txt` and read the REPLY.

**Verify**: the JSON has ≥ 6 results with status `killed` or `survived`.
**If 0 mutants**: the reply format is wrong. Check the debug file:
- reply is empty or an error → model name or URL wrong → BLOCKING FLAG with the exact error.
- reply has JSON but with different keys → fix the parsing in `LLMMutator.mutants_for_file` (accept the alternate key names) and add a FakeLLM test for that exact format.
- reply has the line numbers inside `original` (e.g. `"  12| if x:"`) → strip a leading `\s*\d+\|\s?` from `original` and `mutated` before validating, and add a test.
- the model refuses or chatters → strengthen "Reply with ONLY a JSON array" in `prompts.MUTATE_SYSTEM`.

**Done when**: ≥ 6 valid LLM mutants on shopcalc. Commit `phase 1: live llm works (<model name>)`.

---

### Phase 2: Make the bugs *realistic* (≈45 min)

Goal: LLM mutants should look like bugs a human or agent would actually write, and be **harder to catch** than classic ones. This is the core claim of the project.

**Do**
1. Run both mutators on shopcalc and save JSON (always clear the debug dir first, or `call_0000.txt` will be stale):
```bash
rm -rf .snitch/debug && mkdir -p .snitch
SNITCH_DEBUG_DIR=.snitch/debug python -m snitch run --repo examples/shopcalc --files shopcalc/pricing.py --mutator llm --no-equiv --per-file 15 --json .snitch/llm.json
python -m snitch run --repo examples/shopcalc --files shopcalc/pricing.py --mutator classic --per-file 15 --json .snitch/classic.json
```
2. Measure:
   - **proposed** = number of objects in the JSON array inside the REPLY of `.snitch/debug/call_0000.txt`
   - **valid** = number of entries in `results` of `.snitch/llm.json` (invalid ones were already dropped)
   - **valid%** = valid / proposed
   - **silly** = valid mutants whose `mutated` line contains `return None`, `pass`, `raise`, or replaces a whole condition with `True`/`False`
   - **realistic%** = (valid − silly) / valid
3. Edit ONLY `snitch/prompts.py` (`MUTATE_SYSTEM`, `MUTATE_USER`) to reduce silly ones. Good tricks: add 3 short examples of realistic bugs to the system prompt; ask for diversity across lines; ask that each bug "only shows up for some inputs (an edge case)".
4. Repeat at most 3 prompt iterations. Write the before/after numbers in `NOTES.md` (create it).

**Verify**: `python -m pytest tests -q` still passes.
**Done when**: valid% ≥ 70% AND realistic% ≥ 70%. Commit `phase 2: prompt tuning`.
**Skip rule**: if it's past **7:00 PM IST Monday**, stop tuning, commit what you have, go to Phase 3.

---

### Phase 3: Equivalent-mutant filter (≈45 min). Implement `snitch/equiv.py`

Problem: some "survivors" can't be caught by ANY test (e.g. `x * 2` → `x + x`). They unfairly lower the score.

**Do**: implement `flag_equivalents(llm, repo, results) -> int`:
```
count = 0
for r in results:
    if r.status != Status.SURVIVED: continue
    source = (repo / r.mutant.file).read_text(encoding="utf-8")
    line = r.mutant.line
    context = "\n".join(source.splitlines()[max(0, line - 16): line + 15])
    try:
        reply = llm.complete(EQUIV_SYSTEM, EQUIV_USER.format(context=context, line=r.mutant.line,
                                                             original=r.mutant.original, mutated=r.mutant.mutated),
                             temperature=0.0)
        data = extract_json(reply)
    except (ValueError, RuntimeError):
        continue                           # API error or unsure -> NOT equivalent (be conservative), never crash
    if isinstance(data, dict) and data.get("equivalent") is True:
        r.mutant.likely_equivalent = True
        count += 1
return count
```
Import `EQUIV_SYSTEM, EQUIV_USER` from `.prompts` and `extract_json` from `.llm`. Only `True` (the JSON boolean) counts. The strings "true"/"yes" do NOT count.

**Add tests** in a NEW file `tests/test_equiv.py` using `FakeLLM`:
- a survivor + fake reply `{"equivalent": true, ...}` → flagged, returns 1
- a survivor + fake reply `{"equivalent": false, ...}` → not flagged
- a KILLED result → LLM is never called (`len(fake.calls) == 0`)
- garbage reply `"I think so"` → not flagged, no crash

Build MutantResult objects by hand, like `test_report_score_excludes_equivalent` in `tests/test_core.py`. For `repo`, use the `DEMO` path and a real line from `shopcalc/pricing.py`.

**Verify**: `python -m pytest tests -q` → all pass (13 old + your new ones).
**Done when**: tests pass. If you have a key, also run `python -m snitch run --repo examples/shopcalc --files shopcalc/pricing.py --mutator llm` and confirm it prints the equivalent count line or none. Commit `phase 3: equivalence filter`.

---

### Phase 4: Kill loop (≈1.5 h). Implement `snitch/kill.py`. THE STAR FEATURE

For each survivor, generate a test that **proves** the bug matters. The verification is the point. Never keep an unverified test.

**Do**: implement `write_killer_tests(llm, repo, results, test_cmd, timeout, attempts=2) -> int`:
```
from .runner import copy_repo, run_tests
from .mutate import apply_mutant
from .prompts import KILL_SYSTEM, KILL_USER
from .models import Status
import re, shutil

def _extract_code(reply):
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", reply, re.S)
    return (m.group(1) if m else reply).strip() + "\n"

def _find_example_test(repo):
    for p in sorted(repo.rglob("test_*.py")):
        if p.name.startswith("test_snitch_") or ".snitch" in p.parts: continue
        return "\n".join(p.read_text(encoding="utf-8").splitlines()[:60])
    return ""

def _test_dir(work):
    return work / "tests" if (work / "tests").is_dir() else work

made = 0
example_test = _find_example_test(repo)
for r in results:
    if r.status != Status.SURVIVED or r.mutant.likely_equivalent: continue
    src = (repo / r.mutant.file).read_text(encoding="utf-8")
    line = r.mutant.line
    context = "\n".join(src.splitlines()[max(0, line - 21): line + 20])
    feedback = ""
    for attempt in range(attempts):
        prompt = KILL_USER.format(example_test=example_test, file=r.mutant.file, context=context,
                                  line=r.mutant.line, original=r.mutant.original, mutated=r.mutant.mutated,
                                  description=r.mutant.description) + feedback
        code = _extract_code(llm.complete(KILL_SYSTEM, prompt, temperature=0.2))
        if "def test_" not in code: feedback = "\n\nYour reply had no pytest test function. Try again."; continue
        test_name = f"test_snitch_{r.mutant.id}.py"

        # (a) must PASS on ORIGINAL code
        work = copy_repo(repo); (_test_dir(work)/test_name).write_text(code)
        st_orig, out_orig, _ = run_tests(work, test_cmd, timeout); shutil.rmtree(work.parent, ignore_errors=True)
        if st_orig != Status.SURVIVED:                      # SURVIVED here means "all tests passed"
            feedback = f"\n\nYour test FAILED on the correct code. Output:\n{out_orig[-1500:]}\nFix it."; continue

        # (b) must FAIL on MUTATED code
        work = copy_repo(repo); (_test_dir(work)/test_name).write_text(code)
        f = work / r.mutant.file; f.write_text(apply_mutant(f.read_text(), r.mutant))
        st_mut, out_mut, _ = run_tests(work, test_cmd, timeout); shutil.rmtree(work.parent, ignore_errors=True)
        if st_mut == Status.KILLED:
            r.killer_test = code; made += 1; break
        feedback = "\n\nYour test PASSED on the buggy code, so it doesn't catch the bug. Make it check the exact edge case."
return made
```
Robustness (required):
- Wrap each `llm.complete(...)` in `try/except RuntimeError` → treat as a failed attempt (`continue`), never crash.
- Delete temp dirs in `try/finally` (`shutil.rmtree(work.parent, ignore_errors=True)` inside `finally`), so a failure doesn't leak them.
- `apply_mutant` can raise `ValueError` → `break` out of the attempts for that mutant.
- In `_extract_code`, if there is no fence AND no `def test_` in the reply, return `""`.

Status naming warning: `run_tests` returns `Status.SURVIVED` when **all tests pass** and `Status.KILLED` when **some test fails**. Read that twice.

Also add a CLI flag `--write-tests DIR` in `snitch/cli.py`. Only ADD; don't restructure.
- In `build_parser()`, after the `--kill` line: `r.add_argument("--write-tests", metavar="DIR", help="save verified killer tests here")`
- In `cmd_run()`, right after the `if a.kill and llm is not None:` block:
```python
    if a.write_tests:
        out_dir = Path(a.write_tests); out_dir.mkdir(parents=True, exist_ok=True)
        for r in results:
            if r.killer_test:
                (out_dir / f"test_snitch_{r.mutant.id}.py").write_text(r.killer_test, encoding="utf-8")
```

**Add tests** in NEW `tests/test_kill.py` with FakeLLM on the shopcalc demo. Use the survivor from `test_runner_kills_and_survives` (`if quantity >= 10:` → `if quantity > 10:`):
- fake returns a CORRECT killer test:
  ````python
  ```python
  from shopcalc.pricing import bulk_discount
  def test_snitch_ten():
      assert bulk_discount(10) == 0.10
  ```
  ````
  → returns 1, `killer_test` set.
- fake returns a test that fails on the original too (`assert bulk_discount(10) == 0.99`) on every attempt → returns 0, `killer_test` stays None.
- fake returns a test that passes on both (`assert bulk_discount(1) == 0.0`) → returns 0.
- non-survivor results → LLM never called.

**Verify**: `python -m pytest tests -q` → all pass. Then, if you have a key:
```bash
python -m snitch run --repo examples/shopcalc --files shopcalc/pricing.py --mutator llm --kill --md .snitch/demo.md
```
`.snitch/demo.md` should contain at least one "Suggested test (verified" block.
**Done when**: the tests pass (the live run is a bonus). Commit `phase 4: verified kill loop`.

---

### Phase 5: GitHub repo + PR-comment demo (≈1 h)

**Do**
1. **FLAG (BLOCKING for this phase only)**: ask Morty to create the public repo `github.com/morty649/snitch` and give you push access (or run `gh auth login` himself). Meanwhile do Phase 6 prep or the README.
2. Push this repo there.
3. Create a second public demo repo `snitch-demo` (Morty creates it, same FLAG). Copy the **CONTENTS** of `examples/shopcalc/` to the **ROOT** of snitch-demo, so `shopcalc/` and `tests/` sit at the root (not under `examples/`). Add `.github/workflows/snitch.yml` copied from `.github/workflows/snitch-pr.yml`, with the provider/model lines filled in.
4. **FLAG**: Morty adds the repo secret `SNITCH_API_KEY` in `snitch-demo` settings. You cannot see or type keys.
   Commit all of that to `main` FIRST (the workflow must exist on main), then create branch `refund-store-credit`.
5. In `snitch-demo`, from branch `refund-store-credit` (same repo, NOT a fork, or the secret won't be available), open a PR that changes `refund_amount` (e.g. adds a 7-day "store credit" tier) **with a description claiming "fully tested"**, plus one weak test.
6. Confirm the Action posts the Snitch comment. Save a screenshot path or the comment URL in `NOTES.md`.

**Done when**: a real PR shows a Snitch comment with survivors. If Actions fail and you can't fix them in 45 min, FLAG and instead run locally with `--md` and put that output in the README as "example PR comment".

---

### Phase 6: Mini-benchmark (≈2 h). The "this guy has research taste" part

Question: **Do PRs written by AI coding agents ship with tests that catch realistic bugs? And are LLM-generated bugs sneakier than classic mutation operators?**

**Do**
1. Fill `bench/prs.csv` with **8 to 10** real merged PRs authored by coding agents. Candidate searches (untested syntax, adjust if `gh` complains):
   ```bash
   gh search prs --app copilot-swe-agent --merged --language python --limit 50 --json repository,number,url,title
   gh search prs --app devin-ai-integration --merged --language python --limit 50 --json repository,number,url,title
   gh search prs --merged --language python --match body '"Generated with Claude Code"' --limit 50 --json repository,number,url,title
   ```
   Per candidate: `gh pr view N -R owner/repo --json baseRefOid,headRefOid,files,body` and `gh repo view owner/repo --json diskUsage`.
   Keep a PR only if it changes 1–4 non-test `.py` files, the repo's diskUsage < 20000 (KB), and it doesn't need a database, Docker, GPUs or secrets.
   **FLAG (NON-BLOCKING)** asking Morty for 8 PR URLs if `gh` is missing, unauthenticated, returns errors, or you haven't found 8 good PRs after 30 minutes.
2. Implement `bench/run_bench.py` per its docstring, with THESE exact details (they override the docstring):
   - Skip CSV lines starting with `#`.
   - Full clone (no `--depth`) into `bench/.work/<owner>__<repo>`. Then `git fetch origin pull/<N>/head:pr<N>`, `git checkout pr<N>`, and `BASE=$(git merge-base <base_sha> pr<N>)`. Use BASE for `--diff`, not base_sha directly.
   - One venv per repo, so repos can't break each other: `python -m venv --system-site-packages bench/.work/<name>/venv`. Install with `<venv>/bin/pip install -q .` (**NOT** `-e`), or `-r requirements.txt` if that fails, plus `pytest`.
   - Run snitch from the snitch root, wrapped in `timeout 600`:
     `PYTHONPATH=<abs snitch root> <venv>/bin/python -m snitch run --repo <abs repo> --diff <BASE> --per-file 6 --mutator llm --json <abs>/llm.json --test-cmd "<venv>/bin/python -m pytest -q -x -p no:cacheprovider"`, then the same with `--mutator classic --json <abs>/classic.json`.
   - If a JSON file is missing after a run, write that row with `status=no_json_exit<code>` (exit 2 = tests fail on unmodified code).
   - Columns: `n_llm` = count of killed+survived+timeout results, minus likely-equivalent ones; `llm_trust` = `trust_score` from the JSON; `n_equiv` = `likely_equivalent`. Same for classic.
   - Sanity canary: if classic trust is exactly 0.0 with ≥ 3 mutants, set `status=suspect_import_path` (the tests are probably importing an installed copy, not the mutated one).
   - Never silently drop a row.
3. **Create** `bench/make_table.py` (it doesn't exist yet): read results.csv and print a Markdown table plus 3 summary lines:
   - mean LLM trust vs mean classic trust (over rows with status=ok)
   - % of PRs where ≥ 1 LLM mutant survived
   - total mutants, total survivors, total likely-equivalent
4. Write `bench/RESULTS.md` from real output. Add a short "Limitations" section: small N, equivalent-mutant judge is an LLM, single-line bugs only, repo selection bias.

**Done when**: `bench/RESULTS.md` has ≥ 5 successful rows (status=ok). Fewer is OK if time runs out: report honestly what you got.
**Skip rule**: if it's past **8:00 AM IST Tuesday**, stop adding PRs and write up what you have.

---

### Phase 7: README + demo assets (≈1 h; must start by 10:00 AM IST Tuesday at the latest)

Rewrite `README.md` (keep the existing structure, fill in real content):
1. One-line pitch + a terminal screenshot or code block of a real run on shopcalc
2. Install, Configure a model (`.env`), Quickstart (offline classic mode + LLM mode)
3. How it works (the 5 steps from section 0 of this plan)
4. `--kill` with a REAL verified test from your run
5. GitHub Action usage (link the demo PR)
6. Benchmark results (from `bench/RESULTS.md`)
7. "Built with Alan": FLAG Morty to provide 1–2 screenshots of the Alan execution trace / workflow, and put them in `docs/` with captions he gives you
8. Limitations + roadmap (JS/TS support, multi-line mutants, mutating only covered lines, caching)
9. License MIT (add `LICENSE` file)

Also write `DEMO.md`: a 90-second script Morty will read while recording:
- 0:00 green repo, high coverage
- 0:15 `snitch run`, live dots
- 0:35 the score + one survivor diff ("an off-by-one in refunds nobody caught")
- 0:55 `--kill`: each survivor now shows a verified test (fails on the bug, passes on real code). Only say "score goes from X to Y" if you actually reran with the written tests added to the repo (`--write-tests examples_copy/tests`) and measured Y. Do it on a COPY of shopcalc, never on `examples/shopcalc` itself.
- 1:15 PR comment + benchmark headline number
- 1:25 one-line close

**FLAG (BLOCKING, last)**: "Ready for Morty: record demo video + submit." List the repo URL, demo PR URL, and the headline numbers.

## 4. Time budget (IST)

| Window | Phases |
|---|---|
| Mon 1:45 PM–3:30 PM | 0, 1, 2 |
| Mon 3:30 PM–7:00 PM | 3, 4 |
| Mon 7:00 PM–10:00 PM | 5, start 6 |
| overnight (if the agent keeps running) | 6 |
| Tue 7:00 AM–10:00 AM | finish 6, 7 |
| Tue 10:00 AM–12:00 PM | Morty records the demo and submits; agent only fixes what Morty reports |

If behind schedule, cut in this order: Phase 6 down to 5 PRs, then Phase 2 iterations, then Phase 5 (use local `--md` output). **Never cut Phase 4.**

## 5. Known limits (keep them in the README, don't "fix" them now)
- Python + pytest only. Single-line mutants only.
- Each mutant copies the whole repo; fine for small repos, slow for big ones.
- Equivalence and killer tests depend on model quality. The verification step protects killer tests; equivalence flags are a heuristic.
