# qnxscout

**Know what breaks before you port to QNX 8.0.**

qnxscout reads a C/C++ source tree (or a release tarball) on any host and tells you what will not build, link or behave correctly on QNX 8.0: where, why, how to fix it, and which QNX document or QNX port patch the advice comes from. No QNX SDP is needed to scan. If you have one installed, qnxscout can verify its findings against it.

```
$ qnxscout scan tmux-3.7c.tar.gz
qnxscout: QNX 8.0 port-readiness report for tmux-3.7c
  scanned 200 C/C++ files and 5 build files (autotools) in 3.4s

  Grade D: Significant porting work  (effort points 49.0, 9 distinct issues, ~8 files to touch)

[BLOCKER] QNX030 SA_RESTART is not defined on QNX  (4 hits in 2 files)
    - client.c:561: SA_RESTART is used
[BLOCKER] QNX031 IOV_MAX is not defined on QNX  (4 hits in 1 file)
    - compat/imsg-buffer.c:727: IOV_MAX is used
[BLOCKER] QNX042 forkpty/openpty live in <unix.h> on QNX  (1 hit in 1 file)
    - compat/fdforkpty.c:33: forkpty() is called, but no file includes <unix.h>, where QNX declares it
[RUNTIME] QNX046 flock() is in <fcntl.h> and does not survive fork() on QNX  (1 hit in 1 file)
    - client.c:89: flock() lock in a program that also forks
[LINK] QNX080 Sockets live in libsocket  (1 hit in 1 file)
    - client.c:122: uses socket(), connect(), bind(), listen(); the build only searches for libsocket - QNX ports link -lsocket explicitly even then (conditional)
[LINK] QNX081 POSIX regex lives in libregex  (1 hit in 1 file)
    - format.c:4513: uses regcomp(), regexec(), regfree() but the build never links regex
[REVIEW] QNX063 Per-OS source files have no QNX variant  (1 hit in 1 file)
    - osdep-aix.c:1: osdep-*.c exists for aix, cygwin, darwin, ... but not QNX; generic fallback: osdep-unknown.c (conditional)
[REVIEW] QNX079 Stale config.sub/config.guess  (1 hit in 1 file)
    - etc/config.sub:5: config.sub is from 2017; QNX ports refresh helper scripts this old (conditional)
(abridged: each finding also prints why, fix and evidence links)
```

That is, item for item, what QNX engineers changed to port tmux in [`qnx-ports/aports/extra/tmux`](https://github.com/qnx-ports/aports/tree/main/extra/tmux). qnxscout predicted it from the pristine upstream tarball.

## Why

QNX 8.0 is free for non-commercial use, and QNX is porting the open-source world onto it in the open. [`qnx-ports/aports`](https://github.com/qnx-ports/aports) holds 721 packages and 396 patches. Reading those patches shows that porting friction is not random. The same few dozen differences recur:

* `SA_RESTART`, `IOV_MAX` and `d_type` are missing.
* Sockets live in `libsocket`, POSIX regex in `libregex`, and inotify in `libfsnotify`.
* `forkpty()` exists but is declared in `<unix.h>`.
* `epoll`, `eventfd` and `timerfd` come from QNX compatibility libraries.
* `#if __linux__ / #elif __APPLE__ / #else #error` chains, and CMake files that only know `Linux`, stop the build.

Today you discover them one compile error at a time, on the target. qnxscout tells you all of them up front.

## What it does

* **69 evidence-backed rules.** Every finding links to its source: the [QNX 8.0 C Library Reference](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/about.html), the [QNX Porting Guide](https://www.qnx.com/developers/docs/qnxeverywhere/com.qnx.doc.qpg/topic/about.html), [QNX's own agent skills](https://github.com/qnx/qnx-agent-skills), or the actual patch QNX engineers wrote for the same problem. See [`docs/RULES.md`](docs/RULES.md).
* **Real preprocessor evaluation for QNX.** Lines are classified as *compiled on QNX*, *excluded*, or *depends on build configuration*. This finds `#error`s that QNX reaches, `#else` branches where QNX falls into Windows code, and platform chains with no QNX branch, while staying quiet about code that is already Linux-only or behind a working feature test.
* **Build-system analysis.** CMake and Meson conditions are evaluated as they will run on QNX (`CMAKE_SYSTEM_NAME` is `QNX`, Meson's system is `'qnx'`). That catches `FATAL_ERROR`s QNX reaches, Linux-only branches, `pthread`/`dl`/`util` link items, and C90 builds. Autotools and Makefiles are checked too, including stale `config.sub`.
* **Effort grade A–E**, calibrated against the size of real QNX port patches.
* **SDP verification.** `--sdp $QNX_TARGET` checks findings against your installed SDP's headers and the symbols your target libraries actually export. It reads ELF directly, so it needs no QNX tools.
* **Fits your workflow.** Output is text, HTML, Markdown, JSON or SARIF. A GitHub Action puts QNX issues into Code Scanning, and `--fail-on blocker` gates CI.

## Install

```bash
python3 -m pip install .          # Python 3.9+, no dependencies
```

## Use

```bash
qnxscout scan path/to/project                         # or a .tar.gz / .tar.xz / .zip
qnxscout scan path/to/project -f html -o report.html  # shareable report
qnxscout scan path/to/project -f sarif -o qnx.sarif   # GitHub code scanning / IDEs
qnxscout scan path/to/project --arch aarch64le        # one target architecture
qnxscout scan path/to/project --sdp "$QNX_TARGET"     # verify against your QNX SDP 8.0
qnxscout scan path/to/project --fail-on blocker       # CI gate (exit code 2)
qnxscout explain QNX030                               # why, fix, and evidence for one rule
qnxscout rules                                        # list all rules
```

Severities:

| Severity | Meaning |
|---|---|
| `blocker` | will not compile or link on QNX 8.0 as written |
| `runtime` | builds, but is known to misbehave on QNX |
| `link` | needs a QNX library or link flag, no code change |
| `review` | platform-dependent logic that needs a porting decision |
| `info` | background, e.g. code already behind a feature test |

*Conditional* findings are in code whose QNX status depends on build configuration (a `HAVE_*` macro, an option).

## How well does it work?

[`bench/evaluate.py`](bench/evaluate.py) measures qnxscout against reality. For every package in `qnx-ports/aports` it downloads the pristine upstream source the recipe builds from, scans it, and compares the findings with what QNX engineers changed (their patches, plus the extra link flags and steps in the APKBUILD).

| | |
|---|---|
| QNX ports scanned from pristine upstream source | 609 of 721 |
| Real fixes QNX engineers made (package, issue) | 211 in 135 packages |
| **Predicted by qnxscout before building** | **155 (74%)** |
| ... counting the right file as a hit | 164 (78%) |
| Effort score: needed QNX fixes vs. built unchanged (AUC) | 0.777 |
| Graded **A** (likely builds as-is) and QNX indeed needed no fix | 224 of 232 (97%) |

The ground truth is a conservative lower bound. Some QNX recipe flags are redundant (libuv already links
`socket` in its upstream QNX branch), and a fix QNX made once in a central header counts once. Weak spots are
documented per rule: large-stack detection (only fixed-size arrays of 256 KiB or more) and C-standard detection
(only explicit `-std=c89`-style flags) catch a minority of what QNX fixed. Full per-package results and per-rule
recall are in [`bench/results/`](bench/results/).

## The porting frontier

[`bench/frontier.py`](bench/frontier.py) asks a forward-looking question: *what could QNX port next, and how hard would each package be?* It takes every Alpine package that is not yet in `qnx-ports/aports`, keeps the ones whose dependencies are all already ported, and scans their pristine sources.

Of **4,969** Alpine packages with C/C++-style builds that QNX has not ported yet, **1,559** have every dependency already on QNX. qnxscout scanned 957 of them with C/C++ code: **527** are predicted to be grade A or B (build as-is, or link flags and a few defines).

The ranked list is in [`docs/FRONTIER.md`](docs/FRONTIER.md).

## How it works

| Stage | File | What it does |
|---|---|---|
| Lexer | [`qnxscout/lexer.py`](qnxscout/lexer.py) | Blanks comments and literal contents while keeping every line and column; handles raw strings, digit separators and directive continuations |
| `#if` evaluation | [`qnxscout/ppexpr.py`](qnxscout/ppexpr.py), [`qnxscout/preproc.py`](qnxscout/preproc.py) | Three-valued evaluation with short-circuiting under the QNX 8.0 target model; include guards; project-wide macro inference across headers |
| Knowledge base | [`qnxscout/kb.py`](qnxscout/kb.py), [`qnxscout/data/`](qnxscout/data/) | The rules and target model, plus an index of the 1,947 functions in the QNX 8.0 C Library Reference (header and library for each) |
| C/C++ rules | [`qnxscout/rules_c.py`](qnxscout/rules_c.py) | API, macro, member and header rules; platform-chain analysis; `makedev` arity; `O_DIRECTORY`; procfs paths; stack arrays; feature-test macros |
| Build systems | [`qnxscout/buildsys.py`](qnxscout/buildsys.py) | CMake tokenizer and `if()` evaluator; Meson evaluator; autotools and Makefile checks |
| Scanner | [`qnxscout/scanner.py`](qnxscout/scanner.py) | Two-pass project analysis, per-OS file detection, link-library checks |
| SDP check | [`qnxscout/sdp.py`](qnxscout/sdp.py) | Header and ELF `.dynsym` verification against `$QNX_TARGET` |

## Use in CI

```yaml
# .github/workflows/qnx-readiness.yml
jobs:
  qnxscout:
    runs-on: ubuntu-latest
    permissions: { security-events: write, contents: read }
    steps:
      - uses: actions/checkout@v4
      - uses: OWNER/qnxscout@v0.1.0
      - uses: github/codeql-action/upload-sarif@v3
        with: { sarif_file: qnxscout.sarif }
```

## Tutorial

[`docs/codelab/qnxscout-port-readiness.md`](docs/codelab/qnxscout-port-readiness.md) is a QNX-codelab-format tutorial. It scans tmux, turns the findings into a QNX patch, and builds it on a QNX 8.0 target with `abuild`.

## Limitations

* qnxscout predicts and does not compile. Findings in code whose QNX status depends on build options are marked *conditional*. Use `--sdp` to confirm against your SDP, and always build on QNX.
* It does not model every dependency's headers, so macros defined by third-party libraries are treated as unknown unless they are well known (`G_OS_UNIX`, `Q_OS_QNX`, ...).
* Runtime behaviour beyond the documented pitfalls (timing, scheduling, resource managers) is out of scope.
* The knowledge base reflects QNX SDP 8.0 as documented in November 2026. Rules cite their evidence so they can be re-checked as QNX evolves.

## License

Apache-2.0. QNX is a trademark of BlackBerry Limited. qnxscout is an independent project and is not affiliated with or endorsed by BlackBerry/QNX. The function index in `qnxscout/data` lists only names, header names and library names from the public QNX 8.0 C Library Reference.
