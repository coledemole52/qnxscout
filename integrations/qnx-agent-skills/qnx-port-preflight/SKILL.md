---
name: qnx-port-preflight
description: "Covers running qnxscout, a static QNX 8.0 port-readiness scanner, on a package's pristine source before and during a port, and how to turn its JSON report into a work plan. Read this when choosing or estimating a package to port, before the first abuild of a new port, when a build fails with an undefined symbol, missing header, '#error', or CMake/Meson platform error and you want every similar problem at once, and before the review pass to check nothing predicted was left unaddressed."
---

# QNX port preflight with qnxscout

qnxscout reads a source tree and predicts what will not compile, link or behave correctly on QNX 8.0. Each finding points to a file and line and cites the evidence behind the rule: the QNX 8.0 C Library Reference, the QNX Porting Guide, `qnx-platform-facts`, or a patch in `qnx-ports/aports`. It is pure Python with no dependencies, so it runs on the host or on the QNX target's Python 3.

Use it to see the whole port up front instead of discovering it one build failure at a time.

## Predictions are priors, not evidence

The router's rules 1 and 2 apply in full. A qnxscout finding is a strong, cited prior about what the build will do. It is not proof. Do not write "X fails on QNX" in a report because qnxscout said so. Write it when the build output shows it, or attribute it: "qnxscout predicts X (rule QNX030)". Findings marked `"confidence": "medium"` depend on build configuration, such as a `HAVE_*` macro or an option, and are even softer.

## Scan the pristine source first

Scan the upstream tarball *before* any patches are applied, so the report describes the work rather than the work already done:

```sh
abuild fetch                                   # download sources into $SRCDEST
qnxscout scan "$SRCDEST"/<pkgname>-<pkgver>.tar.gz -f json -o /tmp/<pkgname>.qnxscout.json
qnxscout scan "$SRCDEST"/<pkgname>-<pkgver>.tar.gz                       # human-readable summary
```

If the SDP is installed on the host, add `--sdp "$QNX_TARGET"`. That re-checks every reported header against the SDP's `usr/include` and every reported function against the symbols the target libraries export. Findings the SDP contradicts are downgraded to `info` with a note.

## Turn the report into a plan

The JSON has `score` (grade A–E, `link_flags`, per-rule summary) and `findings` (rule, severity, file, line, message, confidence). Work through it by severity:

| Severity | What it usually becomes | Skill that governs the change |
|---|---|---|
| `link` | Extra `-l` flags in the APKBUILD's `LDFLAGS`, for example `-lsocket -lregex -lepoll -leventfd` | `alpine-qnx-porting` |
| `blocker` | A platform-gated source change: a missing define, a `#elif defined(__QNX__)` branch, a header swap | `aports-patch-creation`, `qnx-platform-facts` |
| `runtime` | A behavioural fix found by tests (`O_DIRECTORY`, `printf("%s", NULL)`, `flock` across `fork`) | `aports-patch-creation` |
| `review` | A decision: a Linux-only CMake/Meson branch QNX skips, a stale `config.sub` (`update_config_sub`), per-OS source files with no QNX variant | `alpine-qnx-porting` |

Group the source findings by file before patching. Several blockers often belong in one central compat header, which keeps the patch small and upstreamable. Explain any rule with:

```sh
qnxscout explain QNX030
```

## When a build fails

Search the report for the symbol or header in the error before investigating from scratch. If qnxscout predicted it, the cited evidence usually contains the fix QNX already used elsewhere. If it did not predict it, that is a new fact. Once the build output proves it, record it in the right skill (router rule 6), and consider proposing it as a qnxscout rule so the next scan predicts it.

## Before the review pass

Re-scan the patched tree (`abuild unpack` applies the patches) and compare it with the pristine report:

```sh
qnxscout scan src/<pkgname>-<pkgver> -f json -o /tmp/<pkgname>.after.json
```

Every remaining `blocker` or `runtime` finding should be either fixed, or explained in the port notes as not applicable, with the evidence that shows why (for example, the file is not compiled on QNX).
