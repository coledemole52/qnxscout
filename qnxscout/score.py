"""Turn findings into a port-effort estimate.

A porting fix is usually made once per *issue* (one compat define, one link
flag, one new #elif branch), not once per call site, so effort is counted per
rule: severity weight x confidence x a small logarithmic factor for how many
files are involved.  Medium-confidence (build-configuration dependent) and
test-only issues count half.  Grade thresholds are calibrated against the size
of the patches QNX engineers actually wrote (see bench/).
"""
from __future__ import annotations

import math
from collections import defaultdict

from . import kb

GRADES = [
    (0, "A", "Likely builds as-is"),
    (8, "B", "Minor fixes: link flags or a few defines"),
    (25, "C", "Moderate porting work"),
    (60, "D", "Significant porting work"),
    (float("inf"), "E", "Major porting effort"),
]


def rule_summary(findings: list) -> dict:
    out = {}
    for f in findings:
        if f.severity == "info":
            continue
        d = out.setdefault(f.rule, {"severity": f.severity, "count": 0, "files": set(), "high": False,
                                    "tests_only": True})
        d["count"] += 1
        d["files"].add(f.file)
        if f.confidence == "high" and not f.in_tests:
            d["high"] = True
        if not f.in_tests:
            d["tests_only"] = False
        if kb.SEVERITIES.index(f.severity) < kb.SEVERITIES.index(d["severity"]):
            d["severity"] = f.severity
    return out


def points_from_summary(summary: dict) -> float:
    pts = 0.0
    for rid, d in summary.items():
        files = d["files"] if isinstance(d["files"], int) else len(d["files"])
        w = kb.SEVERITY_WEIGHT.get(d["severity"], 0)
        conf = 1.0 if d["high"] else 0.5
        test = 0.5 if d["tests_only"] else 1.0
        pts += w * conf * test * (1 + 0.5 * math.log2(max(files, 1)))
    return round(pts, 1)


def grade_for(points: float) -> tuple:
    return next((g, label) for limit, g, label in GRADES if points <= limit)


def score_findings(findings: list) -> dict:
    summ = rule_summary(findings)
    points = points_from_summary(summ)
    grade, label = grade_for(points)
    by_sev = defaultdict(int)
    for f in findings:
        by_sev[f.severity] += 1
    return {
        "points": points,
        "grade": grade,
        "label": label,
        "by_severity": {s: by_sev.get(s, 0) for s in kb.SEVERITIES},
        "distinct_rules": len(summ),
        "files_to_touch": len({f.file for f in findings if f.severity in ("blocker", "runtime", "review")}),
        "link_flags": sorted({kb.RULES_BY_ID[r].link for r, d in summ.items()
                              if kb.RULES_BY_ID[r].severity == "link" and kb.RULES_BY_ID[r].link}),
        "rules": {r: {"severity": d["severity"], "count": d["count"], "files": len(d["files"]),
                      "high": d["high"], "tests_only": d["tests_only"]} for r, d in sorted(summ.items())},
    }
