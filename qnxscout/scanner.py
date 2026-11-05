"""Walk a source tree, run every analyzer, and score the result."""
from __future__ import annotations

import fnmatch
import os
import re
import time
from collections import defaultdict
from typing import Iterable, Optional

from . import buildsys, kb, rules_c
from .lexer import lex
from .model import Finding, ScanResult
from .preproc import MacroEnv, parse_int, run as run_pp
from .score import score_findings

C_EXT = {".c", ".h", ".cc", ".cpp", ".cxx", ".c++", ".hpp", ".hh", ".hxx", ".h++", ".inl", ".ipp", ".tcc",
         ".cu", ".m", ".mm"}
CPP_EXT = {".cc", ".cpp", ".cxx", ".c++", ".hpp", ".hh", ".hxx", ".h++", ".ipp", ".tcc", ".mm"}
HEADER_EXT = {".h", ".hpp", ".hh", ".hxx", ".h++", ".inl", ".ipp", ".tcc", ".def", ".inc"}
SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".tox", ".venv", "venv", ".cache",
             ".idea", ".vscode", "CMakeFiles", "autom4te.cache", ".deps", ".libs"}
BUILD_NAMES = {"CMakeLists.txt", "meson.build", "meson_options.txt", "meson.options", "configure.ac",
               "configure.in", "Makefile", "Makefile.am", "Makefile.in", "GNUmakefile", "makefile",
               "config.sub", "SConstruct", "SConscript", "BUILD", "BUILD.bazel", "setup.py", "build.rs",
               "config.h.in", "config.h.cmake", "config.h.meson", "configure.cmake"}
BUILD_EXT = {".cmake", ".mk", ".mak", ".bzl", ".gyp", ".gypi", ".gn", ".gni", ".pro", ".pri", ".in",
             ".am", ".ac", ".m4"}
MAX_BYTES = 4 * 1024 * 1024
LINK_RX = {rid: re.compile(r"(?<![\w$.>])(" + "|".join(sorted(names, key=len, reverse=True)) + r")\s*\(")
           for rid, (names, _lib) in kb.LINK_CHECKS.items()}
WELL_KNOWN_FACTS = {
    "G_OS_UNIX": ("def", 1), "G_OS_WIN32": ("undef", None), "G_PLATFORM_WIN32": ("undef", None),
    "Q_OS_QNX": ("def", 1), "Q_OS_UNIX": ("def", 1), "Q_OS_LINUX": ("undef", None), "Q_OS_WIN": ("undef", None),
    "Q_OS_WIN32": ("undef", None), "Q_OS_MACOS": ("undef", None), "Q_OS_DARWIN": ("undef", None),
    "Q_OS_ANDROID": ("undef", None), "Q_OS_IOS": ("undef", None), "Q_OS_MAC": ("undef", None),
}


PLATFORM_TOKENS = {
    "linux": "linux", "gnu_linux": "linux", "android": "android", "freebsd": "freebsd", "netbsd": "netbsd",
    "openbsd": "openbsd", "dragonfly": "dragonfly", "dragonflybsd": "dragonfly", "bsd": "bsd",
    "darwin": "darwin", "macos": "darwin", "macosx": "darwin", "osx": "darwin", "apple": "darwin", "ios": "ios",
    "win32": "windows", "win64": "windows", "windows": "windows", "mingw": "windows", "msvc": "windows",
    "cygwin": "cygwin", "haiku": "haiku", "solaris": "solaris", "sunos": "solaris", "illumos": "solaris",
    "aix": "aix", "hpux": "hpux", "emscripten": "emscripten", "wasm": "wasm", "wasi": "wasm",
    "fuchsia": "fuchsia", "hurd": "hurd", "beos": "haiku", "os2": "os2", "vms": "vms", "zos": "zos",
    "qnx": "qnx", "nto": "qnx", "posix": "posix", "unix": "unix",
    "vxworks": "vxworks", "zephyr": "zephyr", "freertos": "freertos", "rtems": "rtems", "nuttx": "nuttx",
    "threadx": "threadx", "esp32": "esp32", "espidf": "esp32", "arduino": "arduino", "mbed": "mbed",
    "riot": "riot", "contiki": "contiki", "tizen": "tizen", "wince": "windows", "uwp": "windows",
    "xbox": "console", "ps4": "console", "ps5": "console", "psp": "console", "vita": "console",
    "nds": "console", "3ds": "console", "wii": "console",
}
_PLAT_SPLIT = re.compile(r"[-_./]")


def platform_of_path(rel: str) -> Optional[str]:
    """Platform a source file is dedicated to, judged from its name (osdep-freebsd.c, win32/x.c)."""
    parts = rel.lower().split("/")
    stem = os.path.splitext(parts[-1])[0]
    for tok in _PLAT_SPLIT.split(stem):
        if tok in PLATFORM_TOKENS:
            return PLATFORM_TOKENS[tok]
    for d in parts[:-1]:
        if d in PLATFORM_TOKENS and d not in ("posix", "unix"):
            return PLATFORM_TOKENS[d]
    return None


GENERIC_TOKENS = r"(?:unknown|generic|posix|unix|default|other|none|stub|dummy|common)"


def has_generic_sibling(rel: str, files: list) -> bool:
    """osdep-linux.c next to osdep-unknown.c / ngx_linux_config.h next to ngx_posix_config.h."""
    d, base = (rel.rsplit("/", 1) if "/" in rel else ("", rel))
    m = re.match(r"^(.*?)(?<![A-Za-z0-9])linux(?![A-Za-z0-9])(.*)$", base, re.I)
    if not m:
        return False
    rx = re.compile(re.escape(m.group(1)) + GENERIC_TOKENS + re.escape(m.group(2)), re.I)
    return any((f.rsplit("/", 1)[0] if "/" in f else "") == d and rx.fullmatch(f.rsplit("/", 1)[-1]) for f in files)


def per_os_families(files: list) -> list:
    """Find families like osdep-linux.c / osdep-freebsd.c that lack a QNX member."""
    fams = defaultdict(dict)
    for rel in files:
        d, base = (rel.rsplit("/", 1) if "/" in rel else ("", rel))
        stem, ext = os.path.splitext(base)
        toks = re.split(r"([-_.])", stem)
        for i in range(0, len(toks), 2):
            t = toks[i].lower()
            if t in PLATFORM_TOKENS and PLATFORM_TOKENS[t] not in ("posix", "unix"):
                key = (d, "".join(toks[:i]) + "*" + "".join(toks[i + 1:]) + ext)
                fams[key][PLATFORM_TOKENS[t]] = rel
    out = []
    for (d, pattern), members in sorted(fams.items()):
        oses = set(members)
        if "qnx" in oses or len(oses - {"windows"}) < 2 or re.search(r"(^|/)(compat|missing|replace|fallback)", d):
            continue
        rx = re.escape(pattern).replace(r"\*", r"(?:unknown|generic|posix|unix|default|other|none|stub|dummy|common)")
        generic = [f for f in files
                   if (f.rsplit("/", 1)[0] if "/" in f else "") == d and re.fullmatch(rx, f.rsplit("/", 1)[-1], re.I)]
        first = sorted(members.values())[0]
        fallback = f"; generic fallback: {generic[0]}" if generic else "; no generic fallback found"
        rule = kb.RULES_BY_ID["QNX063"]
        out.append(Finding("QNX063", rule.severity, first, 1,
                           f"{(d + '/' if d else '') + pattern} exists for {', '.join(sorted(oses))} but not QNX"
                           + fallback, "", "high" if not generic else "medium", pattern))
    return out


def _read(path: str) -> Optional[str]:
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return None
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    if b"\0" in data[:4096]:
        return None
    return data.decode("utf-8", errors="replace")


def walk(root: str, excludes: Iterable[str] = ()) -> tuple:
    c_files, build_files = [], []
    excludes = list(excludes)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        rel_dir = os.path.relpath(dirpath, root)
        rel_dir = "" if rel_dir == "." else rel_dir.replace(os.sep, "/")
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not any(
            fnmatch.fnmatch((rel_dir + "/" + d).lstrip("/"), pat) for pat in excludes))
        for fn in sorted(filenames):
            rel = (rel_dir + "/" + fn).lstrip("/")
            if any(fnmatch.fnmatch(rel, pat) for pat in excludes):
                continue
            full = os.path.join(dirpath, fn)
            if os.path.islink(full):
                continue
            ext = os.path.splitext(fn)[1].lower()
            if ext in C_EXT:
                c_files.append(rel)
            elif fn in BUILD_NAMES or ext in BUILD_EXT or fn.startswith("CMakeLists"):
                build_files.append(rel)
    return c_files, build_files


def scan(root: str, arch: str = "any", excludes: Iterable[str] = (), include_tests: bool = True,
         sdp=None, stack_threshold: int = 256 * 1024, progress=None) -> ScanResult:
    t0 = time.time()
    root = os.path.abspath(root)
    c_files, build_files = walk(root, excludes)
    if not include_tests:
        c_files = [f for f in c_files if not rules_c.is_test_path(f)]
    result = ScanResult(root=root, c_files=len(c_files), build_files=len(build_files))

    # ---------------------------------------------------------------- build files first (text index)
    build_texts = {}
    for rel in build_files:
        txt = _read(os.path.join(root, rel))
        if txt is not None:
            build_texts[rel] = txt
    build_blob = "\n".join(build_texts.values())

    proj = rules_c.ProjectIndex(stack_threshold=stack_threshold)
    proj.build_text = build_blob
    proj.files = set(c_files) | set(build_files)
    for f in c_files:
        parts = f.split("/")
        for k in range(1, len(parts)):
            proj.basenames["/".join(parts[k:])] = True
    proj.defines_qnx_source = "_QNX_SOURCE" in build_blob

    # ---------------------------------------------------------------- pass 1: lex + collect
    lexed = {}
    sources = {}
    for idx, rel in enumerate(c_files):
        src = _read(os.path.join(root, rel))
        if src is None:
            continue
        sources[rel] = src
        lexed[rel] = lex(src)
        if progress:
            progress("lex", idx + 1, len(c_files))
    headers = [f for f in lexed if os.path.splitext(f)[1].lower() in HEADER_EXT]
    facts: dict = dict(WELL_KNOWN_FACTS)
    guard_names: set = set()
    for _iteration in range(2):
        env = MacroEnv(arch, facts)
        defs = defaultdict(list)
        for rel in headers:
            pp = run_pp(lexed[rel], env, os.path.splitext(rel)[1].lower() in CPP_EXT)
            if pp.guard_macro:
                guard_names.add(pp.guard_macro)
            for d in pp.defines:
                defs[d.name].append((d.state, None if d.function_like else (parse_int(d.value) if d.value else 1),
                                     d.function_like))
        new = dict(WELL_KNOWN_FACTS)
        for name, entries in defs.items():
            if name in guard_names or name in build_blob:
                continue
            states = {e[0] for e in entries}
            vals = {e[1] for e in entries}
            if states == {True} and len(vals) == 1:
                new[name] = ("def", next(iter(vals)))
            elif states == {False}:
                new[name] = ("undef", None)
        facts = new
    env = MacroEnv(arch, facts)

    # declarations / macro definitions / fork usage across the project
    pps = {}
    for rel, lx in lexed.items():
        pp = run_pp(lx, env, os.path.splitext(rel)[1].lower() in CPP_EXT)
        pps[rel] = pp
        for d in pp.defines:
            proj.macros_defined.setdefault(d.name, []).append((rel, d.line, d.state))
            if d.state is not False and not d.function_like:
                v = parse_int(d.value) if d.value else None
                if v is not None:
                    proj.numeric_macros.setdefault(d.name, v)
        for name, line in rules_c.declared_names(lx):
            if name in rules_c.CALL_RULES and pp.line_state[line] is not False:
                proj.provided.setdefault(name, f"{rel}:{line}")
        if not proj.calls_fork and re.search(r"(?<![\w$.>])(fork|daemon)\s*\(", lx.code):
            proj.calls_fork = True
        if not proj.uses_can and re.search(r"\b(AF_CAN|PF_CAN)\b", lx.code):
            proj.uses_can = True

    # ---------------------------------------------------------------- pass 2: rules
    findings: list = []
    all_files = list(lexed)
    used_calls = defaultdict(list)     # api name -> first (rel, line, state)
    for idx, (rel, lx) in enumerate(lexed.items()):
        pp = pps[rel]
        ctx = rules_c.FileCtx(rel, lx, pp, os.path.splitext(rel)[1].lower() in CPP_EXT, rules_c.is_test_path(rel))
        file_findings = rules_c.check_file(ctx, sources[rel], proj)
        plat = platform_of_path(rel)
        if plat and plat not in ("linux", "qnx", "posix", "unix"):
            for f in file_findings:
                if f.severity != "info":
                    f.note = f"{rel} is specific to {plat}; the QNX build normally does not compile it " \
                             f"(was {f.severity})"
                    f.severity = "info"
        elif plat == "linux" and has_generic_sibling(rel, all_files):
            for f in file_findings:
                if f.severity != "info":
                    f.note = f"{rel} is Linux-specific and has a generic/POSIX sibling the build can select " \
                             f"for QNX (was {f.severity})"
                    f.severity = "info"
        elif plat == "linux":
            for f in file_findings:
                f.confidence = "medium"
                f.note = f"{rel} is Linux-specific; it matters only if the QNX build compiles it"
        findings.extend(file_findings)
        for rid, (names, _lib) in kb.LINK_CHECKS.items():
            if all(n in used_calls for n in names):
                continue
            for m in LINK_RX[rid].finditer(lx.code):
                name = m.group(1)
                if name in used_calls:
                    continue
                line = lx.line_of(m.start())
                if pp.line_state[line] is not False and line not in lx.directive_lines:
                    used_calls[name].append((rel, line, pp.line_state[line]))
        if progress:
            progress("rules", idx + 1, len(lexed))

    findings.extend(per_os_families(list(lexed)))

    # ---------------------------------------------------------------- build systems
    systems = set()
    reachable: list = []          # build text QNX actually evaluates (CMake/Meson); others verbatim
    for rel, txt in build_texts.items():
        base = rel.rsplit("/", 1)[-1]
        start = len(findings)
        try:
            if base == "CMakeLists.txt" or base.endswith(".cmake"):
                systems.add("cmake")
                findings.extend(buildsys.analyze_cmake(rel, txt, reachable))
            elif base in ("meson.build",):
                systems.add("meson")
                findings.extend(buildsys.analyze_meson(rel, txt, reachable))
            elif base == "config.sub":
                findings.extend(buildsys.analyze_config_sub(rel, txt))
            elif base in ("configure.ac", "configure.in") or base.endswith(".m4") and "/" not in rel:
                systems.add("autotools")
                findings.extend(buildsys.analyze_autoconf(rel, txt))
            elif base in ("Makefile.am",):
                systems.add("autotools")
                findings.extend(buildsys.analyze_autoconf(rel, txt))
            elif base in ("Makefile", "GNUmakefile", "makefile") or base.endswith(".mk") or base.endswith(".mak"):
                systems.add("make")
                findings.extend(buildsys.analyze_makefile(rel, txt))
            elif base in ("BUILD", "BUILD.bazel") or base.endswith(".bzl"):
                systems.add("bazel")
            elif base == "setup.py":
                systems.add("python")
        except RecursionError:
            continue
        plat = platform_of_path(rel)
        test = rules_c.is_test_path(rel)
        for f in findings[start:]:
            f.in_tests = f.in_tests or test
            if plat and plat not in ("linux", "qnx", "posix", "unix") and f.severity != "info":
                f.note = f"{rel} is specific to {plat} (was {f.severity})"
                f.severity = "info"
    result.build_systems = sorted(systems)
    link_blob = "\n".join(reachable + [t for r, t in build_texts.items()
                                       if not (r.rsplit("/", 1)[-1] in ("CMakeLists.txt", "meson.build")
                                               or r.endswith(".cmake"))])

    # ---------------------------------------------------------------- project-level link checks
    uses = {}
    for rid, (names, lib) in kb.LINK_CHECKS.items():
        hits = [(n, used_calls[n][0]) for n in names if used_calls.get(n)]
        uses[lib] = bool(hits)
        if not hits or not build_texts:
            continue
        explicit = kb.build_links(lib, link_blob, explicit_only=True)
        searched = kb.build_links(lib, link_blob)
        if explicit:
            continue
        name, (rel, line, st) = hits[0]
        rule = kb.RULES_BY_ID[rid]
        if searched:
            msg = (f"uses {', '.join(n + '()' for n, _ in hits[:4])}; the build only searches for lib{lib} - QNX "
                   f"ports link -l{lib} explicitly even then")
            conf = "medium"
        else:
            msg = f"uses {', '.join(n + '()' for n, _ in hits[:4])} but the build never links {lib}"
            conf = "high" if st is True else "medium"
        findings.append(Finding(rid, rule.severity, rel, line, msg,
                                sources[rel].split("\n")[line - 1].strip()[:160] if rel in sources else "",
                                conf, name, rules_c.is_test_path(rel)))
    result.uses = uses

    # functions QNX declares in a different header than Linux does
    all_includes = set()
    for rel, pp in pps.items():
        all_includes.update(i.header for i in pp.includes)
    for fn, (hdr, rid) in kb.QNX_HEADER_HOME.items():
        if hdr in all_includes or fn in proj.provided:
            continue
        for rel, lx in lexed.items():
            m = re.search(r"(?<![\w$.>])" + fn + r"\s*\(", lx.code)
            if not m:
                continue
            line = lx.line_of(m.start())
            st = pps[rel].line_state[line]
            if st is False or line in lx.directive_lines or rules_c._looks_like_declaration(
                    lx.lines[line - 1][:lx.lines[line - 1].find(fn)].rstrip()):
                continue
            rule = kb.RULES_BY_ID[rid]
            findings.append(Finding(rid, rule.severity, rel, line,
                                    f"{fn}() is called, but no file includes <{hdr}>, where QNX declares it",
                                    sources[rel].split("\n")[line - 1].strip()[:160],
                                    "high" if st is True else "medium", fn, rules_c.is_test_path(rel)))
            break

    # link-only rules: drop if the build already links the compat library
    def already_linked(f: Finding) -> bool:
        rule = kb.RULES_BY_ID[f.rule]
        if rule.severity != "link" or not rule.link:
            return False
        lib = rule.link
        if lib.startswith("-l"):
            name = re.escape(lib[2:])
            return re.search(r"-l\s*" + name + r"\b|['\"]" + name + r"['\"]|link_libraries\([^)]*\b" + name +
                             r"\b(?![./_])", build_blob) is not None
        return lib in build_blob
    findings = [f for f in findings if not already_linked(f)]

    if sdp is not None:
        findings = sdp.refine(findings)
        result.sdp = sdp.root

    # ---------------------------------------------------------------- finish
    seen = set()
    uniq = []
    for f in findings:
        k = f.key()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(f)
    sev_rank = {s: i for i, s in enumerate(kb.SEVERITIES)}
    uniq.sort(key=lambda f: (sev_rank.get(f.severity, 9), f.rule, f.file, f.line))
    result.findings = uniq
    result.files_scanned = len(lexed) + len(build_texts)
    result.provided = dict(proj.provided)
    result.score = score_findings(uniq)
    result.duration_s = round(time.time() - t0, 2)
    return result
