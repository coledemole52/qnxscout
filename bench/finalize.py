#!/usr/bin/env python3
"""Fill the {{PLACEHOLDERS}} in the docs from measured benchmark and frontier results.

  python3 bench/finalize.py --bench bench/results/results.json --frontier bench/results/frontier.json \\
      [--extra /path/to/MISSION_REPORT.md]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from qnxscout import kb  # noqa: E402

DOCS = ["README.md", "docs/submission/DEVPOST.md", "docs/submission/VIDEO_SCRIPT.md"]


def values(bench: dict, frontier: dict) -> dict:
    s = bench["summary"]
    res = [r for r in frontier["results"] if r.get("status") == "ok" and (r.get("c_files") or 0) >= 5]
    grades = {}
    for r in res:
        grades[r["score"]["grade"]] = grades.get(r["score"]["grade"], 0) + 1
    easy = grades.get("A", 0) + grades.get("B", 0)
    table = "\n".join([
        "| | |", "|---|---|",
        f"| QNX ports scanned from pristine upstream source | {s['packages_scanned']} of {s['packages_total']} |",
        f"| Real fixes QNX engineers made (package, issue) | {s['ground_truth_issues']} in {s['packages_with_ground_truth']} packages |",
        f"| **Predicted by qnxscout before building** | **{s['predicted_issues_hit']} ({s['recall']:.0%})** |",
        f"| ... counting the right file as a hit | {s['location_hits']} ({s['recall_with_location']:.0%}) |",
        f"| Effort score: needed QNX fixes vs. built unchanged (AUC) | {s['auc_effort_score']} |",
    ])
    frontier_summary = (f"Of **{frontier['unported_candidates']}** Alpine packages not yet ported, **{frontier['unblocked']}** "
                        f"have every dependency already on QNX. qnxscout scanned {len(res)} of them with C/C++ code: "
                        f"**{easy}** are predicted to be grade A or B (build as-is, or link flags and a few defines).")
    return {
        "RULES": str(len(kb.RULES)),
        "SCANNED": str(s["packages_scanned"]),
        "GT": str(s["ground_truth_issues"]),
        "GT_PKGS": str(s["packages_with_ground_truth"]),
        "RECALL": f"{s['recall']:.0%}",
        "RECALL_LOC": f"{s['recall_with_location']:.0%}",
        "AUC": str(s["auc_effort_score"]),
        "UNPORTED": f"{frontier['unported_candidates']:,}",
        "UNBLOCKED": f"{frontier['unblocked']:,}",
        "FRONTIER_EASY": str(easy),
        "BENCH_TABLE": table,
        "FRONTIER_SUMMARY": frontier_summary,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", required=True)
    ap.add_argument("--frontier", required=True)
    ap.add_argument("--extra", action="append", default=[])
    a = ap.parse_args()
    v = values(json.load(open(a.bench)), json.load(open(a.frontier)))
    for rel in DOCS + a.extra:
        path = rel if os.path.isabs(rel) else os.path.join(ROOT, rel)
        text = open(path).read()
        new = re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: v.get(m.group(1), m.group(0)), text)
        left = re.findall(r"\{\{[A-Z_]+\}\}", new)
        open(path, "w").write(new)
        print(f"{rel}: {'ok' if not left else 'UNFILLED ' + ', '.join(sorted(set(left)))}")
    print(json.dumps({k: val for k, val in v.items() if "\n" not in val}, indent=1))


if __name__ == "__main__":
    main()
