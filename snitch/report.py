"""Render a Report as terminal text, Markdown (for PR comments) or JSON."""
from __future__ import annotations

import json

from .models import Report, Status


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def headline(rep: Report) -> str:
    c = rep.counted()
    surv = rep.survivors()
    return f"Test trust: {_pct(rep.trust_score())}  ({len(surv)} of {len(c)} realistic bugs slipped through)"


def to_terminal(rep: Report) -> str:
    lines = ["", "=" * 70, "SNITCH  " + headline(rep), "=" * 70]
    counts = rep.to_dict()["counts"]
    lines.append("  " + "  ".join(f"{k}={v}" for k, v in counts.items() if v))
    eq = sum(1 for r in rep.results if r.mutant.likely_equivalent)
    if eq:
        lines.append(f"  ({eq} survivor(s) flagged likely-equivalent and excluded from the score)")
    for r in rep.survivors():
        m = r.mutant
        lines += ["", f"[SURVIVED] {m.file}:{m.line}  ({m.category})  {m.description}",
                  f"   - {m.original.strip()}", f"   + {m.mutated.strip()}"]
        if r.killer_test:
            lines.append("   killer test written and verified [OK]")
    lines.append("")
    return "\n".join(lines)


def to_markdown(rep: Report) -> str:
    md = [f"### 🐀 Snitch: {headline(rep)}", ""]
    surv = rep.survivors()
    if not surv:
        md.append("Your tests caught every realistic bug Snitch planted in this PR's changed lines. Nice.")
    else:
        md += ["These single-line bugs in this PR's changed code **pass your whole test suite**:", ""]
        for r in surv[:15]:
            m = r.mutant
            md += [f"<details><summary><code>{m.file}:{m.line}</code>, {m.category}: {m.description}</summary>", "",
                   "```diff", f"- {m.original.strip()}", f"+ {m.mutated.strip()}", "```"]
            if r.killer_test:
                md += ["", "Suggested test (verified: fails on the bug, passes on your code):", "", "```python", r.killer_test.strip(), "```"]
            md += ["</details>", ""]
    md += ["", f"<sub>model: {rep.model or 'n/a'} · base: {rep.base or 'n/a'} · "
           f"{sum(1 for r in rep.results if r.status == Status.KILLED)} killed · "
           f"{sum(1 for r in rep.results if r.mutant.likely_equivalent)} likely-equivalent excluded</sub>"]
    return "\n".join(md)


def to_json(rep: Report) -> str:
    return json.dumps(rep.to_dict(), indent=2)
