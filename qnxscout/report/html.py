"""Self-contained HTML report (no external assets; works offline and as a CI artifact)."""
from __future__ import annotations

import html
import os
from collections import defaultdict

from .. import __version__, kb

SEV_LABEL = {"blocker": "Blocker", "runtime": "Runtime", "link": "Link fix", "review": "Review", "info": "Info"}

CSS = """
:root{--bg:#f7f8fa;--card:#fff;--fg:#1c2230;--muted:#5d6678;--line:#e3e6ec;--mono:#f1f3f7;
--blocker:#c62828;--runtime:#8e24aa;--link:#b26a00;--review:#00838f;--info:#607d8b;--ok:#2e7d32;--accent:#1f5fbf}
@media (prefers-color-scheme:dark){:root{--bg:#0f1218;--card:#171b23;--fg:#e6e9ef;--muted:#9aa3b2;--line:#2a303c;
--mono:#1f2430;--blocker:#ef5350;--runtime:#ce93d8;--link:#ffb74d;--review:#4dd0e1;--info:#90a4ae;--ok:#66bb6a;--accent:#6ea8ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,
"Segoe UI",Roboto,sans-serif}main{max-width:1060px;margin:0 auto;padding:24px 16px 64px}
header{display:flex;gap:24px;align-items:center;flex-wrap:wrap;margin-bottom:20px}
.brand{font-weight:700;letter-spacing:.02em;color:var(--accent)}h1{font-size:22px;margin:2px 0 4px}
.sub{color:var(--muted);font-size:13px}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:18px 20px;margin:14px 0}.score{display:flex;gap:22px;align-items:center;flex-wrap:wrap}
.grade{width:84px;height:84px;border-radius:50%;display:grid;place-items:center;font-size:40px;font-weight:800;
color:#fff;flex:none}.gA,.gB{background:var(--ok)}.gC{background:var(--link)}.gD,.gE{background:var(--blocker)}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}.chip{border-radius:999px;padding:2px 10px;font-size:12px;
font-weight:600;border:1px solid currentColor}.s-blocker{color:var(--blocker)}.s-runtime{color:var(--runtime)}
.s-link{color:var(--link)}.s-review{color:var(--review)}.s-info{color:var(--info)}
code,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12.5px}
code{background:var(--mono);padding:1px 5px;border-radius:4px}details{border-top:1px solid var(--line)}
details:first-of-type{border-top:0}summary{cursor:pointer;list-style:none;padding:12px 0;display:flex;gap:10px;
align-items:baseline;flex-wrap:wrap}summary::-webkit-details-marker{display:none}
summary .rid{font-family:ui-monospace,monospace;color:var(--muted);font-size:12px}summary .t{font-weight:650}
summary .n{color:var(--muted);font-size:13px;margin-left:auto}.body{padding:0 0 14px}
.why{margin:4px 0 8px}.fix{border-left:3px solid var(--accent);padding:4px 10px;background:var(--mono);
border-radius:0 6px 6px 0;margin:8px 0}table{width:100%;border-collapse:collapse;margin-top:8px;table-layout:fixed}
td{border-top:1px solid var(--line);padding:6px 6px;vertical-align:top;word-break:break-word}
td.loc{width:32%}td.snip{color:var(--muted)}.ev{font-size:13px;color:var(--muted);margin-top:8px}
.ev a{color:var(--accent)}.cond{font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:4px;
padding:0 4px;margin-left:6px}footer{color:var(--muted);font-size:12px;margin-top:28px}
@media (max-width:640px){td.loc{width:45%}td.snip{display:none}summary .n{margin-left:0}}
"""


def _e(s) -> str:
    return html.escape(str(s), quote=True)


def render(result, max_rows: int = 40) -> str:
    sc = result.score
    name = os.path.basename(result.root.rstrip("/")) or result.root
    groups = defaultdict(list)
    for f in result.findings:
        groups[(f.severity, f.rule)].append(f)
    order = {s: i for i, s in enumerate(kb.SEVERITIES)}
    items = sorted(groups.items(), key=lambda kv: (order[kv[0][0]], -len({f.file for f in kv[1]}), kv[0][1]))
    chips = "".join(f'<span class="chip s-{s}">{SEV_LABEL[s]}: {n}</span>' for s, n in sc["by_severity"].items() if n)
    link = (f'<div class="sub" style="margin-top:8px">QNX link additions: <code>{_e(" ".join(sc["link_flags"]))}</code></div>'
            if sc["link_flags"] else "")
    parts = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>qnxscout: {_e(name)}</title>
<style>{CSS}</style></head><body><main>
<header><div><div class="brand">qnxscout · QNX 8.0 port-readiness</div><h1>{_e(name)}</h1>
<div class="sub">{result.c_files} C/C++ files · {result.build_files} build files ·
{_e(", ".join(result.build_systems) or "no build system detected")} · scanned in {result.duration_s}s
{(" · verified against SDP " + _e(result.sdp)) if result.sdp else ""}</div></div></header>
<section class="card score"><div class="grade g{sc['grade']}">{sc['grade']}</div><div>
<div style="font-size:18px;font-weight:650">{_e(sc['label'])}</div>
<div class="sub">effort points {sc['points']} · {sc['distinct_rules']} distinct issues · ~{sc['files_to_touch']} files to touch</div>
<div class="chips">{chips or '<span class="chip s-info">no findings</span>'}</div>{link}</div></section>
<section class="card">"""]
    if not items:
        parts.append("<p>No QNX porting issues found.</p>")
    for (sev, rid), fs in items:
        r = kb.RULES_BY_ID[rid]
        files = len({f.file for f in fs})
        rows = []
        for f in sorted(fs, key=lambda f: (f.confidence != "high", f.in_tests, f.file, f.line))[:max_rows]:
            cond = '<span class="cond">conditional</span>' if f.confidence != "high" else ""
            test = '<span class="cond">test/example</span>' if f.in_tests else ""
            note = f'<div class="sub">{_e(f.note)}</div>' if f.note else ""
            rows.append(f'<tr><td class="loc mono">{_e(f.file)}:{f.line}{cond}{test}</td>'
                        f'<td>{_e(f.message)}{note}</td><td class="snip mono">{_e(f.snippet)}</td></tr>')
        more = f'<div class="sub">… and {len(fs) - max_rows} more</div>' if len(fs) > max_rows else ""
        ev = " · ".join(f'<a href="{_e(u)}">{_e(lbl)}</a>' for lbl, u in r.evidence_links())
        parts.append(f"""<details {"open" if sev in ("blocker", "runtime") else ""}><summary>
<span class="chip s-{sev}">{SEV_LABEL[sev]}</span><span class="rid">{rid}</span><span class="t">{_e(r.title)}</span>
<span class="n">{len(fs)} hit{"s" if len(fs) != 1 else ""} · {files} file{"s" if files != 1 else ""}</span></summary>
<div class="body"><div class="why">{_e(r.why)}</div><div class="fix"><b>Fix:</b> {_e(r.fix)}</div>
<table>{"".join(rows)}</table>{more}<div class="ev">Evidence: {ev}</div></div></details>""")
    parts.append(f"""</section><footer>Generated by qnxscout {__version__}. Findings are predictions from static
analysis of the source tree against QNX SDP 8.0 platform facts; every rule links to the QNX documentation or
QNX port patch it is based on. Confirm by building on QNX.</footer></main></body></html>""")
    return "".join(parts)
