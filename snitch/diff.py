"""Find which source lines a PR changed (vs a base ref), so we only mutate those.

Test files are excluded: we mutate code, not tests.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def is_test_file(path: str) -> bool:
    p = Path(path)
    name = p.name
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name == "conftest.py"
        or "tests" in p.parts
        or "test" in p.parts
    )


def parse_unified_diff(diff_text: str) -> dict[str, set[int]]:
    """Parse `git diff -U0` output into {file: {added/changed line numbers in the NEW file}}."""
    changed: dict[str, set[int]] = {}
    current: str | None = None
    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            target = raw[4:].strip()
            if target == "/dev/null":
                current = None
            else:
                current = target[2:] if target.startswith("b/") else target
            continue
        if current is None:
            continue
        m = HUNK_RE.match(raw)
        if m:
            start = int(m.group(1))
            count = int(m.group(2)) if m.group(2) is not None else 1
            if count > 0:
                changed.setdefault(current, set()).update(range(start, start + count))
    return changed


def changed_lines(repo: Path, base: str) -> dict[str, set[int]]:
    """Changed lines in non-test .py files between `base` and the working tree."""
    proc = subprocess.run(
        ["git", "diff", "-U0", "--no-color", base, "--", "*.py"],
        cwd=repo, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git diff failed: {proc.stderr.strip()}")
    parsed = parse_unified_diff(proc.stdout)
    return {f: lines for f, lines in parsed.items() if not is_test_file(f) and lines}


def all_source_lines(repo: Path, files: list[str]) -> dict[str, set[int]]:
    """For --files mode (no git): treat every line of the given files as 'changed'."""
    out: dict[str, set[int]] = {}
    for f in files:
        text = (repo / f).read_text(encoding="utf-8")
        out[f] = set(range(1, len(text.splitlines()) + 1))
    return out
