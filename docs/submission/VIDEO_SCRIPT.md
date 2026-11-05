# Demo video: script and voice-over

`docs/video/make_video.py` renders a 2:34 captioned 1080p video (`qnxscout-demo.mp4`) from real tool output and
the benchmark data. Devpost requires a public YouTube video under 3 minutes with no copyrighted music.

The rendered video is silent with on-screen captions. A voice-over makes it stronger. Record the narration below
over the video (the timings match the scenes) with any screen-recorder or video editor, or upload the video as is.

| Time | Scene | Narration (about 150 words per minute) |
|---|---|---|
| 0:00–0:09 | Title | "This is qnxscout: it tells you what will break before you port C or C++ software to QNX 8.0." |
| 0:09–0:25 | The problem | "QNX is porting the open-source world in the open: seven hundred twenty-one packages and almost four hundred patches. Reading those patches, the same problems come back again and again: missing SA_RESTART and IOV_MAX, sockets in libsocket, forkpty in unix.h, and platform checks that only know Linux. Today you find them one compile error at a time, on the target." |
| 0:25–0:47 | Live scan of tmux | "qnxscout runs on any laptop, without the SDP. One command on the pristine tmux tarball: it evaluates every preprocessor branch the way the QNX compiler will, checks the build system, and lists each problem with file, line, and fix." |
| 0:47–1:05 | Prediction vs. QNX's real port | "And it's right. On the left, qnxscout's prediction. On the right, the patch and recipe QNX engineers actually wrote for tmux. Item for item, the same changes. It also stays quiet about FreeBSD-only files, which QNX never compiles." |
| 1:05–1:20 | HTML report | "Results come as a shareable report with an effort grade, or as Markdown, JSON, or SARIF." |
| 1:20–1:34 | Evidence | "Every rule cites its evidence: the QNX 8.0 C Library Reference, the Porting Guide, or a real QNX port patch. We indexed all one thousand nine hundred forty-seven QNX library functions to get headers and libraries right." |
| 1:34–1:54 | Validation | "We measured it against all of QNX's ports: download the pristine source, scan it, and compare with what QNX engineers actually fixed. qnxscout predicts 74% of those fixes before anyone builds anything." |
| 1:54–2:12 | Porting frontier | "Then we turned it forward. 1,559 Alpine packages that QNX hasn't ported yet already have every dependency on QNX. qnxscout ranks them by effort, giving a ready-made backlog for QNX's porting work." |
| 2:12–2:26 | Workflows | "Verify findings against your installed SDP, put it in GitHub code scanning, or follow the codelab from scan to an abuild on a QNX target." |
| 2:26–2:34 | Close | "qnxscout. Predicted work is work you can plan. It's open source under Apache 2." |

## Optional: a short live clip on QNX

If you have the QNX Developer Desktop (QEMU or Raspberry Pi 5), a 10–15 second clip of `abuild -r -c -K` succeeding
for the codelab's tmux package makes a strong addition at 2:12. Keep the total under 3:00.
