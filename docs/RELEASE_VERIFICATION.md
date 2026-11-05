# Release verification — November 5, 2026

QNXScout is a **host tool targeting QNX SDP 8.0**. Verification here used Windows and Python 3.12.14. No QNX target compiler, target hardware/QEMU, or actual installed SDP was used. Synthetic SDP tests do not establish real-SDP verification.

## Reproduce

```sh
git clone https://github.com/coledemole52/qnxscout.git
cd qnxscout
python -m venv .venv
# Activate .venv using the command appropriate to your shell.
python -m pip install .
python -m unittest discover -s tests -v
qnxscout scan tests/fixtures/sample -f html -o sample.html
```

The original 31-test suite passed on Windows: 30 tests passed and the Linux host-libc ELF test was skipped. The existing CLI test now additionally verifies that a missing path returns exit code 1 instead of a misleading Grade A. CI runs the existing suite and installation smoke test on Windows and Ubuntu with Python 3.9, 3.12 and 3.13.

The standalone package installed into a fresh virtual environment and scanned the pristine tmux 3.7c release archive. It found 24 findings across nine rules (including info-level findings), grade D. Its `SA_RESTART` use at `client.c:561` corresponds to a known QNX compatibility issue. The same upstream archive is executed during the recorded video; the recording console displays actual installed-CLI output. The console is capture equipment, not a shipped QNXScout web interface.

## Fresh source review: libhydrogen

A separate scan used the libhydrogen upstream master snapshot retrieved November 5, 2026; upstream HEAD was `264bf429021972c83b2a1a0cda13a765ddc3e11f`. No `libhydrogen` package or source path appears in either saved benchmark JSON dataset. This is an unfamiliar-project usability check, not a new accuracy benchmark.

The scanner reported grade B, five findings (four review, one info), across QNX060, QNX062 and QNX063. Manual source inspection found **important false-positive/review limitations**:

- `impl/random.h` has a `__unix__` branch using `random/unix.h`, so the later unsupported-platform `#error` is not evidence that a normal QNX Unix configuration fails. The scanner conservatively leaves earlier unknown configuration branches unresolved.
- `impl/common.h` checks OpenBSD/glibc for an optional `HAVE_EXPLICIT_BZERO` definition. Absence of a QNX branch does not itself establish a defect; fallback behavior must be inspected.
- The per-OS implementation warning explicitly notes `random/unix.h` as a generic fallback. A separate QNX file is not necessarily required.

These warnings are review prompts, not confirmed compatibility defects. No libhydrogen patch or QNX build is claimed. This fresh check reinforces why severity, confidence, evidence and manual review are necessary, and why grades must not be presented as build certificates.

## Historical benchmark limits

The retained data reports 609 package scans and 155/211 (73.5%) same-rule matches against identified rule-mappable historical issues. Labels use the rule vocabulary; some ports informed rule development. The denominator is not every modification engineers made. This release did not rerun the full historical download/evaluation pipeline and does not establish held-out accuracy or prospective reliability.

