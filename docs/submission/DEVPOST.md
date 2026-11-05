# Devpost submission: qnxscout

Paste each section into the matching Devpost field. Placeholders in `{{...}}` are filled from
`bench/results/SUMMARY.md` before submitting.

---

## Project name

qnxscout

## Tagline (Elevator pitch, 200 chars max)

Know what breaks before you port to QNX 8.0. qnxscout reads any C/C++ source tree and predicts the fixes QNX engineers would make, each backed by QNX docs and real QNX port patches.

## Category

Developer Tooling & Host Tools

(Also enter: Best Codelab / Tutorial, with the codelab URL. qnxscout is a host-based tool (Linux, macOS, Windows) that supports software targeting QNX 8.0.)

---

## About the project (Devpost "story", Markdown)

### Inspiration

QNX 8.0 is now free for non-commercial use, and QNX is porting the open-source world onto it in the open: `qnx-ports/aports` already holds **721 packages** and **396 patches**. We read every one of those patches. The same problems come up again and again:

* `SA_RESTART` and `IOV_MAX` are not defined.
* `struct dirent` has no `d_type`.
* Sockets live in `libsocket` and POSIX regex in `libregex`.
* `forkpty()` exists but is declared in `<unix.h>`.
* `#if __linux__ … #elif __APPLE__ … #else #error` chains stop the build.
* CMake files only know `Linux`.

Today each one is discovered one compile error at a time, on the target. We wanted a tool that tells you all of it before you start.

### What it does

`qnxscout scan <dir-or-tarball>` runs on any host and produces a port-readiness report for QNX 8.0:

* **What breaks, where, and why.** {{RULES}} rules cover missing Linux APIs, POSIX gaps, header locations, platform dispatch, build systems and runtime pitfalls. Each finding has a file and line, an explanation, a concrete fix, and **evidence links**: the QNX 8.0 C Library Reference page, the QNX Porting Guide, or the exact patch QNX engineers wrote for the same problem.
* **Effort grade A–E**, calibrated against the size of real QNX port patches.
* **Quick wins first.** It separates true blockers from link-only fixes and lists the link flags you need, such as `-lsocket -lregex -lepoll -leventfd`. Many "missing" Linux APIs are actually available on QNX Everywhere through QNX's compatibility libraries, which the official guide does not mention.
* **Optional SDP verification** (`--sdp $QNX_TARGET`). It checks every finding against your installed QNX SDP's headers and the symbols your target libraries actually export, read directly from ELF.
* **Fits existing workflows.** Output is terminal, HTML, Markdown, JSON or **SARIF**. A GitHub Action shows QNX issues in Code Scanning, and `--fail-on blocker` can gate CI.
* **The porting frontier.** We ran qnxscout over Alpine's package tree. **{{UNPORTED}}** Alpine packages are not yet in `qnx-ports/aports`, and **{{UNBLOCKED}}** of them already have every dependency on QNX. We scanned those and ranked them by predicted effort. The result is a ready-made backlog for QNX's porting effort and for anyone entering the Open-Source Ports category.

### How we built it

qnxscout is pure Python with no dependencies, so it installs anywhere QNX developers work.

1. **A position-preserving C/C++ lexer** blanks out comments and string literals (including raw strings and digit separators) while keeping every line and column, so a match in a comment or `"epoll_wait("` string is never reported.
2. **A three-valued preprocessor evaluator for the QNX 8.0 target.** It knows what QNX's compilers predefine (`__QNX__`, `__unix__`, LP64, little-endian) and what they do not (`__linux__`, `__GLIBC__`, `__APPLE__`, ...). It knows which header macros QNX lacks (`SA_RESTART`, `IOV_MAX`, `SO_PEERCRED`) and which configure results such as `HAVE_EPOLL` or `HAVE_PIPE2` QNX will produce. It also infers project macros (`#define OS_POSIX` under `#if defined(__QNX__) || ...`) across headers. Every line comes out as *compiled on QNX*, *excluded*, or *depends on build configuration*. That's how it finds `#error` directives QNX actually reaches, `#else` branches where QNX falls into Windows code, and platform chains with no QNX branch. Code already guarded by a working feature test is not reported.
3. **An evidence-backed knowledge base.** We indexed all **1,947 functions** in the public QNX 8.0 C Library Reference (header and library for each). That is how we know, for example, that `inotify_init()` exists in `libfsnotify` and `crypt()` in `liblogin`. We mined the 396 QNX port patches and QNX's own agent skills for the platform facts behind each rule. Every rule cites its sources.
4. **CMake and Meson evaluation.** `if()` / `elseif()` chains are evaluated the way they run on QNX, which finds `FATAL_ERROR`s QNX reaches, Linux-only branches, and `pthread`/`dl`/`util` link items QNX does not have. Link checks only count build text QNX actually evaluates. A `socket` library linked in a SunOS-only branch does not count.
5. **A benchmark against reality.** For each of QNX's ports we download the pristine upstream source the recipe builds from, scan it, and compare with the changes QNX engineers made: their patches plus the extra flags and steps in each APKBUILD.

### Validation (from `bench/`)

* Packages evaluated: **{{SCANNED}}** QNX ports scanned from pristine upstream source.
* Ground truth: **{{GT}}** distinct issues QNX engineers fixed in **{{GT_PKGS}}** packages.
* **Recall: {{RECALL}}.** qnxscout predicted that share of them from the pristine source alone, before anyone built anything. With location credit (it flagged the file QNX patched) the figure is **{{RECALL_LOC}}**.
* The effort score separates packages that needed QNX fixes from those that built unchanged with **AUC {{AUC}}**.
* Worked example: for tmux 3.7c qnxscout predicts every change in QNX's port, namely `SA_RESTART`, `IOV_MAX`, `<unix.h>` for `forkpty`, `-lregex`, and the `config.sub` refresh. It correctly stays quiet about FreeBSD-only files and about socket linking, which tmux's configure already handles.

### Challenges we ran into

* **Not crying wolf.** A naive grep for `epoll_wait` flags every project that already supports BSD. Getting precision required real preprocessor evaluation with unknowns that short-circuit correctly (`defined(__linux__) && HAVE_FOO` is known false on QNX), include-guard detection, project-wide macro inference, per-OS source-file detection (`osdep-freebsd.c` is never compiled on QNX), and recognising projects that ship their own fallback implementations.
* **Being right about QNX.** We never mark a function missing just because a grep came up empty. Each "missing" claim is backed by its absence from the QNX 8.0 C Library Reference *and* a QNX port that worked around it. Some of the most valuable facts were counter-intuitive: `inotify` and `forkpty` exist on QNX, just in different places, and `flock()` locks are dropped across `fork()`.
* **Honest ground truth.** QNX's patches are noisy labels. Some APKBUILD flags are redundant (libuv already links `socket` in its upstream QNX branch), and some fixes land in a central header rather than at each call site. We built the benchmark to measure at the issue level and documented its limits.

### Accomplishments that we're proud of

* Predicting real QNX engineering work from pristine source, measured across QNX's whole port tree instead of a hand-picked demo.
* A {{RULES}}-rule knowledge base in which every claim links to public QNX evidence.
* The porting frontier: {{UNBLOCKED}} unblocked Alpine packages, ranked by predicted effort.
* Zero-dependency install, SARIF and GitHub Code Scanning integration, and SDP verification that reads ELF directly.

### What we learned

QNX is far more POSIX-complete than its reputation suggests. Most porting friction is a few dozen recurring, *knowable* differences, plus build systems that only ever imagined Linux, macOS and Windows. That knowledge was scattered across hundreds of patches. Encoding it once makes it reusable by every porter.

### What's next

* Contribute the codelab to `qnx/codelabs`, and propose qnxscout as a pre-flight check for `qnx-ports/aports` pull requests.
* A `--fix` mode that writes the QNX compat header and APKBUILD changes as a draft patch.
* Feeding newly merged QNX ports back into the rule base automatically, so the tool learns as QNX ports more.
* Coverage for QNX-specific opportunities such as suggesting a resource manager where code polls `/sys`.

---

## Built with

python · c · c++ · cmake · meson · autotools · sarif · github-actions · qnx · qnx-sdp-8.0 · alpine-linux

## Try it out (links)

* Repository: `https://github.com/OWNER/qnxscout`
* Codelab: `https://github.com/OWNER/qnxscout/blob/main/docs/codelab/qnxscout-port-readiness.md`

---

## Additional required fields

### Evidence of QNX use (where reviewers can verify the QNX connection)

qnxscout is a host-based developer tool whose output is specifically for building software for QNX 8.0:

* `qnxscout/kb.py` is the QNX 8.0 target model: predefined macros, missing header macros, and the {{RULES}} QNX porting rules with links to QNX documentation and QNX port patches.
* `qnxscout/data/qnx80_libc_index.json` indexes all 1,947 functions of the QNX 8.0 C Library Reference, with header and library for each.
* `qnxscout/preproc.py` evaluates `#if` for a QNX 8.0 target (`__QNX__`, `__QNXNTO__`, `aarch64le`/`x86_64`).
* `qnxscout/buildsys.py` evaluates CMake (`CMAKE_SYSTEM_NAME = QNX`) and Meson (`system = 'qnx'`) as on QNX.
* `qnxscout/sdp.py` verifies findings against an installed QNX SDP 8.0 (`$QNX_TARGET` headers and ELF exports).
* `bench/evaluate.py` validates the tool against `qnx-ports/aports` (QNX's own ports).
* `docs/codelab/qnxscout-port-readiness.md` is a QNX 8.0 codelab that ends with an `abuild` build on a QNX target.

### Build and run instructions

* QNX version: QNX SDP 8.0 (QNX Everywhere). qnxscout analyses software targeting QNX 8.0.
* Target: host tool. It runs on Linux, macOS or Windows (Python 3.9+). Optional `--sdp` uses an installed QNX SDP 8.0. The codelab builds the scanned package on a QNX 8.0 target (QEMU or Raspberry Pi) with `abuild`.
* Toolchain: Python 3.9+ standard library only. For the on-target build in the codelab, the QNX Developer Desktop toolchain and `abuild`.

```bash
git clone https://github.com/OWNER/qnxscout && cd qnxscout
python3 -m pip install .
qnxscout scan path/to/project              # or a .tar.gz
qnxscout scan path/to/project -f html -o report.html
qnxscout scan path/to/project --sdp "$QNX_TARGET"   # optional, with QNX SDP 8.0 installed
python3 -m unittest discover -s tests             # test suite
```
