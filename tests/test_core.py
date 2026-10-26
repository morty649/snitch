"""Core tests. These MUST stay green after every phase. Run: python -m pytest tests -q

Never delete or weaken these to make them pass. If one fails, fix the code.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from snitch.cli import main
from snitch.diff import is_test_file, parse_unified_diff
from snitch.llm import FakeLLM, extract_json
from snitch.models import Mutant, Report, MutantResult, Status
from snitch.mutate import ClassicMutator, LLMMutator, apply_mutant, generate, validate_mutant
from snitch.runner import baseline, run_all

DEMO = Path(__file__).resolve().parents[1] / "examples" / "shopcalc"
PRICING = "shopcalc/pricing.py"


def _line_of(text: str, needle: str) -> int:
    for i, l in enumerate(text.splitlines(), 1):
        if needle in l:
            return i
    raise AssertionError(needle)


# ---------- diff ----------
def test_parse_unified_diff():
    d = """diff --git a/x.py b/x.py
--- a/x.py
+++ b/x.py
@@ -3,0 +4,2 @@ def f():
+    a = 1
+    b = 2
@@ -10 +12 @@
-    old
+    new
--- a/gone.py
+++ /dev/null
@@ -1,3 +0,0 @@
"""
    assert parse_unified_diff(d) == {"x.py": {4, 5, 12}}


def test_is_test_file():
    assert is_test_file("tests/test_a.py") and is_test_file("pkg/test_x.py") and is_test_file("conftest.py")
    assert not is_test_file("pkg/core.py")


# ---------- json extraction ----------
def test_extract_json_variants():
    assert extract_json('[{"a":1}]') == [{"a": 1}]
    assert extract_json('Sure!\n```json\n[{"a":1}]\n```\nhope this helps') == [{"a": 1}]
    assert extract_json('blah {"mutants": [1]} blah') == {"mutants": [1]}
    with pytest.raises(ValueError):
        extract_json("no json here")


# ---------- mutants ----------
def test_apply_and_validate():
    src = "def f(x):\n    if x >= 10:\n        return 1\n    return 0\n"
    m = Mutant("", "f.py", 2, "if x >= 10:", "if x > 10:")
    assert apply_mutant(src, m) == "def f(x):\n    if x > 10:\n        return 1\n    return 0\n"
    assert validate_mutant(src, m)
    assert not validate_mutant(src, Mutant("", "f.py", 2, "if x >= 10:", "if x >= 10:"))      # no-op
    assert not validate_mutant(src, Mutant("", "f.py", 2, "if x == 3:", "if x > 10:"))        # wrong original
    assert not validate_mutant(src, Mutant("", "f.py", 2, "if x >= 10:", "if x >>> 10:"))     # syntax error


def test_classic_mutator_on_demo():
    src = (DEMO / PRICING).read_text()
    lines = set(range(1, len(src.splitlines()) + 1))
    ms = ClassicMutator(per_file=100).mutants_for_file(DEMO, PRICING, lines)
    assert len(ms) >= 8
    assert all(validate_mutant(src, m) for m in ms)
    assert len({m.id for m in ms}) == len(ms)


def test_llm_mutator_with_fake_llm_filters_garbage():
    src = (DEMO / PRICING).read_text()
    ln = _line_of(src, "if quantity >= 10:")
    good = {"line": ln, "original": "if quantity >= 10:", "mutated": "if quantity > 10:", "category": "boundary", "description": "10 items get no discount"}
    reply = "Here you go:\n```json\n" + json.dumps([
        good,
        good,                                                                 # duplicate -> dropped
        {"line": ln, "original": "WRONG", "mutated": "x = 1"},               # bad original -> dropped
        {"line": ln, "original": "if quantity >= 10:", "mutated": "if quantity >>> 10:"},  # syntax -> dropped
        {"line": 9999, "original": "x", "mutated": "y"},                     # out of target -> dropped
        {"oops": True},                                                      # malformed -> dropped
    ]) + "\n```"
    llm = FakeLLM(lambda s, u: reply)
    ms = LLMMutator(llm).mutants_for_file(DEMO, PRICING, {ln})
    assert [m.mutated for m in ms] == ["if quantity > 10:"]
    assert "Only mutate these line numbers" in llm.calls[0][1]


# ---------- runner (end to end on demo repo) ----------
def test_baseline_passes_on_demo():
    ok, tail = baseline(DEMO)
    assert ok, tail


def test_runner_kills_and_survives():
    src = (DEMO / PRICING).read_text()
    ln_b = _line_of(src, "if quantity >= 10:")
    ln_r = _line_of(src, "if days_since_purchase <= 14:")
    survivor = Mutant("s", PRICING, ln_b, "if quantity >= 10:", "if quantity > 10:")          # tests never check exactly 10
    killed = Mutant("k", PRICING, ln_r, "if days_since_purchase <= 14:", "if days_since_purchase <= 1:")
    res = {r.mutant.id: r.status for r in run_all(DEMO, [survivor, killed], jobs=2)}
    assert res == {"s": Status.SURVIVED, "k": Status.KILLED}
    # the real demo files must be untouched
    assert (DEMO / PRICING).read_text() == src


def test_report_score_excludes_equivalent():
    m1, m2, m3 = (Mutant(str(i), "f.py", 1, "a", "b") for i in range(3))
    m3.likely_equivalent = True
    rep = Report("r", None, [MutantResult(m1, Status.KILLED), MutantResult(m2, Status.SURVIVED), MutantResult(m3, Status.SURVIVED)])
    assert rep.trust_score() == 0.5
    assert [r.mutant.id for r in rep.survivors()] == ["1"]


def test_cli_classic_files_mode(tmp_path, capsys):
    out_json = tmp_path / "r.json"
    out_md = tmp_path / "r.md"
    code = main(["run", "--repo", str(DEMO), "--files", PRICING, "--mutator", "classic",
                 "--json", str(out_json), "--md", str(out_md), "--jobs", "4"])
    assert code == 0
    data = json.loads(out_json.read_text())
    assert data["counts"]["survived"] >= 1 and data["counts"]["killed"] >= 1
    assert 0 < data["trust_score"] < 1
    assert "Snitch" in out_md.read_text()


def test_cli_fail_under_gate(tmp_path):
    code = main(["run", "--repo", str(DEMO), "--files", PRICING, "--mutator", "classic", "--fail-under", "0.99"])
    assert code == 1


@pytest.mark.skipif(shutil.which("git") is None, reason="git missing")
def test_cli_diff_mode(tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(DEMO, repo)
    run = lambda *c: subprocess.run(c, cwd=repo, check=True, capture_output=True)
    run("git", "init", "-q", "-b", "main")
    run("git", "-c", "user.email=a@b", "-c", "user.name=t", "add", ".")
    run("git", "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "init")
    p = repo / PRICING
    p.write_text(p.read_text().replace("return round(paid / 2, 2)", "return round(paid * 0.5, 2)"))
    out = tmp_path / "r.json"
    assert main(["run", "--repo", str(repo), "--diff", "main", "--mutator", "classic", "--json", str(out)]) == 0
    data = json.loads(out.read_text())
    assert data["results"], "expected mutants on the changed line"
    assert {r["mutant"]["line"] for r in data["results"]} == {_line_of(p.read_text(), "paid * 0.5")}


def test_docstrings_never_mutated():
    src = (DEMO / PRICING).read_text()
    ms = ClassicMutator(per_file=100).mutants_for_file(DEMO, PRICING, set(range(1, len(src.splitlines()) + 1)))
    from snitch.mutate import docstring_lines
    doc = docstring_lines(src)
    assert doc and not any(m.line in doc for m in ms)
