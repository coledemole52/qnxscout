id: qnxscout-port-readiness
title: Predict QNX 8.0 Porting Work Before You Build, with qnxscout
summary: Scan a Linux C/C++ project on your laptop, see exactly what will break on QNX 8.0 and why, then fix it and build it on a QNX target. Worked example - tmux.
categories: qnx, porting, alpine, tools
tags: beginner
difficulty: 2
status: draft
authors: qnxscout contributors
feedback_link: https://github.com/qnx/codelabs/issues

# Predict QNX 8.0 Porting Work Before You Build, with qnxscout

## Introduction

Porting a Linux program to QNX 8.0 usually goes like this: copy the build recipe, start a build on the target, hit an error, fix it, rebuild, hit the next error. Most of those errors are well known to QNX porters - `SA_RESTART` is not defined, sockets live in `libsocket`, `forkpty()` is declared in `<unix.h>` - but you only discover them one compile at a time.

**qnxscout** is a free, open-source host tool that reads a source tree and tells you up front what will break on QNX 8.0, where, why, and how QNX's own engineers fixed the same problem in other packages. It runs on Linux, macOS or Windows with plain Python. No QNX SDP is needed to scan, and it can optionally verify its findings against your SDP.

In this codelab you will reproduce QNX's real port of **tmux** (it lives in `qnx-ports/aports` as `extra/tmux`), but you will know every change you need before you compile a single file.

**What you will learn:**

* How to run a QNX 8.0 port-readiness scan on any C/C++ source tree or tarball
* How to read the findings and the evidence behind each one
* How to turn the findings into a single, upstream-friendly QNX patch and APKBUILD changes
* How to build the result on a QNX 8.0 target with `abuild`
* How to verify findings against your installed SDP, and how to add the scan to CI

**Prerequisites:**

* Any host with Python 3.9 or newer (for the scan)
* For the build steps: a QNX 8.0 target with the QNX Developer Desktop and a working `abuild` environment, as set up in the codelab *Porting an Alpine Linux Package to QNX 8.0*
* Optional: QNX SDP 8.0 installed through QNX Everywhere (for `--sdp` verification)

---

## How it works - Overview

qnxscout does not grep for scary function names. It:

1. **Lexes** every C/C++ file so comments, string literals and `#if 0` blocks never produce findings.
2. **Evaluates the preprocessor for a QNX 8.0 target.** It knows what the QNX compilers predefine (`__QNX__`, `__unix__`, 64-bit, little-endian) and what they do not (`__linux__`, `__GLIBC__`, ...), and which configure results such as `HAVE_EPOLL` or `HAVE_PIPE2` will come out on QNX. Every line is classified as *compiled on QNX*, *not compiled*, or *depends on build configuration*.
3. **Applies 68 rules**, each backed by public evidence: the QNX 8.0 C Library Reference, the QNX Porting Guide, QNX's own agent skills, or a patch QNX engineers wrote in `qnx-ports/aports`.
4. **Evaluates CMake and Meson conditions** the way they will run on QNX (`CMAKE_SYSTEM_NAME` is `QNX`, Meson's system is `qnx`) to find Linux-only branches, `FATAL_ERROR`s that QNX reaches, and libraries QNX does not have (`pthread`, `dl`, `util`).
5. **Scores** the result from A (likely builds as-is) to E (major porting effort).

---

## Step 1 - Install qnxscout

On your host:

```bash
git clone https://github.com/OWNER/qnxscout.git
cd qnxscout
python3 -m pip install .
qnxscout --version
```

Replace `OWNER` with the account that hosts qnxscout. qnxscout has no dependencies outside the Python standard library.

---

## Step 2 - Get the pristine upstream source

Download exactly the tarball the QNX recipe builds from, without any QNX patches applied:

```bash
curl -LO https://github.com/tmux/tmux/releases/download/3.7c/tmux-3.7c.tar.gz
```

qnxscout can scan the archive directly, or you can extract it first. Both work.

---

## Step 3 - Scan

```bash
qnxscout scan tmux-3.7c.tar.gz
```

You will see a report like this (abridged):

```
qnxscout: QNX 8.0 port-readiness report for tmux-3.7c
  scanned 200 C/C++ files and 5 build files (autotools) in 2.9s

  Grade D: Significant porting work  (effort points 47.5, 8 distinct issues)

[BLOCKER] QNX030 SA_RESTART is not defined on QNX  (4 hits in 2 files)
    - client.c:561: SA_RESTART is used
    - proc.c:250: SA_RESTART is used
[BLOCKER] QNX031 IOV_MAX is not defined on QNX  (4 hits in 1 file)
    - compat/imsg-buffer.c:727: IOV_MAX is used
[BLOCKER] QNX042 forkpty/openpty live in <unix.h> on QNX  (1 hit in 1 file)
    - compat/fdforkpty.c:33: forkpty() is called, but no file includes <unix.h>, where QNX declares it
[RUNTIME] QNX046 flock() is in <fcntl.h> and does not survive fork() on QNX
    - client.c:89: flock() lock in a program that also forks
[LINK] QNX081 POSIX regex lives in libregex
    - format.c:4513: uses regcomp(), regexec(), regfree() but the build never links regex
[REVIEW] QNX079 Stale config.sub/config.guess
    - etc/config.sub:5: config.sub is from 2017; QNX ports refresh helper scripts this old
```

For a shareable report, write HTML instead:

```bash
qnxscout scan tmux-3.7c.tar.gz -f html -o tmux-qnx.html
```

---

## Step 4 - Understand the findings

Every finding comes with *why*, *fix*, and *evidence*. To read one in full:

```bash
qnxscout explain QNX030
```

For tmux the findings map to concrete work:

| Finding | What it means on QNX 8.0 | Fix |
| :--- | :--- | :--- |
| QNX030 `SA_RESTART` | QNX does not define it; five QNX ports add a fallback | `#define SA_RESTART 0` when undefined |
| QNX031 `IOV_MAX` | Not defined on QNX | use `UIO_MAXIOV` from `<sys/uio.h>` |
| QNX042 `forkpty()` | Implemented in QNX libc, but declared in `<unix.h>` | include `<unix.h>` on QNX |
| QNX081 `regcomp()` | POSIX regex is in `libregex`, not libc | link `-lregex` |
| QNX079 `config.sub` | 2017 helper script | refresh it (`update_config_sub`) |
| QNX046 `flock()` | QNX drops a parent's `flock()` across `fork()` | review: tmux's server lock file |

Notice what is *not* reported. tmux's `osdep-freebsd.c` includes FreeBSD-only headers, but qnxscout knows that file is only compiled on FreeBSD. It instead tells you (QNX063) that tmux picks `osdep-*.c` per OS and will fall back to `osdep-unknown.c` on QNX. Socket linking is not reported either, because tmux's `configure.ac` already searches for `socket()` with `AC_SEARCH_LIBS`.

---

## Step 5 - Write one QNX patch

All three source findings belong in tmux's central compatibility header, `compat.h`, gated on `__QNX__` so other platforms are untouched. This is the shape that upstream maintainers accept.

On your QNX target, inside your `qnx-ports/aports` checkout, follow the patch workflow from *Porting an Alpine Linux Package to QNX 8.0*:

```bash
cd ~/aports/extra/tmux
abuild clean
abuild unpack
cd src/tmux-3.7c/
cp compat.h compat.h.orig
```

Add this block just before the final `#endif /* COMPAT_H */`:

```c
#ifdef __QNX__

#include <unix.h>

#ifndef IOV_MAX
#include <sys/uio.h>
#define IOV_MAX UIO_MAXIOV
#endif

#ifndef SA_RESTART
#define SA_RESTART 0
#endif

#endif
```

Then generate the patch, fix its header to the `a/` `b/` form, and add it to `source=` as that codelab describes:

```bash
diff -u compat.h.orig compat.h > ../../001-fix-qnx-compat.patch
```

This is the same change QNX engineers made in `extra/tmux/qnx-compat.patch`, which is how you can check qnxscout's prediction against reality.

---

## Step 6 - Fold the link and config findings into the APKBUILD

Two findings are not source changes:

* **QNX081 (`-lregex`)**: add the library to the build flags.
* **QNX079 (`config.sub`)**: refresh the autotools helper scripts in `prepare()`.

In `APKBUILD`:

```sh
prepare() {
	default_prepare
	update_config_sub
}

build() {
	CFLAGS="$CFLAGS -Wl,-lsocket,-lregex" \
	./configure \
		--build=$CBUILD \
		--host=$CHOST \
		--prefix=/usr
	make
}
```

QNX's own tmux recipe also passes `-lsocket` explicitly, which is a belt-and-braces addition next to tmux's `AC_SEARCH_LIBS`.

Update checksums:

```bash
abuild checksum
```

---

## Step 7 - Build and verify on QNX

```bash
cd ~/aports/extra/tmux
abuild -r -c -K
```

If the build fails, re-run qnxscout with `--show-info`. It also lists *conditional* findings (code whose QNX status depends on configure results), which are the next place to look.

---

## Step 8 - (Optional) Verify against your SDP

The built-in knowledge comes from QNX's public documentation and ports. If you have QNX SDP 8.0 installed through QNX Everywhere, let qnxscout check every reported header against `$QNX_TARGET/usr/include` and every reported function against the symbols your target libraries actually export. It reads ELF files directly, so no QNX tools need to be on the path:

```bash
source ~/qnx800/qnxsdp-env.sh
qnxscout scan tmux-3.7c.tar.gz --sdp "$QNX_TARGET" --arch x86_64
```

Each finding is then marked *confirmed by your SDP*, or downgraded with a note such as "your SDP's libc exports X()".

---

## Step 9 - Put it in CI

Add a workflow to any C/C++ repository on GitHub, and every push will show QNX porting issues in **Security > Code scanning** and in the run summary:

```yaml
jobs:
  qnxscout:
    runs-on: ubuntu-latest
    permissions:
      security-events: write
    steps:
      - uses: actions/checkout@v4
      - uses: OWNER/qnxscout@v0.1.0
      - uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: qnxscout.sarif
```

Use `qnxscout scan . --fail-on blocker` to make the job fail when a change introduces something that cannot build on QNX.

---

## Step 10 - Pick your next port

qnxscout ships a *porting frontier* report (`docs/FRONTIER.md`): Alpine packages not yet in `qnx-ports/aports` whose dependencies are all already ported, ranked by predicted effort. Grade A and B packages there are good first contributions.

---

## Summary

You learned how to:

* Scan pristine upstream source for QNX 8.0 porting issues on any host, without the SDP
* Read each finding together with the QNX evidence behind it
* Turn the findings into one platform-gated patch plus APKBUILD changes, the way QNX's own ports do
* Build on a QNX target with `abuild`, verify against your SDP, and catch regressions in CI

Predicted work you can see before you build is work you can plan, estimate and split up. Happy porting.
