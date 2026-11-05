from __future__ import annotations

import json

from .. import __version__, kb


def render(result) -> str:
    used = sorted({f.rule for f in result.findings})
    return json.dumps({
        "tool": "qnxscout", "version": __version__, "target": "QNX SDP 8.0",
        "root": result.root, "duration_s": result.duration_s, "sdp": result.sdp,
        "files": {"c_cpp": result.c_files, "build": result.build_files},
        "build_systems": result.build_systems,
        "score": result.score,
        "rules": {r: {"title": kb.RULES_BY_ID[r].title, "severity": kb.RULES_BY_ID[r].severity,
                      "why": kb.RULES_BY_ID[r].why, "fix": kb.RULES_BY_ID[r].fix,
                      "evidence": [u for _l, u in kb.RULES_BY_ID[r].evidence_links()]} for r in used},
        "project_provides": result.provided,
        "findings": [f.to_dict() for f in result.findings],
    }, indent=2)
