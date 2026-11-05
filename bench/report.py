#!/usr/bin/env python3
"""Write bench/results/SUMMARY.md and docs/FRONTIER.md from the JSON results."""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from qnxscout import kb  # noqa: E402
from qnxscout.score import grade_for, points_from_summary  # noqa: E402


def bench_md(path: str) -> str:
    d = json.load(open(path))
    s, pk = d["summary"], d["packages"]
    ok = [p for p in pk if p.get("status") == "ok"]
    L = ["# qnxscout benchmark: QNX's own ports", "",
         "Method: for each package in `qnx-ports/aports`, download the pristine upstream source the recipe builds, "
         "scan it with qnxscout, and compare with what QNX engineers changed: their QNX-specific patches "
         "(identifiers in changed lines, and code they wrapped in new `#if` blocks) plus APKBUILD changes "
         "(extra `-l` flags when the source uses that library, `update_config_sub`, raised C standard). "
         "Recall is per (package, issue).", "",
         "| Metric | Value |", "|---|---|",
         f"| QNX packages in qnx-ports/aports | {s['packages_total']} |",
         f"| Scanned from pristine upstream source | {s['packages_scanned']} |",
         f"| Packages with QNX fixes qnxscout can be checked against | {s['packages_with_ground_truth']} |",
         f"| Distinct (package, issue) fixes made by QNX engineers | {s['ground_truth_issues']} |",
         f"| **Predicted by qnxscout (same rule)** | **{s['predicted_issues_hit']} ({s['recall']:.0%})** |",
         f"| Predicted, counting the right file as a hit | {s['location_hits']} ({s['recall_with_location']:.0%}) |",
         f"| Effort-score AUC: needed QNX fixes vs. built unchanged | {s['auc_effort_score']} |", "",
         "Not scanned: " + ", ".join(f"{k} ({v})" for k, v in s["status_counts"].items() if k != "ok") + ".", "",
         f"Notes: {s['note']}" if s.get("note") else "", "",
         "Ground truth is a conservative lower bound: some QNX recipe flags are redundant (libuv already links "
         "`socket` in its upstream QNX branch), and a fix QNX made centrally (one compat header) counts once.", "",
         "## Per-rule recall", "", "| Rule | Issue | QNX fixed | Predicted | Recall | Packages flagged |",
         "|---|---|---|---|---|---|"]
    for rid, r in sorted(s["per_rule"].items(), key=lambda kv: (-kv[1]["gt"], kv[0])):
        if rid not in kb.RULES_BY_ID:
            continue
        rec = f"{r['hit'] / r['gt']:.0%}" if r["gt"] else "-"
        L.append(f"| {rid} | {kb.RULES_BY_ID[rid].title} | {r['gt']} | {r['hit']} | {rec} | {r['predicted_in']} |")
    L += ["", "## Grade vs. actual QNX patch size", "",
          "| Grade | Packages | Median QNX patch lines | Share needing any QNX source patch |", "|---|---|---|---|"]
    by = {}
    for p in ok:
        by.setdefault(p["score"]["grade"], []).append(p)
    for g in "ABCDE":
        ps = by.get(g, [])
        if not ps:
            continue
        lines = sorted(p.get("qnx_patch_lines", 0) for p in ps)
        med = lines[len(lines) // 2]
        share = sum(1 for p in ps if p.get("qnx_patches")) / len(ps)
        L.append(f"| {g} | {len(ps)} | {med} | {share:.0%} |")
    L += ["", "## Every package", "", "| Package | Grade | QNX fixed | qnxscout predicted | Missed |", "|---|---|---|---|---|"]
    for p in ok:
        gt = set(p["ground_truth"])
        if not gt:
            continue
        pr = set(p["predicted"])
        L.append(f"| {p['package']} | {p['score']['grade']} | {', '.join(sorted(gt))} | {', '.join(sorted(gt & pr)) or '-'} "
                 f"| {', '.join(sorted(gt - pr)) or '-'} |")
    return "\n".join(L) + "\n"


def frontier_md(path: str, top: int = 150) -> str:
    d = json.load(open(path))
    res = [r for r in d["results"] if r.get("status") == "ok" and (r.get("c_files") or 0) >= 5]
    grades = {}
    for r in res:
        grades[r["score"]["grade"]] = grades.get(r["score"]["grade"], 0) + 1
    L = ["# The QNX porting frontier", "",
         f"Generated {d['generated']} by `bench/frontier.py`. Alpine (edge) packages that are **not yet in "
         f"qnx-ports/aports**: {d['unported_candidates']} with C/C++-style builds. Of those, **{d['unblocked']}** "
         "already have every build and runtime dependency ported to QNX. Each was scanned from pristine upstream "
         "source and ranked by predicted QNX porting effort.", "",
         "| Grade | Packages |", "|---|---|"] + [f"| {g} | {grades.get(g, 0)} |" for g in "ABCDE"] + [
         "", f"## Easiest {min(top, len(res))} (at least 5 C/C++ files)", "",
         "| # | Package | Grade | Points | C/C++ files | What qnxscout expects you to fix | Description |",
         "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(res[:top], 1):
        tops = ", ".join(f"{k} {kb.RULES_BY_ID[k].title.split(' ')[0]}" for k in list(r.get("top_findings", {}))[:3]) or "nothing"
        L.append(f"| {i} | [{r['package']}]({r.get('url') or ''}) | {r['score']['grade']} | {r['score']['points']} | "
                 f"{r.get('c_files', '')} | {tops} | {(r.get('description') or '').replace('|', '/')[:70]} |")
    L += ["", "## Most wanted dependencies", "",
          "Dependencies that are not yet on QNX, ranked by how many unported packages each one blocks.", "",
          "| Dependency | Packages waiting on it |", "|---|---|"]
    for name, n in d["most_wanted_dependencies"][:30]:
        L.append(f"| {name} | {n} |")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench")
    ap.add_argument("--frontier")
    ap.add_argument("--out-bench", default=os.path.join(HERE, "results", "SUMMARY.md"))
    ap.add_argument("--out-frontier", default=os.path.join(os.path.dirname(HERE), "docs", "FRONTIER.md"))
    a = ap.parse_args()
    if a.bench:
        os.makedirs(os.path.dirname(a.out_bench), exist_ok=True)
        open(a.out_bench, "w").write(bench_md(a.bench))
        print("wrote", a.out_bench)
    if a.frontier:
        open(a.out_frontier, "w").write(frontier_md(a.frontier))
        print("wrote", a.out_frontier)


if __name__ == "__main__":
    main()
