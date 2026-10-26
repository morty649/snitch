"""Turn changed lines into validated Mutants.

Two mutators:
  * LLMMutator     - asks a model for realistic, agent-style bugs (the product)
  * ClassicMutator - old-school operator flips (< -> <=, == -> !=, ...). Used offline, in tests,
                     and as the BASELINE in the benchmark ("are LLM bugs harder to catch than classic ones?").

Every mutant goes through validate_mutant(): the original line must match, the change must be real,
and the mutated file must still parse (ast.parse). Bad mutants are dropped, never crash the run.
"""
from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path

from .llm import LLM, extract_json
from .models import Mutant
from .prompts import MUTATE_SYSTEM, MUTATE_USER


def _mid(file: str, line: int, mutated: str) -> str:
    return hashlib.sha1(f"{file}:{line}:{mutated}".encode()).hexdigest()[:8]


def apply_mutant(source: str, m: Mutant) -> str:
    """Return `source` with mutant applied. Raises ValueError if it doesn't fit."""
    lines = source.splitlines(keepends=True)
    if not (1 <= m.line <= len(lines)):
        raise ValueError(f"line {m.line} out of range")
    current = lines[m.line - 1]
    if current.strip() != m.original.strip():
        raise ValueError(f"original mismatch at line {m.line}: {current.strip()!r} != {m.original.strip()!r}")
    indent = current[: len(current) - len(current.lstrip())]
    newline = "\n" if current.endswith("\n") else ""
    lines[m.line - 1] = indent + m.mutated.strip() + newline
    return "".join(lines)


def validate_mutant(source: str, m: Mutant) -> bool:
    if m.mutated.strip() == m.original.strip() or not m.mutated.strip():
        return False
    try:
        new_src = apply_mutant(source, m)
        ast.parse(new_src)
    except (ValueError, SyntaxError):
        return False
    return True


def _is_mutable_line(text: str) -> bool:
    s = text.strip()
    return bool(s) and not s.startswith(("#", '"""', "'''", "import ", "from ", "@")) and not s.startswith("def ") and not s.startswith("class ")


def docstring_lines(source: str) -> set[int]:
    """Line numbers covered by bare string statements (docstrings). Never mutate those."""
    out: set[int] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant) and isinstance(node.value.value, str):
            out.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return out


def mutable_targets(source: str, target_lines: set[int]) -> list[int]:
    src_lines = source.splitlines()
    skip = docstring_lines(source)
    return sorted(l for l in target_lines if l <= len(src_lines) and l not in skip and _is_mutable_line(src_lines[l - 1]))


def numbered(source: str) -> str:
    return "\n".join(f"{i:4d}| {l}" for i, l in enumerate(source.splitlines(), start=1))


class LLMMutator:
    def __init__(self, llm: LLM, per_file: int = 12):
        self.llm = llm
        self.per_file = per_file

    def mutants_for_file(self, repo: Path, file: str, target_lines: set[int]) -> list[Mutant]:
        source = (repo / file).read_text(encoding="utf-8")
        targets = mutable_targets(source, target_lines)
        if not targets:
            return []
        user = MUTATE_USER.format(file=file, numbered_code=numbered(source), target_lines=targets, n=self.per_file)
        try:
            raw = extract_json(self.llm.complete(MUTATE_SYSTEM, user))
        except (ValueError, RuntimeError) as e:
            print(f"\nsnitch: skipping {file}: {e}")
            return []
        if isinstance(raw, dict):  # some models wrap the list: {"mutants": [...]}
            raw = next((v for v in raw.values() if isinstance(v, list)), [])
        out: list[Mutant] = []
        seen: set[tuple[int, str]] = set()
        for item in raw if isinstance(raw, list) else []:
            try:
                m = Mutant(
                    id="",
                    file=file,
                    line=int(item["line"]),
                    original=str(item["original"]),
                    mutated=str(item["mutated"]),
                    description=str(item.get("description", "")),
                    category=str(item.get("category", "other")),
                )
            except (KeyError, TypeError, ValueError):
                continue
            if m.line not in targets:
                continue
            key = (m.line, m.mutated.strip())
            if key in seen or not validate_mutant(source, m):
                continue
            seen.add(key)
            m.id = _mid(file, m.line, m.mutated)
            out.append(m)
        return out[: self.per_file]


# (pattern, replacement, category) — each matching rule yields one mutant (first occurrence on the line).
CLASSIC_RULES: list[tuple[str, str, str]] = [
    (r"<=", "<", "boundary"),
    (r">=", ">", "boundary"),
    (r"(?<![<>=!])<(?![<=])", "<=", "boundary"),
    (r"(?<![<>=!-])>(?![>=])", ">=", "boundary"),
    (r"==", "!=", "condition"),
    (r"!=", "==", "condition"),
    (r"\band\b", "or", "condition"),
    (r"\bor\b", "and", "condition"),
    (r"\bTrue\b", "False", "condition"),
    (r"\bFalse\b", "True", "condition"),
    (r" \+ 1\b", "", "off_by_one"),
    (r" - 1\b", "", "off_by_one"),
    (r"(?<![*/+\-=]) \+ (?!=)", " - ", "arithmetic"),
    (r"(?<![*/+\-=]) \* (?!=)", " / ", "arithmetic"),
]


class ClassicMutator:
    def __init__(self, per_file: int = 12):
        self.per_file = per_file

    def mutants_for_file(self, repo: Path, file: str, target_lines: set[int]) -> list[Mutant]:
        source = (repo / file).read_text(encoding="utf-8")
        src_lines = source.splitlines()
        out: list[Mutant] = []
        for ln in mutable_targets(source, target_lines):
            text = src_lines[ln - 1].strip()
            code, _, _comment = text.partition("  #")
            for pat, rep, cat in CLASSIC_RULES:
                if re.search(pat, code):
                    mutated = re.sub(pat, rep, code, count=1)
                    m = Mutant(id="", file=file, line=ln, original=text, mutated=mutated,
                               description=f"classic {cat}: /{pat}/ -> {rep!r}", category=cat)
                    if validate_mutant(source, m):
                        m.id = _mid(file, ln, mutated)
                        out.append(m)
        return out[: self.per_file]


def generate(mutator, repo: Path, changed: dict[str, set[int]]) -> list[Mutant]:
    mutants: list[Mutant] = []
    for file, lines in sorted(changed.items()):
        mutants.extend(mutator.mutants_for_file(repo, file, lines))
    return mutants
