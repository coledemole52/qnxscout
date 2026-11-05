"""Rebuild demo with a real CLI run recorded in a local capture console.
Visual direction and story adapted from docs/video/make_video.py and VIDEO_SCRIPT.md.
No target-build or prospective benchmark claim is made.
"""
from pathlib import Path
import argparse, json, os, shutil, subprocess, sys, threading, time, html
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from PIL import Image, ImageDraw, ImageFont

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--tmux',required=True,type=Path)
parser.add_argument('--out-dir',type=Path,default=Path('dist/demo'))
args=parser.parse_args()
BASE=Path(__file__).resolve().parents[2]
W=BASE/'.cache/demo';W.mkdir(parents=True,exist_ok=True)
OUT=args.out_dir.resolve();OUT.mkdir(parents=True,exist_ok=True)
REPO=BASE
NODE=shutil.which('node')
PW=os.environ.get('QNXSCOUT_PLAYWRIGHT_MODULE','playwright')
CHROME=os.environ.get('QNXSCOUT_CHROMIUM','')
FF='ffmpeg'
scenes=[
 ('QNXScout','Find porting friction\nbefore the first build.', ['QNX 8.0 • Developer Tooling & Host Tools','C/C++ source → locations, fixes, evidence','Python 3.9+ • Apache-2.0 • no runtime dependencies'],
  'QNX Scout is a host tool for developers targeting QNX eight. It scans C and C plus plus source before the first build, and turns familiar porting problems into a practical review list.'),
 ('THE PROBLEM','A Linux build hides\nQNX-specific assumptions.', ['Missing macros: SA_RESTART and IOV_MAX','Different headers: forkpty in <unix.h>','Different link libraries: socket and regex'],
  'Porting often starts with repeated build failures. A familiar function may need a different header, a separate library, or a QNX specific replacement. QNX Scout brings those known differences into the first review.'),
 ('LIVE HOST DEMO','',[],
  'This is an actual QNX Scout process running on Windows against the pristine tmux three point seven c release archive. The source is scanned now. The report identifies source locations, suggested fixes, and links to the QNX evidence behind each rule. No QNX software development platform is required for this static scan.'),
 ('A REAL COMPATIBILITY ISSUE','SA_RESTART is not\ndefined on QNX.', ['tmux client.c:561 uses SA_RESTART','QNX030 identifies the use and explains why','Review the QNX-specific signal handling fix'],
  'Here is one concrete issue. Tmux uses S A restart in client dot c. QNX Scout flags it because that macro is not defined on QNX. Instead of a bare error message, the finding explains the compatibility issue and points to the documented porting fix.'),
 ('FROM FINDING TO ACTION','A report you can\nreview and share.', ['Each finding: file + line → why → fix → evidence','HTML for review • JSON for automation • SARIF for CI','Optional SDP verification against headers and ELF exports'],
  'The result is a review artifact. Developers can inspect the exact source location, follow the evidence, and decide on a fix. HTML makes it shareable; SARIF fits code scanning. Optional S D P verification checks installed headers and exported symbols. A grade is an effort heuristic, not proof of a successful QNX build.'),
 ('MEASURED, WITH LIMITS','155 / 211\n73.5% historical recall', ['609 pristine-source packages in saved benchmark','Denominator: identified, rule-mappable historical issues','Retrospective labels • ports informed rule development'],
  'The saved benchmark covers six hundred and nine packages. Same rule matches cover one hundred fifty five of two hundred eleven identified historical issues, or seventy three point five percent. Those labels use the rule vocabulary, and ports informed development. This does not measure every engineering modification or prove future accuracy.'),
 ('OPEN SOURCE + CODELAB','Try it on your\nnext QNX port.', ['github.com/coledemole52/qnxscout','Install → scan → inspect evidence → build and test','QNX 8.0 tutorial included • host tool verified on Windows'],
  'The repository includes source, tests, reports, and a QNX eight port readiness tutorial. Install, scan, inspect the evidence, then build and test on your target. This release demonstrates the host scanner; it does not claim an executed QNX target build. Start with the public repository linked below.'),
]
def font(n,bold=False,mono=False):
    return ImageFont.truetype('C:/Windows/Fonts/'+('consola.ttf' if mono else 'segoeuib.ttf' if bold else 'segoeui.ttf'),n)
for i,(tag,title,lines,narration) in enumerate(scenes):
    im=Image.new('RGB',(1920,1080),'#0d1117');d=ImageDraw.Draw(im)
    d.rectangle((0,0,18,1080),fill='#6ea8ff');d.text((110,90),tag,font=font(30,True),fill='#6ea8ff')
    d.multiline_text((110,190),title,font=font(88,True),fill='#e6edf3',spacing=10)
    y=510
    for line in lines:
        d.text((115,y),'• '+line,font=font(35),fill='#c9d1d9');y+=83
    d.line((110,940,1810,940),fill='#30363d',width=2)
    d.text((110,978),'QNXScout  /  QNX 8.0 port-readiness',font=font(25),fill='#8b949e')
    d.text((1730,978),f'{i+1:02d} / 07',font=font(25),fill='#8b949e')
    im.save(W/f'{i}.png');(W/f'{i}.txt').write_text(narration,encoding='utf-8')
# Offline, installed system voice. No account, paid service or music.
ps='''Add-Type -AssemblyName System.Speech
$speaker=New-Object System.Speech.Synthesis.SpeechSynthesizer
$speaker.SelectVoice('Microsoft Zira Desktop')
$speaker.Rate=0
Get-ChildItem -LiteralPath '%s' -Filter '*.txt' | ForEach-Object {
 $speaker.SetOutputToWaveFile([IO.Path]::ChangeExtension($_.FullName,'.wav'))
 $speaker.Speak([IO.File]::ReadAllText($_.FullName))
 $speaker.SetOutputToNull()
}
$speaker.Dispose()
''' % str(W).replace("'","''")
(W/'voice.ps1').write_text(ps,encoding='utf-8')
subprocess.run(['powershell','-NoProfile','-Command',ps],check=True)
state={'text':'Ready. Click Run scan to launch the installed CLI.','done':False}
def runscan():
    state['text']='> qnxscout scan tmux-3.7c.tar.gz\n\nScanning pristine upstream source...\n'
    p=subprocess.Popen([sys.executable,'-m','qnxscout','scan',str(args.tmux.resolve())],cwd=REPO,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8')
    text=p.communicate()[0];state['text']='> qnxscout scan tmux-3.7c.tar.gz\n\n'+text;state['done']=True
    (W/'live-output.txt').write_text(text,encoding='utf-8')
PAGE='''<!doctype html><style>*{box-sizing:border-box}body{margin:0;background:#0d1117;color:#e6edf3;font-family:Segoe UI,sans-serif;padding:55px 85px}h1{font-size:38px;margin:0 0 10px}.sub{font-size:25px;color:#8b949e}button{margin:22px 0;background:#6ea8ff;color:#010409;border:0;border-radius:8px;padding:14px 26px;font-size:24px}pre{height:760px;overflow:auto;background:#010409;padding:28px;border:1px solid #30363d;border-radius:14px;font:23px/1.42 Consolas,monospace;white-space:pre-wrap}#badge{color:#7ee787;margin-left:25px;font-size:24px}</style><h1>QNXScout — live host scan</h1><div class=sub>Windows / installed Python CLI / pristine tmux 3.7c / QNX 8.0 target model</div><button onclick="fetch('/run',{method:'POST'});this.disabled=true">Run scan</button><span id=badge>Ready</span><pre id=log></pre><script>setInterval(async()=>{const x=await(await fetch('/state')).json();document.querySelector('#log').textContent=x.text;document.querySelector('#badge').textContent=x.done?'Scan complete — actual process output':'Host scanner';},200)</script>'''
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        b=json.dumps(state).encode() if self.path=='/state' else PAGE.encode();self.send_response(200);self.send_header('Content-Type','application/json; charset=utf-8' if self.path=='/state' else 'text/html; charset=utf-8');self.end_headers();self.wfile.write(b)
    def do_POST(self):
        threading.Thread(target=runscan,daemon=True).start();self.send_response(200);self.end_headers()
    def log_message(self,*a):pass
server=ThreadingHTTPServer(('127.0.0.1',8786),H);threading.Thread(target=server.serve_forever,daemon=True).start()
js='''const {chromium}=require(%s);(async()=>{const b=await chromium.launch(%s ? {executablePath:%s} : {});const c=await b.newContext({viewport:{width:1920,height:1080},recordVideo:{dir:%s,size:{width:1920,height:1080}}});const p=await c.newPage();await p.goto('http://127.0.0.1:8786');await p.waitForTimeout(1200);await p.getByRole('button',{name:'Run scan',exact:true}).click();await p.getByText('Scan complete — actual process output',{exact:true}).waitFor();await p.screenshot({path:%s});await p.waitForTimeout(7000);await p.locator('pre').evaluate(el=>{el.scrollTop=500});await p.waitForTimeout(6000);await p.locator('pre').evaluate(el=>{el.scrollTop=1000});await p.waitForTimeout(6000);await p.locator('pre').evaluate(el=>{el.scrollTop=0});await p.waitForTimeout(10000);const v=p.video();await c.close();await v.saveAs(%s);await b.close();})();''' % tuple(json.dumps(x) for x in [PW,CHROME,CHROME,str(W/'capture'),str(W/'live.png'),str(W/'live.webm')])
(W/'record.cjs').write_text(js,encoding='utf-8');subprocess.run([str(NODE),str(W/'record.cjs')],check=True);server.shutdown()
import wave
parts=[];durations=[]
for i in range(len(scenes)):
    with wave.open(str(W/f'{i}.wav')) as a: duration=a.getnframes()/a.getframerate()+1.5
    durations.append(duration);seg=W/f'part{i}.mp4'
    source=['-stream_loop','-1','-i',str(W/'live.webm')] if i==2 else ['-loop','1','-i',str(W/f'{i}.png')]
    subprocess.run([FF,'-y','-loglevel','error',*source,'-i',str(W/f'{i}.wav'),'-t',str(duration),'-vf','scale=1920:1080,setsar=1,format=yuv420p','-r','30','-c:v','libx264','-preset','fast','-crf','21','-c:a','aac','-ar','48000','-ac','2',str(seg)],check=True);parts.append(seg)
assert sum(durations)<180,sum(durations)
(W/'concat.txt').write_text(''.join("file '"+p.as_posix()+"'\n" for p in parts),encoding='utf-8')
subprocess.run([FF,'-y','-loglevel','error','-f','concat','-safe','0','-i',str(W/'concat.txt'),'-c','copy','-movflags','+faststart',str(OUT/'qnxscout-demo.mp4')],check=True)
(OUT/'demo-transcript.txt').write_text('\n\n'.join(s[3] for s in scenes),encoding='utf-8')
print('VIDEO COMPLETE',sum(durations),durations)

