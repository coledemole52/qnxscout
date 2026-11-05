#!/usr/bin/env python3
"""The QNX porting frontier: which Alpine packages could QNX port next, and how hard will each be?

1. Alpine packages that are *not* yet in qnx-ports/aports (by origin name).
2. Keep the ones whose build and runtime dependencies are all already ported
   to QNX ("unblocked"), using Alpine's APKINDEX (runtime deps, provides) and
   the APKBUILD makedepends.
3. Download each unblocked package's pristine upstream source, run qnxscout,
   and rank by predicted porting effort.

Usage:
  python3 bench/frontier.py --qnx-aports PATH --alpine-aports PATH --cache DIR --out DIR [--limit N]
(alpine-aports: a checkout of alpinelinux/aports; APKBUILDs only is enough)
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import io
import json
import os
import re
import shutil
import sys
import tarfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
from evaluate import ARCHIVE_RE, MAX_C_FILES, extract, fetch, git_fallback, parse_apkbuild  # noqa: E402
from qnxscout.scanner import scan  # noqa: E402

INDEX_URLS = ["https://dl-cdn.alpinelinux.org/alpine/edge/main/x86_64/APKINDEX.tar.gz",
              "https://dl-cdn.alpinelinux.org/alpine/edge/community/x86_64/APKINDEX.tar.gz"]
BASE = {"musl", "musl-dev", "linux-headers", "build-base", "busybox", "abuild", "alpine-baselayout",
        "libc-dev", "musl-utils", "scanelf", "fortify-headers", "gcc", "g++", "binutils", "make",
        "libgcc", "libstdc++", "libstdc++-dev", "libatomic", "libgomp", "libssp", "musl-libintl",
        "alpine-base", "apk-tools", "ca-certificates-bundle", "utmps-dev", "utmps", "skalibs"}
NOT_C_PREFIX = ("py3-", "perl-", "ruby-", "go-", "rust-", "font-", "ttf-", "R-", "php", "nodejs-",
                "openjdk", "dotnet", "ghc", "texlive", "lua-", "postgresql", "kde", "plasma", "gnome-",
                "xfce4-", "linux-", "firmware")


def load_index(cache: str) -> dict:
    pkgs = {}
    for url in INDEX_URLS:
        dest = os.path.join(cache, url.split("/")[-3] + "-APKINDEX.tar.gz")
        if not os.path.exists(dest):
            fetch(url, dest, 20)
        with tarfile.open(dest) as t:
            data = t.extractfile("APKINDEX").read().decode("utf-8", "replace")
        for block in data.split("\n\n"):
            rec = {}
            for line in block.splitlines():
                if len(line) > 2 and line[1] == ":":
                    rec.setdefault(line[0], []).append(line[2:])
            if "P" in rec:
                pkgs[rec["P"][0]] = {"origin": rec.get("o", [rec["P"][0]])[0],
                                     "depends": (rec.get("D", [""])[0]).split(),
                                     "provides": (rec.get("p", [""])[0]).split(),
                                     "repo": "main" if "main" in url else "community"}
    return pkgs


def build_resolver(pkgs: dict):
    provider = {}
    for name, rec in pkgs.items():
        provider[name] = rec["origin"]
        for p in rec["provides"]:
            provider.setdefault(re.split(r"[=<>~]", p)[0], rec["origin"])

    def resolve(dep: str):
        dep = re.split(r"[=<>~]", dep.lstrip("!"))[0]
        if not dep or dep.startswith("!"):
            return None
        if dep in provider:
            return provider[dep]
        base = re.sub(r"-(dev|static|libs|doc|tools|utils|openrc)$", "", dep)
        return provider.get(base, base)
    return resolve


def candidates(qnx_aports: str, alpine: str, pkgs: dict) -> list:
    ported = set()
    for repo in ("core", "extra"):
        ported.update(os.listdir(os.path.join(qnx_aports, repo)))
    resolve = build_resolver(pkgs)
    by_origin = {}
    for name, rec in pkgs.items():
        by_origin.setdefault(rec["origin"], set()).update(rec["depends"])
    out = []
    for repo in ("main", "community"):
        base = os.path.join(alpine, repo)
        for origin in sorted(os.listdir(base)):
            if origin in ported or origin.startswith(NOT_C_PREFIX):
                continue
            ab = os.path.join(base, origin, "APKBUILD")
            if not os.path.exists(ab):
                continue
            env = parse_apkbuild(ab)
            mk = (env.get("makedepends", "") + " " + env.get("makedepends_build", "") + " " +
                  env.get("makedepends_host", "")).split()
            if any(re.match(r"^(cargo|rust|go|nodejs|npm|openjdk|ghc|dotnet|zig)\b", m) for m in mk):
                continue
            deps = set(mk) | by_origin.get(origin, set())
            missing = set()
            for d in deps:
                o = resolve(d)
                if not o or o == origin or o in BASE or d in BASE or d.startswith(("so:libc.musl", "cmd:", "/")):
                    continue
                if o not in ported:
                    missing.add(o)
            out.append({"package": origin, "alpine_repo": repo, "version": env.get("pkgver"),
                        "url": env.get("url"), "description": env.get("pkgdesc"),
                        "missing_deps": sorted(missing), "unblocked": not missing,
                        "sources": env["_sources"], "apkbuild": ab})
    return out


def scan_candidate(c: dict, cache: str, max_mb: int) -> dict:
    srcs = [(f, u) for f, u in c["sources"] if ARCHIVE_RE.search(f) or ARCHIVE_RE.search(u)]
    res = {k: c[k] for k in ("package", "alpine_repo", "version", "url", "description")}
    if not srcs:
        res["status"] = "no-archive-source"
        return res
    fname, url = srcs[0]
    if fname.endswith(".zst"):
        res["status"] = "unsupported-archive"
        return res
    arch = os.path.join(cache, "dl", f"{c['package']}--{fname}")
    os.makedirs(os.path.dirname(arch), exist_ok=True)
    root = None
    if not fetch(url, arch, max_mb):
        root = git_fallback(url, os.path.join(cache, "git", c["package"]))
        if not root:
            res["status"] = "download-failed-or-too-large"
            return res
    root = root or extract(arch, os.path.join(cache, "src", c["package"]))
    try:
        if not root:
            res["status"] = "extract-failed"
            return res
        n_c = sum(1 for dp, _d, fns in os.walk(root) for fn in fns
                  if os.path.splitext(fn)[1].lower() in (".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh"))
        res["c_files"] = n_c
        if n_c == 0:
            res["status"] = "no-c-code"
            return res
        if n_c > MAX_C_FILES:
            res["status"] = "skipped-too-large"
            return res
        r = scan(root)
        res["status"] = "ok"
        res["score"] = r.score
        top = {}
        for f in r.findings:
            if f.severity != "info" and f.rule not in top:
                top[f.rule] = f"{f.file}:{f.line} {f.message}"[:160]
        res["top_findings"] = top
        return res
    finally:
        for d in (os.path.join(cache, "src", c["package"]), os.path.join(cache, "git", c["package"])):
            shutil.rmtree(d, ignore_errors=True)
        if os.path.exists(arch):
            os.unlink(arch)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qnx-aports", required=True)
    ap.add_argument("--alpine-aports", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-mb", type=int, default=25)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(a.cache, exist_ok=True)
    os.makedirs(a.out, exist_ok=True)
    pkgs = load_index(a.cache)
    cands = candidates(a.qnx_aports, a.alpine_aports, pkgs)
    unblocked = [c for c in cands if c["unblocked"]]
    print(f"{len(cands)} unported C-ish Alpine packages; {len(unblocked)} have every dependency already on QNX",
          flush=True)
    if a.limit:
        unblocked = unblocked[:a.limit]
    partial = os.path.join(a.out, "partial.jsonl")
    results, done = [], set()
    if os.path.exists(partial):
        for line in open(partial):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            results.append(r)
            done.add(r["package"])
    todo = [c for c in unblocked if c["package"] not in done]
    with cf.ProcessPoolExecutor(max_workers=a.jobs) as ex, open(partial, "a") as pf:
        futs = {ex.submit(scan_candidate, c, a.cache, a.max_mb): c for c in todo}
        for i, fut in enumerate(cf.as_completed(futs), len(done) + 1):
            try:
                r = fut.result()
            except Exception as e:  # pragma: no cover
                c = futs[fut]
                r = {k: c[k] for k in ("package", "alpine_repo", "version", "url", "description")}
                r["status"] = f"error: {e}"
            results.append(r)
            pf.write(json.dumps(r, default=str) + "\n")
            pf.flush()
            sc = r.get("score") or {}
            print(f"[{i}/{len(unblocked)}] {r['package']:30s} {r['status']:26s} {sc.get('grade', '-')} "
                  f"{sc.get('points', '')}", flush=True)
    blocked = {}
    for c in cands:
        for m in c["missing_deps"]:
            blocked[m] = blocked.get(m, 0) + 1
    json.dump({"generated": time.strftime("%Y-%m-%d"), "unported_candidates": len(cands),
               "unblocked": len([c for c in cands if c["unblocked"]]),
               "most_wanted_dependencies": sorted(blocked.items(), key=lambda kv: -kv[1])[:40],
               "results": sorted(results, key=lambda r: (r.get("status") != "ok",
                                                         (r.get("score") or {}).get("points", 1e9)))},
              open(os.path.join(a.out, "frontier.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
