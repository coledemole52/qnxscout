#!/usr/bin/env python3
"""Render the < 3 minute demo video from real qnxscout output.

Scenes are HTML pages (1920x1080) rendered to PNG with headless Chromium
(Playwright), then assembled with ffmpeg (fade in/out per scene, no audio;
narration lines are in VIDEO_SCRIPT.md for an optional voice-over).

  python3 docs/video/make_video.py --tmux path/to/tmux-3.7c.tar.gz \\
      --bench bench/results/results.json --frontier bench/results/frontier.json --out qnxscout-demo.mp4
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

W, H = 1920, 1080
BASE_CSS = """
*{box-sizing:border-box;margin:0}body{width:1920px;height:1080px;background:#0d1117;color:#e6edf3;
font-family:Inter,'Segoe UI',Roboto,system-ui,sans-serif;overflow:hidden}
.wrap{padding:90px 120px;height:100%;display:flex;flex-direction:column}
.kicker{color:#6ea8ff;font-size:30px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;margin-bottom:22px}
h1{font-size:84px;line-height:1.08;font-weight:800;letter-spacing:-.02em}
h2{font-size:58px;line-height:1.12;font-weight:750;margin-bottom:34px;letter-spacing:-.01em}
p,li{font-size:34px;line-height:1.45;color:#c9d1d9}ul{padding-left:40px}li{margin:8px 0}
.mono,pre{font-family:'JetBrains Mono','Fira Code',Menlo,Consolas,monospace}
pre{font-size:25px;line-height:1.42;white-space:pre-wrap}
.term{background:#010409;border:1px solid #30363d;border-radius:18px;padding:34px 40px;flex:1;overflow:hidden}
.bar{display:flex;gap:10px;margin-bottom:22px}.bar i{width:16px;height:16px;border-radius:50%;background:#30363d;display:block}
.b{color:#ff7b72;font-weight:700}.r{color:#d2a8ff;font-weight:700}.l{color:#e3b341;font-weight:700}
.v{color:#56d4dd;font-weight:700}.g{color:#7ee787}.d{color:#8b949e}.w{color:#ffffff;font-weight:700}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:40px;flex:1}
.card{background:#161b22;border:1px solid #30363d;border-radius:18px;padding:30px 34px}
.card h3{font-size:32px;margin-bottom:16px;color:#e6edf3}
.ok{color:#7ee787;font-weight:800;margin-right:12px}
.big{font-size:150px;font-weight:850;line-height:1;color:#7ee787}
.stat{display:flex;gap:60px;margin:20px 0 34px}.stat div{min-width:300px}
.stat b{display:block;font-size:96px;font-weight:850;line-height:1}.stat span{font-size:28px;color:#8b949e}
.caption{position:absolute;left:0;right:0;bottom:0;padding:22px 120px;background:rgba(1,4,9,.86);
border-top:1px solid #30363d;font-size:31px;color:#e6edf3}
table{border-collapse:collapse;width:100%}td{font-size:28px;padding:9px 12px;border-bottom:1px solid #21262d}
.barrow{display:grid;grid-template-columns:420px 1fr 120px;gap:18px;align-items:center;margin:9px 0}
.barrow .lbl{font-size:26px;color:#c9d1d9}.track{height:26px;background:#21262d;border-radius:6px;overflow:hidden}
.fill{height:100%;background:linear-gradient(90deg,#2f81f7,#7ee787)}.pct{font-size:26px;text-align:right}
.logo{font-family:'JetBrains Mono',monospace;color:#6ea8ff}
"""


def page(body: str, caption: str = "") -> str:
    cap = f'<div class="caption">{caption}</div>' if caption else ""
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{BASE_CSS}</style></head><body>{body}{cap}</body></html>"


def colorize(text: str) -> str:
    out = []
    for line in text.split("\n"):
        e = html.escape(line)
        e = re.sub(r"^\[BLOCKER\]", '<span class="b">[BLOCKER]</span>', e)
        e = re.sub(r"^\[RUNTIME\]", '<span class="r">[RUNTIME]</span>', e)
        e = re.sub(r"^\[LINK\]", '<span class="l">[LINK]</span>', e)
        e = re.sub(r"^\[REVIEW\]", '<span class="v">[REVIEW]</span>', e)
        e = re.sub(r"(Grade [A-E]: [^(]*)", r'<span class="w">\1</span>', e)
        e = re.sub(r"^(\s+- )(\S+:\d+)", r'\1<span class="g">\2</span>', e)
        out.append(e)
    return "\n".join(out)


def scenes(data: dict) -> list:
    S = []
    S.append((page(f"""<div class="wrap" style="justify-content:center">
<div class="kicker">QNX Global Hackathon 2026 · Developer Tooling &amp; Host Tools</div>
<h1><span class="logo">qnxscout</span><br>Know what breaks before you<br>port to QNX 8.0</h1>
<p style="margin-top:36px;font-size:38px">A port-readiness scanner for C/C++ code, backed by QNX's own documentation and ports.</p>
</div>"""), 9))
    S.append((page("""<div class="wrap"><div class="kicker">The problem</div>
<h2>QNX is porting the open-source world.<br>The same problems keep coming back.</h2>
<div class="stat"><div><b>721</b><span>packages in qnx-ports/aports</span></div><div><b>396</b><span>patches QNX engineers wrote</span></div></div>
<ul><li><span class="mono">SA_RESTART</span>, <span class="mono">IOV_MAX</span>, <span class="mono">d_type</span> are missing</li>
<li>sockets in <span class="mono">libsocket</span>, regex in <span class="mono">libregex</span>, <span class="mono">forkpty()</span> in <span class="mono">&lt;unix.h&gt;</span></li>
<li><span class="mono">#if __linux__ … #else #error</span> and CMake files that only know Linux</li></ul>
<p style="margin-top:24px">Today: discovered one compile error at a time, on the target.</p></div>""",
                   "Porting friction is not random: it is a few dozen recurring, knowable differences."), 16))
    S.append((page(f"""<div class="wrap"><div class="kicker">Demo · any laptop, no SDP needed</div>
<div class="term"><div class="bar"><i></i><i></i><i></i></div><pre><span class="g">$</span> qnxscout scan tmux-3.7c.tar.gz
{colorize(data['tmux_text'])}</pre></div></div>""",
                   "One command on the pristine upstream tarball: every issue, with file and line, before you build."), 22))
    pred = "".join(f'<li><span class="ok">✓</span>{x}</li>' for x in [
        "SA_RESTART not defined", "IOV_MAX not defined → UIO_MAXIOV", "forkpty() needs &lt;unix.h&gt;",
        "link -lregex", "link -lsocket", "refresh config.sub"])
    S.append((page(f"""<div class="wrap"><div class="kicker">Checked against reality</div>
<h2>qnxscout's prediction vs. QNX's real tmux port</h2><div class="cols">
<div class="card"><h3>qnxscout (pristine source)</h3><ul style="list-style:none;padding:0">{pred}</ul></div>
<div class="card"><h3>qnx-ports/aports/extra/tmux</h3><pre style="font-size:22px">{html.escape(data['tmux_patch'])}</pre></div>
</div></div>""", "Item for item, the changes QNX engineers made. And no noise from FreeBSD-only files."), 18))
    S.append((page(f"""<div class="wrap" style="padding:60px 120px"><div class="kicker">Shareable HTML report</div>
<img src="file://{data['report_png']}" style="width:100%;border-radius:14px;border:1px solid #30363d"></div>""",
                   "Grade A–E, severity, why, fix, and the exact lines. Also Markdown, JSON and SARIF."), 15))
    S.append((page(f"""<div class="wrap"><div class="kicker">Every rule cites its evidence</div>
<div class="term"><div class="bar"><i></i><i></i><i></i></div><pre><span class="g">$</span> qnxscout explain QNX030
{html.escape(data['explain'])}</pre></div></div>""",
                   f"{data['rules']} rules, each linked to the QNX 8.0 C Library Reference, the Porting Guide, or a QNX port patch."), 14))
    bars = "".join(f'<div class="barrow"><div class="lbl mono">{html.escape(lbl)}</div><div class="track">'
                   f'<div class="fill" style="width:{pct:.0f}%"></div></div><div class="pct">{pct:.0f}%</div></div>'
                   for lbl, pct in data["bars"])
    S.append((page(f"""<div class="wrap"><div class="kicker">Validated on QNX's own ports</div>
<h2>Does it predict what QNX engineers actually fixed?</h2>
<div class="stat"><div><b>{data['recall']}</b><span>of {data['gt']} real QNX fixes predicted<br>from pristine source</span></div>
<div><b>{data['scanned']}</b><span>QNX ports scanned</span></div><div><b>{data['auc']}</b><span>AUC: effort score separates<br>packages that needed fixes</span></div></div>
{bars}</div>""", "Benchmark: pristine upstream source vs. the patches and recipe changes in qnx-ports/aports."), 20))
    rows = "".join(f"<tr><td class='mono'>{html.escape(r['package'])}</td><td>{r['grade']}</td><td class='d'>"
                   f"{html.escape((r.get('description') or '')[:70])}</td></tr>" for r in data["frontier_top"])
    S.append((page(f"""<div class="wrap"><div class="kicker">The porting frontier</div>
<h2>{data['unblocked']} Alpine packages could be ported next.<br>Here are the easiest.</h2>
<table>{rows}</table></div>""",
                   f"{data['unported']} Alpine packages are not on QNX yet; {data['unblocked']} already have every dependency ported. qnxscout ranks them."), 18))
    S.append((page("""<div class="wrap"><div class="kicker">Fits real workflows</div>
<h2>From laptop to CI to SDP</h2><div class="cols">
<div class="card"><h3>Verify against your SDP</h3><pre>qnxscout scan . --sdp $QNX_TARGET</pre>
<p style="margin-top:14px">Checks headers and ELF-exported symbols of your installed QNX SDP 8.0.</p></div>
<div class="card"><h3>GitHub Code Scanning</h3><pre>qnxscout scan . -f sarif
qnxscout scan . --fail-on blocker</pre><p style="margin-top:14px">SARIF + GitHub Action; gate PRs on QNX portability.</p></div>
<div class="card"><h3>Codelab</h3><p>Scan tmux, write one QNX patch, build it on QNX 8.0 with <span class="mono">abuild</span>.</p></div>
<div class="card"><h3>Zero dependencies</h3><p>Pure Python 3.9+. Linux, macOS, Windows.</p></div></div></div>"""), 14))
    S.append((page("""<div class="wrap" style="justify-content:center"><h1><span class="logo">qnxscout</span></h1>
<p style="font-size:44px;margin-top:20px">Predicted work is work you can plan.</p>
<p style="margin-top:40px" class="mono">github.com/OWNER/qnxscout · Apache-2.0</p></div>"""), 8))
    return S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmux", required=True)
    ap.add_argument("--tmux-patch", required=True)
    ap.add_argument("--bench", required=True)
    ap.add_argument("--frontier", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--repo-owner", default="OWNER")
    a = ap.parse_args()
    from qnxscout.report import html as html_report, text
    from qnxscout.scanner import scan
    from qnxscout import kb
    from qnxscout.cli import _extract_archive
    work = tempfile.mkdtemp(prefix="qnxvideo-")
    src = _extract_archive(a.tmux) if os.path.isfile(a.tmux) else a.tmux
    res = scan(src)
    res.root = "tmux-3.7c"
    full = text.render(res, color=False, max_per_rule=2)
    keep = []
    for line in full.split("\n"):
        if line.startswith("    why:") or line.startswith("    fix:") or line.startswith("    evidence:") or \
                line.startswith("  findings:") or line.startswith("  QNX link") or line.strip().startswith("... and"):
            continue
        keep.append(line)
    tmux_text = "\n".join(l for l in keep if l.strip() != "")
    report_html = os.path.join(work, "report.html")
    with open(report_html, "w") as fh:
        fh.write(html_report.render(res))
    report_png = os.path.join(work, "report.png")
    explain = subprocess.run([sys.executable, "-m", "qnxscout", "explain", "QNX030"], capture_output=True,
                             text=True, cwd=ROOT).stdout
    bench = json.load(open(a.bench))["summary"]
    fr = json.load(open(a.frontier))
    per = bench["per_rule"]
    bars = []
    for rid, d in sorted(per.items(), key=lambda kv: -kv[1]["gt"]):
        if d["gt"] >= 3:
            bars.append((f"{rid} {kb.RULES_BY_ID[rid].title[:28]}", 100.0 * d["hit"] / d["gt"]))
    bars = bars[:7]
    top = [r for r in fr["results"] if r.get("status") == "ok" and (r.get("c_files") or 0) >= 10][:9]
    for r in top:
        r["grade"] = r["score"]["grade"]
    data = {
        "tmux_text": tmux_text, "tmux_patch": open(a.tmux_patch).read().split("@@", 2)[-1][-900:],
        "report_png": report_png, "explain": explain, "rules": len(kb.RULES),
        "recall": f"{round(100 * bench['recall'])}%", "gt": bench["ground_truth_issues"],
        "scanned": bench["packages_scanned"], "auc": bench.get("auc_effort_score") or "n/a", "bars": bars,
        "frontier_top": top, "unblocked": fr["unblocked"], "unported": fr["unported_candidates"],
    }
    pages = scenes(data)
    js = os.path.join(work, "shot.js")
    with open(js, "w") as fh:
        fh.write("""const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await b.newPage({viewport:{width:1920,height:1080}});
for (const [src, out] of JSON.parse(process.argv[2])) { await p.goto('file://' + src); await p.waitForTimeout(150);
await p.screenshot({path: out}); } await b.close(); })();""")
    # first the HTML report screenshot (light theme looks best on the dark slide)
    rep_js = os.path.join(work, "rep.js")
    with open(rep_js, "w") as fh:
        fh.write("""const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await b.newPage({viewport:{width:1500,height:760},
colorScheme:'light', deviceScaleFactor: 1.25}); await p.goto('file://' + process.argv[2]);
await p.screenshot({path: process.argv[3]}); await b.close(); })();""")
    subprocess.run(["node", rep_js, report_html, report_png], check=True)
    jobs = []
    for i, (doc, _dur) in enumerate(pages):
        hp = os.path.join(work, f"s{i:02d}.html")
        doc = doc.replace("OWNER", a.repo_owner)
        with open(hp, "w") as fh:
            fh.write(doc)
        jobs.append([hp, os.path.join(work, f"s{i:02d}.png")])
    subprocess.run(["node", js, json.dumps(jobs)], check=True)
    parts = []
    for i, (_doc, dur) in enumerate(pages):
        seg = os.path.join(work, f"s{i:02d}.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-t", str(dur), "-i", jobs[i][1],
                        "-vf", f"fade=t=in:st=0:d=0.5,fade=t=out:st={dur - 0.5}:d=0.5,format=yuv420p",
                        "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "20", seg], check=True)
        parts.append(seg)
    lst = os.path.join(work, "list.txt")
    with open(lst, "w") as fh:
        fh.write("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-c", "copy", "-movflags", "+faststart", a.out], check=True)
    for i, (_hp, png) in enumerate(jobs):
        shutil.copy(png, os.path.splitext(a.out)[0] + f"-scene{i:02d}.png")
    print(f"wrote {a.out} ({sum(d for _x, d in pages)} s)")


if __name__ == "__main__":
    main()
