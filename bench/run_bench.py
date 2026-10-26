"""Phase 6 benchmark: do agent-written PRs' tests catch realistic bugs? And are LLM bugs sneakier than classic ones?

Usage:  python bench/run_bench.py bench/prs.csv --out bench/results.csv
Then:   python bench/make_table.py bench/results.csv > bench/RESULTS.md

For each row in prs.csv:
  1. git clone repo_url into bench/.work/<name>, checkout head_sha
  2. create a venv-free install: `pip install -e .` (if fails, `pip install -r requirements.txt`); skip row on failure
  3. run `python -m snitch run --diff <base_sha> --mutator llm   --json llm.json`
  4. run `python -m snitch run --diff <base_sha> --mutator classic --json classic.json`
  5. append a row: repo, pr, agent, n_llm, llm_trust, n_classic, classic_trust, n_equiv, status
Rows that fail (clone/install/baseline) are written with status=<reason> and NOT dropped silently.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

SNITCH_ROOT = Path(__file__).resolve().parents[1]


def sh(cmd: str, cwd: Path | None = None, timeout: int = 600) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + "\n" + p.stderr)[-2000:]
    except subprocess.TimeoutExpired:
        return 124, "timed out"


def load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def summarize(data: dict) -> tuple[int, float | None, int]:
    """(n counted minus equiv, trust, n_equiv) per PLAN.md: n = killed+survived+timeout minus likely-equivalent."""
    results = data.get("results", [])
    equiv = sum(1 for r in results if r.get("mutant", {}).get("likely_equivalent"))
    counted = [r for r in results if r["status"] in ("killed", "survived", "timeout")
               and not r.get("mutant", {}).get("likely_equivalent")]
    n = len(counted)
    trust = data.get("trust_score")
    return n, trust, equiv


def run_row(row: dict, workdir: Path) -> dict:
    repo_url = row["repo_url"].strip()
    pr = row["pr_number"].strip()
    agent = row.get("agent", "").strip()
    base_sha = row.get("base_sha", "").strip()
    head_sha = row.get("head_sha", "").strip()
    out = {"repo": repo_url, "pr": pr, "agent": agent, "n_llm": 0, "llm_trust": "",
           "n_classic": 0, "classic_trust": "", "n_equiv": 0, "status": "ok"}
    name = repo_url.rstrip("/").split("/")[-2:]
    dirname = "__".join(name).replace(".", "_")
    dest = workdir / dirname
    if not (dest / ".git").is_dir():
        code, tail = sh(f"git clone {repo_url} {dest}", timeout=300)
        if code != 0:
            out["status"] = "clone_failed"
            return out
    # checkout PR head: fetch pull ref then checkout head sha
    code, _ = sh(f"git fetch origin pull/{pr}/head:pr{pr}", cwd=dest, timeout=300)
    if code != 0:
        # fall back: fetch all and checkout head sha directly
        sh("git fetch origin", cwd=dest, timeout=300)
    code, tail = sh(f"git checkout {head_sha}", cwd=dest, timeout=120)
    if code != 0:
        out["status"] = "checkout_failed"
        return out
    code, _ = sh(f"git merge-base {base_sha} {head_sha}", cwd=dest, timeout=60)
    base_out = subprocess.run(f"git merge-base {base_sha} {head_sha}", shell=True, cwd=dest,
                              capture_output=True, text=True, timeout=60)
    base = base_out.stdout.strip() if base_out.returncode == 0 else base_sha

    venv = dest / "venv"
    vpy = venv / "bin" / "python"
    if not vpy.exists():
        # use our own interpreter (3.14), not system python3 (often 3.9) which is too old for these repos
        code, tail = sh(f"{sys.executable} -m venv --system-site-packages venv", cwd=dest, timeout=300)
        if code != 0:
            out["status"] = "venv_failed"
            return out
    # candidate install targets: root package, requirements, then any subdir with pyproject (uv workspaces)
    targets = []
    if (dest / "pyproject.toml").exists() or (dest / "setup.py").exists():
        targets.append(dest)
    if (dest / "requirements.txt").exists():
        targets.append(None)  # marker for -r requirements.txt
    for sub in sorted(p.parent for p in dest.glob("*/pyproject.toml")):
        if sub != dest:
            targets.append(sub)
    installed = False
    for t in targets:
        if t is None:
            code, _ = sh(f"{vpy} -m pip install -q -r requirements.txt", cwd=dest, timeout=600)
        else:
            code, _ = sh(f"{vpy} -m pip install -q .", cwd=t, timeout=600)
        if code == 0:
            installed = True
    if not installed:
        out["status"] = "install_failed"
        return out
    # test plugins the suite may need (asyncio, httpx, mock...); best-effort
    sh(f"{vpy} -m pip install -q pytest pytest-asyncio pytest-mock httpx anyio trio", cwd=dest, timeout=600)

    test_cmd = f"{vpy} -m pytest -q -x -p no:cacheprovider"
    rowdir = workdir / f"{dirname}-pr{pr}"
    rowdir.mkdir(parents=True, exist_ok=True)
    llm_json = rowdir / "llm.json"
    code, tail = sh(
        f"timeout 600 env PYTHONPATH={SNITCH_ROOT} {vpy} -m snitch run --repo {dest} "
        f"--diff {base} --per-file 6 --mutator llm --json {llm_json} --test-cmd \"{test_cmd}\"",
        cwd=SNITCH_ROOT, timeout=660)
    dllm = load_json(llm_json)
    if dllm is None:
        out["status"] = f"no_json_exit{code}"
        return out
    n_llm, trust_llm, n_equiv = summarize(dllm)
    out.update(n_llm=n_llm, llm_trust="" if trust_llm is None else trust_llm, n_equiv=n_equiv)

    classic_json = rowdir / "classic.json"
    code, tail = sh(
        f"timeout 600 env PYTHONPATH={SNITCH_ROOT} {vpy} -m snitch run --repo {dest} "
        f"--diff {base} --per-file 6 --mutator classic --json {classic_json} --test-cmd \"{test_cmd}\"",
        cwd=SNITCH_ROOT, timeout=660)
    dclass = load_json(classic_json)
    if dclass is None:
        out["status"] = f"no_json_exit{code}"
        return out
    n_cl, trust_cl, _ = summarize(dclass)
    out.update(n_classic=n_cl, classic_trust="" if trust_cl is None else trust_cl)
    if trust_cl == 0.0 and n_cl >= 3:
        out["status"] = "suspect_import_path"
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python bench/run_bench.py bench/prs.csv --out bench/results.csv", file=sys.stderr)
        return 2
    csv_path = Path(sys.argv[1])
    out_path = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else SNITCH_ROOT / "bench" / "results.csv"
    workdir = SNITCH_ROOT / "bench" / ".work"
    workdir.mkdir(parents=True, exist_ok=True)
    rows = [r for r in csv.DictReader((l for l in csv_path.read_text().splitlines() if not l.startswith("#")))
            if r.get("repo_url", "").strip()]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["repo", "pr", "agent", "n_llm", "llm_trust",
                                          "n_classic", "classic_trust", "n_equiv", "status"])
        w.writeheader()
        for row in rows:
            res = run_row(row, workdir)
            w.writerow(res)
            f.flush()
            print(f"{res['repo']}#{res['pr']}: llm_trust={res['llm_trust']} classic_trust={res['classic_trust']} status={res['status']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
