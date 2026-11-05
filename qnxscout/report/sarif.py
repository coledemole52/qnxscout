"""SARIF 2.1.0 output, for GitHub code scanning and IDE integrations."""
from __future__ import annotations

import json

from .. import __version__, kb

LEVEL = {"blocker": "error", "runtime": "error", "link": "warning", "review": "warning", "info": "note"}
SECURITY_SEVERITY = {"blocker": "8.0", "runtime": "7.0", "link": "5.0", "review": "4.0", "info": "1.0"}


def render(result) -> str:
    used = sorted({f.rule for f in result.findings})
    index = {r: i for i, r in enumerate(used)}
    rules = []
    for rid in used:
        r = kb.RULES_BY_ID[rid]
        ev = r.evidence_links()
        rules.append({
            "id": rid,
            "name": r.title.replace(" ", ""),
            "shortDescription": {"text": r.title},
            "fullDescription": {"text": r.why},
            "help": {"text": f"{r.why}\n\nFix: {r.fix}",
                     "markdown": f"{r.why}\n\n**Fix:** {r.fix}\n\n**Evidence:**\n" +
                                 "\n".join(f"- [{label}]({url})" for label, url in ev)},
            "helpUri": ev[0][1] if ev else "https://github.com/",
            "defaultConfiguration": {"level": LEVEL[r.severity]},
            "properties": {"tags": ["qnx", "portability", r.category], "precision": "medium",
                           "problem.severity": LEVEL[r.severity]},
        })
    results = []
    for f in result.findings:
        results.append({
            "ruleId": f.rule,
            "ruleIndex": index[f.rule],
            "level": LEVEL.get(f.severity, "note"),
            "message": {"text": f.message + (f" ({f.note})" if f.note else "")},
            "locations": [{"physicalLocation": {
                "artifactLocation": {"uri": f.file, "uriBaseId": "%SRCROOT%"},
                "region": {"startLine": max(1, f.line), "snippet": {"text": f.snippet}} if f.snippet
                else {"startLine": max(1, f.line)}}}],
            "partialFingerprints": {"qnxscout/v1": f"{f.rule}:{f.file}:{f.symbol}"},
            "properties": {"severity": f.severity, "confidence": f.confidence, "inTests": f.in_tests},
        })
    doc = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "qnxscout", "version": __version__,
                                "informationUri": "https://github.com/",
                                "rules": rules}},
            "results": results,
            "properties": {"score": result.score, "target": "QNX SDP 8.0"},
        }],
    }
    return json.dumps(doc, indent=2)
