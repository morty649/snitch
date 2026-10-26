"""All LLM prompts live here so they can be tuned without touching logic.

Phase 2 of PLAN.md is about improving MUTATE_SYSTEM / MUTATE_USER. Keep the JSON schema identical.
"""

MUTATE_SYSTEM = """You are a senior engineer who plants REALISTIC bugs to audit a test suite.
You write the kind of bug a tired human or an AI coding agent would actually ship:
off-by-one, < vs <=, wrong boundary, swapped arguments, inverted condition, missing None/empty check,
wrong default, rounding/truncation error, wrong variable, early return, dropped edge case.
Never write obviously silly bugs (e.g. `return None` everywhere, deleting whole functions, syntax errors).
Each bug changes EXACTLY ONE line. The changed line must still be valid Python with the same indentation.
Each bug should only show up for SOME inputs (an edge case), not break everything — a bug that breaks
every input is too easy to catch and not realistic.
Spread your mutants across different lines and different bug categories; do not repeat the same kind of
change twice.
Examples of good realistic bugs:
- `if quantity >= 10:` -> `if quantity > 10:` (boundary: exactly-10 orders silently lose the discount)
- `return round(paid / 2, 2)` -> `return round(paid / 3, 2)` (wrong divisor: half-refunds come out wrong)
- `if not code:` -> `if code is None:` (empty-string coupon now crashes instead of being ignored)
Reply with ONLY a JSON array, no prose."""

MUTATE_USER = """File: {file}

Code (line numbers on the left, do NOT include them in your output):
{numbered_code}

Only mutate these line numbers: {target_lines}

Return a JSON array of up to {n} objects, each exactly:
{{"line": <int>, "original": "<exact current text of that line, without the line number>",
  "mutated": "<the full new line>", "category": "<off_by_one|boundary|condition|argument|null_check|default|arithmetic|other>",
  "description": "<one short sentence: what bug a user would hit>"}}

Rules:
- "original" must match the current line exactly.
- "mutated" must differ from "original" and must behave differently for SOME input.
- Do not produce two mutants for the same line with the same change.
"""

# Phase 3 (equivalence filter)
EQUIV_SYSTEM = """You judge whether a code change can change program behavior.
Reply with ONLY JSON: {"equivalent": true|false, "witness_input": "<an input that behaves differently, or empty>", "reason": "<short>"}"""

EQUIV_USER = """Function context:
{context}

Original line {line}: {original}
Mutated line {line}:  {mutated}

Is there ANY input for which the mutated program behaves differently from the original?
If yes, equivalent=false and give the input. If no input can tell them apart, equivalent=true."""

# Phase 4 (kill loop)
KILL_SYSTEM = """You write ONE pytest test function that FAILS on a buggy version of the code and PASSES on the correct version.
Reply with ONLY a Python code block containing the imports and a single test function named test_snitch_<something>."""

KILL_USER = """The project's existing tests look like this (for import style):
{example_test}

Correct code of {file} (excerpt):
{context}

The bug: line {line} was changed
FROM: {original}
TO:   {mutated}
Bug description: {description}

Write one pytest test that passes on the correct code and fails on the buggy code."""
