"""Turn findings into a port-effort estimate.

Each (rule, file) pair is one "touch point" a porter has to deal with.  Repeat
hits in the same file add only logarithmically (fixing a missing epoll once
fixes all 40 calls), medium-confidence findings count half, and findings in
test code count half.
"""
from __future__ import annotations

import math
from collections import defaultdict

from . import kb

GRADES = [
    (0, "A", "Likely builds as-is"),
    (12, "B", "Minor fixes: link flags or a few defines"),
    (40, "C", "Moderate porting work"),
    (120, "D", "Significant porting work"),
    (float("inf"), "E", "Major porting effort"),
]


def score_findings(findings: list) -> dict:
    groups = defaultdict(list)
    for f in findings:
        if f.severity == "info":
            continue
        groups[(f.rule, f.file)].append(f)
    points = 0.0
    by_sev = defaultdict(int)
    rules = set()
    files = set()
    for (rule_id, file), fs in groups.items():
        sev = fs[0].severity
        w = kb.SEVERITY_WEIGHT.get(sev, 0)
        conf = 1.0 if any(f.confidence == "high" for f in fs) else 0.5
        test = 0.5 if all(f.in_tests for f in fs) else 1.0
        points += w * conf * test * (1 + math.log2(len(fs)) * 0.5)
        rules.add(rule_id)
        files.add(file)
    for f in findings:
        by_sev[f.severity] += 1
    # A link-only problem is solved once per project, not once per file.
    link_rules = {r for r in rules if kb.RULES_BY_ID[r].severity == "link"}
    if link_rules:
        link_pts = sum(kb.SEVERITY_WEIGHT[kb.RULES_BY_ID[r].severity] *
                       (1 + 0.5 * math.log2(1 + sum(1 for (rr, _f) in groups if rr == r)))
                       for r in link_rules)
        points = points - sum(kb.SEVERITY_WEIGHT["link"] * (1 + 0.5 * math.log2(len(fs)))
                              * (1.0 if any(f.confidence == "high" for f in fs) else 0.5)
                              * (0.5 if all(f.in_tests for f in fs) else 1.0)
                              for (r, _f), fs in groups.items() if r in link_rules) + link_pts
    points = round(max(points, 0.0), 1)
    grade, label = next((g, l) for limit, g, l in GRADES if points <= limit)
    blocking_files = len({f.file for f in findings if f.severity in ("blocker", "runtime", "review")})
    return {
        "points": points,
        "grade": grade,
        "label": label,
        "by_severity": {s: by_sev.get(s, 0) for s in kb.SEVERITIES},
        "distinct_rules": len(rules),
        "files_to_touch": blocking_files,
        "link_flags": sorted({kb.RULES_BY_ID[r].link for r in link_rules if kb.RULES_BY_ID[r].link}),
    }
