from __future__ import annotations

import os
import sys
from collections import defaultdict

from .. import kb

COLORS = {"blocker": "31", "runtime": "35", "link": "33", "review": "36", "info": "90"}


def _c(code: str, s: str, color: bool) -> str:
    return f"\033[{code}m{s}\033[0m" if color else s


def render(result, color: bool = None, max_per_rule: int = 6, show_info: bool = False) -> str:
    if color is None:
        color = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
    out = []
    sc = result.score
    name = os.path.basename(result.root.rstrip("/")) or result.root
    out.append(_c("1", f"qnxscout: QNX 8.0 port-readiness report for {name}", color))
    out.append(f"  scanned {result.c_files} C/C++ files and {result.build_files} build files "
               f"({', '.join(result.build_systems) or 'no build system detected'}) in {result.duration_s}s"
               + (f"; verified against SDP at {result.sdp}" if result.sdp else ""))
    out.append("")
    grade = _c("1;" + {"A": "32", "B": "32", "C": "33", "D": "31", "E": "31"}[sc["grade"]],
               f"Grade {sc['grade']}: {sc['label']}", color)
    out.append(f"  {grade}  (effort points {sc['points']}, {sc['distinct_rules']} distinct issues, "
               f"~{sc['files_to_touch']} files to touch)")
    counts = ", ".join(f"{_c(COLORS[s], s, color)} {n}" for s, n in sc["by_severity"].items() if n)
    out.append(f"  findings: {counts or 'none'}")
    if sc["link_flags"]:
        out.append(f"  QNX link additions: {' '.join(sc['link_flags'])}")
    out.append("")
    groups = defaultdict(list)
    for f in result.findings:
        if f.severity == "info" and not show_info:
            continue
        groups[(f.rule, f.severity)].append(f)
    order = {s: i for i, s in enumerate(kb.SEVERITIES)}
    for (rid, sev), fs in sorted(groups.items(), key=lambda kv: (order[kv[0][1]], kv[0][0])):
        rule = kb.RULES_BY_ID[rid]
        files = len({f.file for f in fs})
        out.append(_c(COLORS[sev], f"[{sev.upper()}] {rid} {rule.title}", color) +
                   f"  ({len(fs)} hit{'s' if len(fs) != 1 else ''} in {files} file{'s' if files != 1 else ''})")
        out.append(f"    why: {rule.why}")
        out.append(f"    fix: {rule.fix}")
        for f in sorted(fs, key=lambda f: (f.confidence != "high", f.in_tests, f.file, f.line))[:max_per_rule]:
            tag = "" if f.confidence == "high" else " (conditional)"
            tag += " [test]" if f.in_tests else ""
            out.append(f"    - {f.file}:{f.line}: {f.message}{tag}")
        if len(fs) > max_per_rule:
            out.append(f"    ... and {len(fs) - max_per_rule} more")
        ev = rule.evidence_links()[:2]
        out.append("    evidence: " + "; ".join(u for _l, u in ev))
        out.append("")
    if not groups:
        out.append("  No QNX porting issues found.")
    return "\n".join(out)
