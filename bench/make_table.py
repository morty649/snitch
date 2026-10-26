"""Read bench/results.csv and print a Markdown table plus 3 summary lines."""
import csv
import sys
from pathlib import Path


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("bench/results.csv")
    rows = list(csv.DictReader(path.read_text().splitlines()))
    ok = [r for r in rows if r.get("status") == "ok"]
    print("| repo | pr | n_llm | llm_trust | n_classic | classic_trust | n_equiv | status |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['repo'].split('/')[-1]} | {r['pr']} | {r['n_llm']} | {r['llm_trust']} | "
              f"{r['n_classic']} | {r['classic_trust']} | {r['n_equiv']} | {r['status']} |")
    print()
    if ok:
        llm = [float(r["llm_trust"]) for r in ok if r["llm_trust"] not in ("", None)]
        cl = [float(r["classic_trust"]) for r in ok if r["classic_trust"] not in ("", None)]
        print(f"- mean LLM trust vs mean classic trust (over {len(ok)} ok rows): "
              f"{sum(llm)/len(llm):.2f} vs {sum(cl)/len(cl):.2f}" if llm and cl else "- no trust numbers yet")
        surv = sum(1 for r in ok if r["n_llm"] and r["llm_trust"] not in ("", None) and float(r["llm_trust"]) < 1.0)
        print(f"- % of PRs where >= 1 LLM mutant survived: {100*surv/len(ok):.0f}% ({surv}/{len(ok)})")
        print(f"- total mutants: {sum(int(r['n_llm'] or 0) for r in ok)}, "
              f"total survivors: {sum(round(float(r['n_llm'] or 0) * (1 - float(r['llm_trust'] or 0))) for r in ok)}, "
              f"total likely-equivalent: {sum(int(r['n_equiv'] or 0) for r in ok)}")
    else:
        print("- no ok rows yet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
