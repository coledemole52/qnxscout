# Demo video source

`build_demo.py` is the final narrated 1080p demo renderer. It adapts the original `make_video.py` story and visual direction, and records an actual installed CLI scan using an isolated browser console. The console is capture equipment; QNXScout remains a command-line tool.

On Windows, install Python 3.9+, Node.js, FFmpeg, Pillow, and Playwright. The renderer uses the installed Microsoft Zira Desktop voice and Segoe UI/Consolas fonts. It has no paid services or music.

```sh
python -m pip install . pillow
npm install playwright
npx playwright install chromium
python docs/video/build_demo.py --tmux path/to/tmux-3.7c.tar.gz --out-dir dist/demo
```

Run from the repository root. If Node cannot resolve Playwright from the temporary recording script, set `QNXSCOUT_PLAYWRIGHT_MODULE` to the absolute installed `playwright` module directory. `QNXSCOUT_CHROMIUM` optionally selects an installed Chromium executable. The renderer writes intermediate assets into `.cache/demo`.

The final video is 148.99 seconds, H.264/AAC, 1920×1080 at 30 fps. It includes synthetic narration, a real Windows host scan of pristine tmux 3.7c, a concrete `SA_RESTART` finding, and explicit historical-benchmark limits. No QNX target execution is claimed.

Upstream archive: https://github.com/tmux/tmux/releases/download/3.7c/tmux-3.7c.tar.gz

Archive SHA-256: `7c60cae9a0e25288e2e24750aafc9e8800fc7fd4555e447e1b29ee4201cfb3bf`.

The original silent slide renderer is retained as `make_video.py` for provenance. Its older visuals are not the final competition video. See the final transcript in `../submission/VIDEO_SCRIPT.md`.
