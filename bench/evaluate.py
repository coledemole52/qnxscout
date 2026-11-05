#!/usr/bin/env python3
"""Evaluate qnxscout against real QNX ports.

Ground truth: qnx-ports/aports, where QNX engineers port Alpine packages to
QNX 8.0.  For each package we

  1. read the APKBUILD (with a tiny shell-variable expander; nothing is executed),
  2. download the pristine upstream source it builds from,
  3. run qnxscout on that pristine source,
  4. extract the issues QNX engineers actually had to fix, from
       - the QNX-specific *.patch files (identifiers in changed lines), and
       - the APKBUILD itself (extra -lsocket/-lepoll/... flags, update_config_sub, -std=c99),
  5. compare.

"Recall" = share of ground-truth issues (per package, per rule) that qnxscout
predicted from the pristine source alone.

Usage:
  python3 bench/evaluate.py --aports PATH/TO/qnx-ports-aports --cache bench/cache \\
      [--packages tmux,libevent] [--max-mb 40] [--limit N] [--jobs 4] [--out bench/results]
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import fnmatch
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from qnxscout import kb  # noqa: E402
from qnxscout.scanner import scan  # noqa: E402

# ----------------------------------------------------------------------------- APKBUILD parsing
ASSIGN_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)=("(?:[^"\\]|\\.)*"|\'[^\']*\'|[^\s#]*)', re.M | re.S)


def _glob_to_re(pat: str, greedy: bool) -> str:
    out = ""
    for ch in pat:
        out += (".*" if greedy else ".*?") if ch == "*" else "." if ch == "?" else re.escape(ch)
    return out


def expand(s: str, env: dict) -> str | None:
    def var(m):
        body = m.group(1) or m.group(2)
        if body is None:
            return ""
        mm = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)(.*)$", body, re.S)
        if not mm:
            raise ValueError(body)
        name, op = mm.group(1), mm.group(2)
        val = env.get(name)
        if val is None:
            raise ValueError(name)
        if not op:
            return val
        if op.startswith("%%"):
            return re.sub("(" + _glob_to_re(op[2:], True) + ")$", "", val, count=1)
        if op.startswith("%"):
            pat = _glob_to_re(op[1:], False)
            m2 = None
            for i in range(len(val), -1, -1):
                if re.fullmatch(pat, val[i:]):
                    m2 = i
                    break
            return val[:m2] if m2 is not None else val
        if op.startswith("##"):
            pat = _glob_to_re(op[2:], True)
            for i in range(len(val), -1, -1):
                if re.fullmatch(pat, val[:i]):
                    return val[i:]
            return val
        if op.startswith("#"):
            pat = _glob_to_re(op[1:], False)
            for i in range(0, len(val) + 1):
                if re.fullmatch(pat, val[:i]):
                    return val[i:]
            return val
        if op.startswith("//") or op.startswith("/"):
            glob_all = op.startswith("//")
            rest = op[2:] if glob_all else op[1:]
            pat, _, rep = rest.partition("/")
            return re.sub(_glob_to_re(pat, False), lambda _m: rep, val, count=0 if glob_all else 1)
        if op.startswith(":"):
            parts = op[1:].split(":")
            off = int(parts[0])
            ln = int(parts[1]) if len(parts) > 1 else None
            return val[off:] if ln is None else val[off:off + ln]
        raise ValueError(op)
    try:
        if "$(" in s or "`" in s:
            return None
        return re.sub(r"\$\{([^}]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)", var, s)
    except (ValueError, re.error, IndexError):
        return None


def parse_apkbuild(path: str) -> dict:
    text = open(path, errors="replace").read()
    # only top-level assignments (before the first function body)
    head = re.split(r"(?m)^[A-Za-z_][A-Za-z0-9_]*\s*\(\)\s*\{", text)[0]
    env = {"CARCH": "x86_64", "CBUILD": "x86_64-pc-nto-qnx8.0.0", "CHOST": "x86_64-pc-nto-qnx8.0.0",
           "srcdir": "/src", "builddir": "/src/b", "pkgdir": "/pkg"}
    for m in ASSIGN_RE.finditer(head):
        name, raw = m.group(1), m.group(2)
        if raw.startswith("'"):
            val = raw[1:-1]
        else:
            if raw.startswith('"'):
                raw = raw[1:-1]
            val = expand(raw, env)
            if val is None:
                continue
        env[name] = val
    sources = []
    for entry in env.get("source", "").split():
        fname, url = (entry.split("::", 1) + [None])[:2] if "::" in entry else (None, entry)
        if "://" in (url or ""):
            sources.append((fname or url.rsplit("/", 1)[-1], url))
    env["_text"] = text
    env["_sources"] = sources
    return env


# ----------------------------------------------------------------------------- ground truth
def _vocab() -> dict:
    v = {}
    for r in kb.RULES:
        for n in r.calls + r.words + r.members:
            v[n] = r.id
        for h in r.headers:
            if re.fullmatch(r"[A-Za-z0-9_/.-]+", h) and not h.endswith("__never"):
                v[h] = r.id
    v.update({
        "CMAKE_SYSTEM_PROCESSOR": "QNX077", "O_DIRECTORY": "QNX050", "_XOPEN_SOURCE": "QNX053",
        "_POSIX_C_SOURCE": "QNX053", "_SC_PHYS_PAGES": "QNX017", "unix.h": "QNX042", "_cmdname": "QNX051",
        "sys/elf.h": "QNX040", "UIO_MAXIOV": "QNX031", "gulliver.h": "QNX038", "process.h": "QNX047",
        "makedev": "QNX037", "lockf": "QNX046", "flock": "QNX046", "posix_spawn": "QNX056",
        "ThreadCtl": "QNX012", "_NTO_TCTL_RUNMASK": "QNX012",
    })
    return v


VOCAB = _vocab()
SOURCE_PATCH_EXT = re.compile(r"\.(c|h|cc|cpp|cxx|hpp|hh|hxx|inl|ipp|c\+\+|in|txt|cmake|build|ac|am|mk|m4)$|"
                              r"(^|/)(Makefile|CMakeLists\.txt|meson\.build|configure|config\.sub)$")


def is_qnx_patch(name: str, text: str) -> bool:
    return bool(re.search(r"qnx|nto", name, re.I) or re.search(r"__QNX__|__QNXNTO__|\bQNX\b|\bqnx\b", text))


def ground_truth(pkgdir: str, env: dict) -> dict:
    """Return {rule_id: [evidence strings]} for what QNX engineers fixed."""
    gt: dict = {}

    def add(rid, why):
        gt.setdefault(rid, []).append(why)
    for fn in sorted(os.listdir(pkgdir)):
        if not fn.endswith(".patch"):
            continue
        text = open(os.path.join(pkgdir, fn), errors="replace").read()
        if not is_qnx_patch(fn, text):
            continue
        for chunk in re.split(r"(?m)^(?=diff |--- )", text):
            m = re.search(r"(?m)^\+\+\+ (?:[ab]/)?(\S+)", chunk)
            if not m or not SOURCE_PATCH_EXT.search(m.group(1)):
                continue
            target = m.group(1)
            lines = chunk.split("\n")
            changed_idx = [i for i, l in enumerate(lines) if (l.startswith("+") or l.startswith("-"))
                           and not l.startswith("+++") and not l.startswith("---")]
            # context lines wrapped by an added #if ... #endif also count
            wrapped, depth = set(), 0
            for i, l in enumerate(lines):
                code = l[1:].strip() if l[:1] in "+- " else ""
                if l.startswith("+") and re.match(r"#\s*if", code):
                    depth += 1
                elif l.startswith("+") and re.match(r"#\s*endif", code) and depth:
                    depth -= 1
                elif depth and l.startswith(" "):
                    wrapped.add(i)
            use = sorted(set(changed_idx) | wrapped)
            body = "\n".join(lines[i][1:] for i in use)
            changed = "\n".join(lines[i][1:] for i in changed_idx)
            for tok in set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*|<[^>\n]+>|\"[^\"\n]+\.h\"", body)):
                key = tok.strip('<>"')
                if key == "error" and not re.search(r"(?<![#\w])error\s*\(", body):
                    continue
                if key in VOCAB:
                    add(VOCAB[key], f"{fn}:{target}:{key}")
            base = target.rsplit("/", 1)[-1]
            if re.search(r"#\s*(?:el)?if.*__QNX__|#\s*elif\s+defined\s*\(?\s*QNX|#\s*ifdef\s+__QNX__", changed) and \
                    base.endswith((".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh")):
                if re.search(r"#\s*error", body):
                    add("QNX060", f"{fn}:{target}:#error")
            if base in ("CMakeLists.txt",) or base.endswith(".cmake"):
                if re.search(r"CMAKE_SYSTEM_NAME|\bQNX\b", changed):
                    add("QNX075", f"{fn}:{target}:CMAKE_SYSTEM_NAME")
                if re.search(r"(?m)^-.*\b(pthread)\b", "\n".join(lines[i] for i in changed_idx)):
                    add("QNX070", f"{fn}:{target}:pthread")
                if re.search(r"(?m)^-.*(-ldl|\bdl\b|CMAKE_DL_LIBS)", "\n".join(lines[i] for i in changed_idx)):
                    add("QNX071", f"{fn}:{target}:dl")
                if re.search(r"FATAL_ERROR", body):
                    add("QNX076", f"{fn}:{target}:FATAL_ERROR")
            if base == "meson.build" and re.search(r"'qnx'|qnx", changed):
                add("QNX075", f"{fn}:{target}:meson system")
            if re.search(r"(?m)^-.*-l(pthread)\b", "\n".join(lines[i] for i in changed_idx)):
                add("QNX070", f"{fn}:{target}:-lpthread")
            if re.search(r"(?m)^-.*-l(dl)\b", "\n".join(lines[i] for i in changed_idx)):
                add("QNX071", f"{fn}:{target}:-ldl")
            if re.search(r"/proc/self/exe|/proc/meminfo|/proc/cpuinfo|/proc/self", body):
                add("QNX051", f"{fn}:{target}:/proc")
            if re.search(r"\(null\)|printf.*NULL", changed):
                add("QNX052", f"{fn}:{target}:(null)")
    # APKBUILD-level fixes
    text = env.get("_text", "")
    build_part = text.split("build()", 1)[1] if "build()" in text else ""
    for lib, rid in (("socket", "QNX080"), ("regex", "QNX081"), ("epoll", "QNX001"), ("eventfd", "QNX002"),
                     ("timerfd", "QNX003"), ("signalfd", "QNX004"), ("fsnotify", "QNX005"),
                     ("memstream", "QNX006"), ("login", "QNX082")):
        if re.search(r"-l" + lib + r"\b", build_part):
            add(rid, f"APKBUILD links -l{lib}")
    if re.search(r"\bupdate_config_sub\b|\bupdate_config_guess\b", text):
        add("QNX079", "APKBUILD update_config_sub")
    if re.search(r"CMAKE_C_STANDARD=(99|11|17)|-std=(gnu|c)(99|11|17)", build_part):
        add("QNX074", "APKBUILD raises C standard")
    if re.search(r"libsysv-ipc-shim", text):
        add("QNX007", "APKBUILD depends on libsysv-ipc-shim")
    if re.search(r"liblocale-shim", text):
        add("QNX009", "APKBUILD depends on liblocale-shim")
    if re.search(r"stack-size", build_part):
        add("QNX054", "APKBUILD sets stack size")
    return gt


# ----------------------------------------------------------------------------- download / extract
def fetch(url: str, dest: str, max_mb: int) -> bool:
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return True
    tmp = dest + ".part"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "qnxscout-bench/0.1"})
        with urllib.request.urlopen(req, timeout=60) as r:
            size = int(r.headers.get("Content-Length") or 0)
            if size and size > max_mb * 1024 * 1024:
                return False
            with open(tmp, "wb") as fh:
                total = 0
                while True:
                    b = r.read(1 << 16)
                    if not b:
                        break
                    total += len(b)
                    if total > max_mb * 1024 * 1024:
                        fh.close()
                        os.unlink(tmp)
                        return False
                    fh.write(b)
        os.replace(tmp, dest)
        return True
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        return False


def extract(archive: str, dest: str) -> str | None:
    if os.path.isdir(dest) and os.listdir(dest):
        entries = os.listdir(dest)
        return os.path.join(dest, entries[0]) if len(entries) == 1 else dest
    os.makedirs(dest, exist_ok=True)
    try:
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as z:
                for m in z.infolist():
                    t = os.path.realpath(os.path.join(dest, m.filename))
                    if t.startswith(os.path.realpath(dest) + os.sep):
                        z.extract(m, dest)
        else:
            with tarfile.open(archive) as t:
                safe = [m for m in t.getmembers() if not (m.issym() or m.islnk() or m.isdev()) and
                        os.path.realpath(os.path.join(dest, m.name)).startswith(os.path.realpath(dest) + os.sep)]
                try:
                    t.extractall(dest, members=safe, filter="data")
                except TypeError:
                    t.extractall(dest, members=safe)
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        return None
    entries = os.listdir(dest)
    return os.path.join(dest, entries[0]) if len(entries) == 1 and os.path.isdir(os.path.join(dest, entries[0])) else dest


MAX_REPO_KB = 150 * 1024
KEEP_SOURCES = os.environ.get("QNXSCOUT_BENCH_KEEP", "") == "1"
MAX_C_FILES = 5000
GH_ARCHIVE = re.compile(r"https://github\.com/([^/]+)/([^/]+?)/+archive/(?:refs/tags/)?(.+?)(?:/[^/]+)?\.(?:tar\.gz|tgz|zip|tar\.bz2|tar\.xz)$")


def git_fallback(url: str, dest: str):
    """GitHub /archive/ tarballs are blocked in some sandboxes; a shallow clone of the tag is equivalent."""
    m = GH_ARCHIVE.match(url)
    if not m:
        return None
    if os.path.isdir(dest) and os.listdir(dest):
        return dest
    owner, repo, ref = m.group(1), m.group(2), m.group(3)
    try:
        with urllib.request.urlopen(urllib.request.Request(
                f"https://api.github.com/repos/{owner}/{repo}", headers={"User-Agent": "qnxscout-bench"}),
                timeout=30) as r:
            size_kb = json.load(r).get("size", 0)
        if size_kb > MAX_REPO_KB:
            return None
    except Exception:
        return None
    for cand in (ref, ref.split("/")[0]):
        try:
            subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", cand,
                            f"https://github.com/{owner}/{repo}.git", dest],
                           check=True, timeout=300, capture_output=True)
            shutil.rmtree(os.path.join(dest, ".git"), ignore_errors=True)
            return dest
        except Exception:
            shutil.rmtree(dest, ignore_errors=True)
    return None


ARCHIVE_RE = re.compile(r"\.(tar\.gz|tgz|tar\.xz|txz|tar\.bz2|tbz2|tar\.zst|tar|zip)$")


def evaluate_package(pkgdir: str, cache: str, max_mb: int) -> dict:
    name = os.path.basename(pkgdir)
    env = parse_apkbuild(os.path.join(pkgdir, "APKBUILD"))
    gt = ground_truth(pkgdir, env)
    patches = [f for f in os.listdir(pkgdir) if f.endswith(".patch")]
    qnx_patches = [f for f in patches if is_qnx_patch(f, open(os.path.join(pkgdir, f), errors="replace").read())]
    patch_lines = 0
    for fn in qnx_patches:
        for l in open(os.path.join(pkgdir, fn), errors="replace"):
            if (l.startswith("+") or l.startswith("-")) and not (l.startswith("+++") or l.startswith("---")):
                patch_lines += 1
    res = {"package": name, "repo": os.path.basename(os.path.dirname(pkgdir)), "version": env.get("pkgver"),
           "patches": len(patches), "qnx_patches": len(qnx_patches), "qnx_patch_lines": patch_lines,
           "ground_truth": gt}
    srcs = [(f, u) for f, u in env["_sources"] if ARCHIVE_RE.search(f) or ARCHIVE_RE.search(u)]
    if not srcs:
        res["status"] = "no-archive-source"
        return res
    fname, url = srcs[0]
    if fname.endswith(".zst"):
        res["status"] = "unsupported-archive"
        return res
    arch_path = os.path.join(cache, "dl", f"{name}--{fname}")
    os.makedirs(os.path.dirname(arch_path), exist_ok=True)
    root = None
    if not fetch(url, arch_path, max_mb):
        root = git_fallback(url, os.path.join(cache, "git", name))
        if not root:
            res["status"] = "download-failed-or-too-large"
            return res
    root = root or extract(arch_path, os.path.join(cache, "src", name))
    if not root:
        res["status"] = "extract-failed"
        return res
    n_c = sum(1 for dp, _d, fns in os.walk(root) for fn in fns
              if os.path.splitext(fn)[1].lower() in (".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh"))
    if n_c > MAX_C_FILES:
        res["status"] = "skipped-too-large"
        res["c_files"] = n_c
        if not KEEP_SOURCES:
            shutil.rmtree(os.path.join(cache, "src", name), ignore_errors=True)
            shutil.rmtree(os.path.join(cache, "git", name), ignore_errors=True)
        return res
    t0 = time.time()
    try:
        r = scan(root)
    except Exception as e:  # pragma: no cover - reported in results
        res["status"] = f"scan-error: {type(e).__name__}: {e}"
        return res
    res["scan_seconds"] = round(time.time() - t0, 2)
    if not KEEP_SOURCES:
        shutil.rmtree(os.path.join(cache, "src", name), ignore_errors=True)
        shutil.rmtree(os.path.join(cache, "git", name), ignore_errors=True)
        if os.path.exists(arch_path):
            os.unlink(arch_path)
    pred = {}
    pred_files = set()
    for f in r.findings:
        if f.severity == "info":
            continue
        pred.setdefault(f.rule, 0)
        pred[f.rule] += 1
        pred_files.add(f.file)
    res["predicted"] = pred
    # location credit: a ground-truth issue in file X counts as found if qnxscout flagged X
    loc = {}
    for rid, evs in gt.items():
        files = {e.split(":")[1] for e in evs if e.count(":") >= 2}
        loc[rid] = any(any(t.endswith(pf) or pf.endswith(t.split("/", 1)[-1]) for pf in pred_files) for t in files)
    res["location_hit"] = loc
    res["score"] = r.score
    res["c_files"] = r.c_files
    res["status"] = "ok"
    return res


def summarize(results: list) -> dict:
    ok = [r for r in results if r.get("status") == "ok"]
    gt_pairs = [(r["package"], rid) for r in ok for rid in r["ground_truth"]]
    hit_pairs = [(r["package"], rid) for r in ok for rid in r["ground_truth"] if rid in r["predicted"]]
    loc_pairs = [(r["package"], rid) for r in ok for rid in r["ground_truth"]
                 if rid in r["predicted"] or r.get("location_hit", {}).get(rid)]
    per_rule = {}
    for r in ok:
        for rid in r["ground_truth"]:
            d = per_rule.setdefault(rid, {"gt": 0, "hit": 0, "predicted_in": 0})
            d["gt"] += 1
            if rid in r["predicted"]:
                d["hit"] += 1
        for rid in r["predicted"]:
            per_rule.setdefault(rid, {"gt": 0, "hit": 0, "predicted_in": 0})["predicted_in"] += 1
    patched = [r for r in ok if r["ground_truth"]]
    clean = [r for r in ok if not r["ground_truth"] and r["patches"] == 0]
    # AUC: does the effort score rank packages that needed QNX fixes above clean ones?
    auc = None
    if patched and clean:
        wins = ties = 0
        for a in patched:
            for b in clean:
                if a["score"]["points"] > b["score"]["points"]:
                    wins += 1
                elif a["score"]["points"] == b["score"]["points"]:
                    ties += 1
        auc = round((wins + 0.5 * ties) / (len(patched) * len(clean)), 3)
    grades = {}
    for group, rs in (("needed_qnx_fixes", patched), ("clean_ports", clean)):
        g = {}
        for r in rs:
            g[r["score"]["grade"]] = g.get(r["score"]["grade"], 0) + 1
        grades[group] = dict(sorted(g.items()))
    return {
        "packages_total": len(results), "packages_scanned": len(ok),
        "packages_with_ground_truth": len(patched), "clean_packages": len(clean),
        "ground_truth_issues": len(gt_pairs), "predicted_issues_hit": len(hit_pairs),
        "recall": round(len(hit_pairs) / len(gt_pairs), 3) if gt_pairs else None,
        "recall_with_location": round(len(loc_pairs) / len(gt_pairs), 3) if gt_pairs else None,
        "location_hits": len(loc_pairs),
        "auc_effort_score": auc, "grades": grades,
        "per_rule": dict(sorted(per_rule.items())),
        "status_counts": {s: sum(1 for r in results if r.get("status") == s) for s in sorted({r.get("status") for r in results})},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aports", required=True)
    ap.add_argument("--cache", default=os.path.join(HERE, "cache"))
    ap.add_argument("--packages", help="comma-separated package names")
    ap.add_argument("--only-ground-truth", action="store_true", help="only packages with QNX fixes")
    ap.add_argument("--max-mb", type=int, default=40)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--out", default=os.path.join(HERE, "results"))
    a = ap.parse_args()
    dirs = []
    for repo in ("core", "extra"):
        base = os.path.join(a.aports, repo)
        for p in sorted(os.listdir(base)):
            if os.path.exists(os.path.join(base, p, "APKBUILD")):
                dirs.append(os.path.join(base, p))
    if a.packages:
        want = set(a.packages.split(","))
        dirs = [d for d in dirs if os.path.basename(d) in want]
    if a.only_ground_truth:
        dirs = [d for d in dirs if ground_truth(d, parse_apkbuild(os.path.join(d, "APKBUILD")))]
    if a.limit:
        dirs = dirs[:a.limit]
    results = []
    with cf.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        futs = {ex.submit(evaluate_package, d, a.cache, a.max_mb): d for d in dirs}
        for i, fut in enumerate(cf.as_completed(futs), 1):
            r = fut.result()
            results.append(r)
            gt = set(r["ground_truth"])
            pr = set(r.get("predicted", {}))
            print(f"[{i}/{len(dirs)}] {r['package']:28s} {r['status']:28s} gt={sorted(gt)} hit={sorted(gt & pr)}",
                  flush=True)
    results.sort(key=lambda r: r["package"])
    os.makedirs(a.out, exist_ok=True)
    summary = summarize(results)
    with open(os.path.join(a.out, "results.json"), "w") as fh:
        json.dump({"summary": summary, "packages": results}, fh, indent=1, default=str)
    print(json.dumps({k: v for k, v in summary.items() if k != "per_rule"}, indent=1))


if __name__ == "__main__":
    main()
