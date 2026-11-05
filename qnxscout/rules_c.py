"""Rules applied to C/C++ translation units and headers."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

from . import kb
from .lexer import Lexed
from .model import Finding
from .preproc import PPResult, parse_int

CALL_RULES: dict = {}
WORD_RULES: dict = {}
MEMBER_RULES: dict = {}
for _r in kb.RULES:
    for _n in _r.calls:
        CALL_RULES[_n] = _r
    for _n in _r.words:
        WORD_RULES[_n] = _r
    for _n in _r.members:
        MEMBER_RULES[_n] = _r


def _alt(names):
    return "|".join(sorted((re.escape(n) for n in names), key=len, reverse=True))


CALL_RE = re.compile(r"(?<![\w$])(" + _alt(CALL_RULES) + r")\s*\(")
WORD_RE = re.compile(r"(?<![\w$])(" + _alt(WORD_RULES) + r")(?![\w$])")
MEMBER_RE = re.compile(r"(?:\.|->)\s*(" + _alt(MEMBER_RULES) + r")(?![\w$])")
DECL_KEYWORDS = {"return", "else", "do", "case", "sizeof", "typeof", "__typeof__", "decltype", "throw",
                 "co_await", "co_return", "co_yield", "delete", "new", "not", "and", "or", "goto", "if",
                 "while", "for", "switch", "defined", "noexcept", "alignof", "_Alignof", "__extension__",
                 "constexpr", "consteval", "static_assert"}

PROC_RE = re.compile(r"^/(?:proc/(?:self|%d|%u|%ld|%lu|%i|[0-9]+|\$|thread-self)/(?:exe|maps|smaps|status|stat|statm|"
                     r"cmdline|fd|fdinfo|mountinfo|mounts|auxv|environ|cgroup|task|limits|io|comm|oom_score_adj)|"
                     r"proc/(?:meminfo|cpuinfo|stat|loadavg|mounts|uptime|version|sys/|net/|pressure/|filesystems|"
                     r"self$)|sys/(?:class|devices|fs|kernel|bus|block|module|firmware|power)\b)")
WIN32_TOKENS = re.compile(r"(?<![\w$])(HANDLE|DWORD|WINAPI|GetLastError|CreateFile[AW]?|CloseHandle|"
                          r"GetTickCount(?:64)?|QueryPerformanceCounter|WSAStartup|WaitForSingleObject|"
                          r"CreateThread|VirtualAlloc|GetModuleHandle[AW]?|GetProcAddress|LoadLibrary[AW]?|"
                          r"__declspec|_beginthreadex|InterlockedIncrement|CRITICAL_SECTION|SYSTEM_INFO)(?![\w$])")
LINUX_MACROS = {"__linux__", "__linux", "linux", "__gnu_linux__", "__ANDROID__", "ANDROID", "__GLIBC__"}
UNIX_FLAVOURS = LINUX_MACROS | {"__APPLE__", "__MACH__", "__FreeBSD__", "__NetBSD__", "__OpenBSD__",
                                "__DragonFly__", "__sun", "__sun__", "_AIX", "__HAIKU__", "__unix__", "__unix"}
TEST_PATH_RE = re.compile(r"(^|/)(tests?|testing|unittests?|testsuite|t|check|checks|spec|fuzz|fuzzing|"
                          r"benchmarks?|bench)(/|$)|(^|/)test_[^/]*$|_tests?\.[ch](pp|c|xx)?$|_unittest\.",
                          re.I)
ELEM_SIZE = {"char": 1, "uint8_t": 1, "int8_t": 1, "u8": 1, "s8": 1, "byte": 1, "BYTE": 1, "u_char": 1,
             "bool": 1, "_Bool": 1, "guchar": 1, "gchar": 1, "jbyte": 1, "UChar": 2, "char16_t": 2,
             "short": 2, "uint16_t": 2, "int16_t": 2, "u16": 2, "wchar_t": 4, "char32_t": 4,
             "int": 4, "unsigned": 4, "uint32_t": 4, "int32_t": 4, "u32": 4, "float": 4, "gint": 4,
             "long": 8, "size_t": 8, "ssize_t": 8, "uint64_t": 8, "int64_t": 8, "u64": 8, "double": 8,
             "uintptr_t": 8, "intptr_t": 8, "off_t": 8, "time_t": 8, "void": 8}
ARRAY_DECL_RE = re.compile(
    r"(?:^\s*|[;{}]\s*)(?:(?:const|volatile|register|unsigned|signed|alignas\s*\([^)]*\)|__attribute__\s*\(\([^)]*\)\))\s+)*"
    r"([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*\[\s*([^\[\];=]{1,80}?)\s*\]\s*(?:\[\s*([^\[\];=]{1,40}?)\s*\])?\s*(?:=|;)")
AT_FUNCS = r"(?:openat|openat64|fstatat|fstatat64|unlinkat|mkdirat|readlinkat|renameat|faccessat|fchmodat|" \
           r"fchownat|utimensat|linkat|symlinkat|mkfifoat|mknodat|scandirat)"


@dataclass
class FileCtx:
    rel: str
    lexed: Lexed
    pp: PPResult
    is_cpp: bool
    in_tests: bool


@dataclass
class ProjectIndex:
    files: set = field(default_factory=set)
    basenames: dict = field(default_factory=dict)       # suffix -> True
    provided: dict = field(default_factory=dict)        # symbol -> "file:line"
    macros_defined: dict = field(default_factory=dict)  # macro -> list of (file, line, state)
    numeric_macros: dict = field(default_factory=dict)  # macro -> int
    calls_fork: bool = False
    build_text: str = ""
    defines_qnx_source: bool = False
    stack_threshold: int = 256 * 1024

    def has_file(self, include: str, from_rel: str) -> bool:
        include = include.lstrip("./")
        if include in self.files:
            return True
        base = from_rel.rsplit("/", 1)[0] + "/" if "/" in from_rel else ""
        if base + include in self.files:
            return True
        return include in self.basenames

    def macro_provided(self, name: str) -> bool:
        return any(st is not False for (_f, _l, st) in self.macros_defined.get(name, []))


def is_test_path(rel: str) -> bool:
    return bool(TEST_PATH_RE.search(rel))


def _guarded(rule: kb.Rule, symbol: str, names: frozenset) -> list:
    if not names:
        return []
    want = {symbol, symbol.upper(), "HAVE_" + symbol.upper(), "HAVE_" + symbol.upper().lstrip("_")}
    hits = [n for n in names if n in want or n in rule.guards]
    for g in rule.guards:
        if "*" in g:
            rx = re.compile(g)
            hits += [n for n in names if rx.fullmatch(n)]
    return sorted(set(hits))


def declared_names(lexed: Lexed) -> list:
    """Names the file itself declares or defines as functions (e.g. a getrandom() fallback)."""
    out = []
    for i, line in enumerate(lexed.lines, 1):
        if i in lexed.directive_lines or "(" not in line:
            continue
        for m in re.finditer(r"([A-Za-z_]\w*)\s*\(", line):
            prev = line[:m.start()].rstrip()
            if _looks_like_declaration(prev):
                out.append((m.group(1), i))
    return out


def _looks_like_declaration(prev: str) -> bool:
    if not prev:
        return False
    if prev.endswith("*") or prev.endswith("&"):
        before = prev.rstrip("*& \t")
        mm = re.search(r"([A-Za-z_]\w*)$", before)
        return bool(mm) and mm.group(1) not in DECL_KEYWORDS
    mm = re.search(r"([A-Za-z_]\w*)$", prev)
    if not mm or mm.group(1) in DECL_KEYWORDS:
        return False
    # "x = foo bar(" is not a declaration; a declaration starts a statement.
    head = prev[:mm.start()].rstrip()
    return head == "" or head[-1] in ";{}" or re.search(
        r"(^|[;{}\s])(static|extern|inline|__inline|__inline__|const|unsigned|signed|struct|enum|union|"
        r"long|short|volatile|virtual|explicit|friend|constexpr|[A-Za-z_]\w*)$", head) is not None


def _snippet(lexed: Lexed, src_lines: list, line: int) -> str:
    s = src_lines[line - 1].strip() if 0 < line <= len(src_lines) else ""
    return s[:160]


def check_file(ctx: FileCtx, src: str, proj: ProjectIndex) -> list:
    lx, pp = ctx.lexed, ctx.pp
    src_lines = src.split("\n")
    findings: list = []

    def add(rule_id: str, line: int, message: str, symbol: str = "", state=True, severity: str = "", note: str = ""):
        rule = kb.RULES_BY_ID[rule_id]
        findings.append(Finding(
            rule=rule_id, severity=severity or rule.severity, file=ctx.rel, line=line, message=message,
            snippet=_snippet(lx, src_lines, line), confidence="high" if state is True else "medium",
            symbol=symbol, in_tests=ctx.in_tests, note=note))

    # ---- symbol, macro and member uses
    for i, line in enumerate(lx.lines, 1):
        if i in lx.directive_lines:
            continue
        state = pp.line_state[i]
        if state is False:
            continue
        guards = pp.line_guards[i]
        if "(" in line:
            for m in CALL_RE.finditer(line):
                name = m.group(1)
                prev = line[:m.start(1)].rstrip()
                if prev.endswith(".") or prev.endswith("->"):
                    continue
                if prev.endswith("::") and re.search(r"[\w>]\s*::$", prev):
                    continue
                if _looks_like_declaration(prev):
                    continue
                if name in proj.provided or proj.macro_provided(name):
                    continue
                rule = CALL_RULES[name]
                g = _guarded(rule, name, guards)
                if g:
                    add(rule.id, i, f"{name}() is used inside #if {', '.join(g)}; check that this "
                        f"configure/feature test fails cleanly on QNX", name, state, "info")
                else:
                    add(rule.id, i, f"{name}() is called", name, state)
        for m in WORD_RE.finditer(line):
            name = m.group(1)
            if proj.macro_provided(name):
                continue
            prev = line[:m.start(1)].rstrip()
            if prev.endswith(".") or prev.endswith("->"):
                continue
            rule = WORD_RULES[name]
            g = _guarded(rule, name, guards)
            if g:
                add(rule.id, i, f"{name} is used inside #if {', '.join(g)}", name, state, "info")
            else:
                add(rule.id, i, f"{name} is used", name, state)
        for m in MEMBER_RE.finditer(line):
            name = m.group(1)
            rule = MEMBER_RULES[name]
            g = _guarded(rule, name, guards)
            if g:
                add(rule.id, i, f"struct member {name} is used inside #if {', '.join(g)}", name, state, "info")
            else:
                add(rule.id, i, f"struct member '{name}' is accessed", name, state)

    # ---- includes
    for inc in pp.includes:
        if inc.state is False or proj.has_file(inc.header, ctx.rel):
            continue
        known = kb.header_known(inc.header)
        if known is not False:
            continue
        rule = next(r for pat, r in kb.HEADER_RULES if pat.match(inc.header))
        hdr_macro = "HAVE_" + re.sub(r"[^A-Za-z0-9]", "_", inc.header).upper()
        hits = sorted(n for n in inc.guards if n == hdr_macro or n in rule.guards or
                      any("*" in g and re.fullmatch(g, n) for g in rule.guards))
        sev = rule.header_severity or rule.severity
        if hits:
            add(rule.id, inc.line, f"#include <{inc.header}> inside #if {', '.join(hits)}", inc.header,
                inc.state, "info")
        else:
            add(rule.id, inc.line, f"#include <{inc.header}> - not available on QNX 8.0", inc.header,
                inc.state, sev)
        if kb.WINDOWS_HEADERS.match(inc.header):
            pass

    for inc in pp.includes:
        if inc.state is True and kb.WINDOWS_HEADERS.match(inc.header) and not proj.has_file(inc.header, ctx.rel):
            add("QNX061", inc.line, f"#include <{inc.header}> is compiled on QNX", inc.header, True)

    # ---- #error reachable
    for e in pp.errors:
        if e.state is True:
            add("QNX060", e.line, f"#error {e.text[:100]} is reached on QNX", "#error", True)
        elif e.state is None and e.platform:
            add("QNX060", e.line, f"#error {e.text[:100]} may be reached on QNX (depends on build "
                "configuration macros)", "#error", None, "review")

    # ---- platform chains
    for ch in pp.chains:
        if ch.parent_eff is False:
            continue
        branches = ch.branches
        names_by_branch = [b.names for b in branches]
        has_else = any(b.kind == "else" for b in branches)
        linux_branch = next((b for b in branches if b.kind != "else" and b.names & LINUX_MACROS), None)
        if (linux_branch and not has_else and all(b.taken is False for b in branches)
                and not any("__QNX__" in n or "QNX" in n for ns in names_by_branch for n in ns)):
            body = [ln for ln in range(linux_branch.line + 1, (linux_branch.end_line or linux_branch.line) + 1)
                    if 0 < ln <= len(lx.lines) and lx.lines[ln - 1].strip()]
            if body:
                first = src_lines[body[0] - 1].strip()[:80]
                plats = sorted({n for b in branches for n in b.names if kb.PLATFORM_MACRO_RE.match(n)})
                add("QNX062", ch.start, f"QNX takes no branch of this #if chain ({', '.join(plats)}); "
                    f"the Linux branch provides e.g. '{first}'", "#if", ch.parent_eff if ch.parent_eff is not None else None)
        taken_else = next((b for b in branches if b.kind == "else" and b.taken is True), None)
        if taken_else:
            flavours = {n for b in branches if b.kind != "else" for n in b.names if n in UNIX_FLAVOURS}
            if len(flavours) >= 2 or (flavours & LINUX_MACROS and "__APPLE__" in flavours):
                for ln in range(taken_else.line + 1, (taken_else.end_line or taken_else.line) + 1):
                    if ln in lx.directive_lines or not (0 < ln <= len(lx.lines)):
                        continue
                    if pp.line_state[ln] is not True:
                        continue
                    wm = WIN32_TOKENS.search(lx.lines[ln - 1])
                    if wm:
                        add("QNX061", ln, f"QNX compiles the #else branch after "
                            f"{'/'.join(sorted(flavours))}, which uses the Win32 API ({wm.group(1)})",
                            wm.group(1), True)
                        break

    # ---- makedev() with two arguments
    for i, line in enumerate(lx.lines, 1):
        if "makedev" not in line or pp.line_state[i] is False or i in lx.directive_lines:
            continue
        for m in re.finditer(r"(?<![\w$])makedev\s*\(", line):
            if _looks_like_declaration(line[:m.start()].rstrip()):
                continue
            off = lx.line_offsets[i - 1] + m.end()
            depth, commas, j = 1, 0, off
            code = lx.code
            while j < len(code) and depth and j - off < 600:
                ch = code[j]
                if ch in "([{":
                    depth += 1
                elif ch in ")]}":
                    depth -= 1
                elif ch == "," and depth == 1:
                    commas += 1
                j += 1
            if depth == 0 and commas == 1 and not proj.macro_provided("makedev"):
                add("QNX037", i, "makedev() is called with two arguments; QNX's makedev() takes "
                    "(node, major, minor)", "makedev", pp.line_state[i])

    # ---- O_DIRECTORY heuristic
    open_re = re.compile(r"([A-Za-z_][\w.\->\[\]]*)\s*=\s*(?:::)?(open|open64|openat|openat64)\s*\(")
    for i, line in enumerate(lx.lines, 1):
        if pp.line_state[i] is False or i in lx.directive_lines or "open" not in line:
            continue
        for m in open_re.finditer(line):
            var = m.group(1).split(".")[-1].split("->")[-1]
            args = " ".join(lx.lines[i - 1:i + 2])[m.end():][:300]
            args = args[:args.find(";")] if ";" in args else args
            window = "\n".join(lx.lines[i:i + 60])
            v = re.escape(var)
            if re.search(r"O_DIRECTORY", args):
                if re.search(r"(?<![\w$])f(?:data)?sync\s*\(\s*" + v + r"\s*\)", window):
                    add("QNX050", i, f"'{var}' is opened with O_DIRECTORY and then fsync()ed; fsync() on a "
                        f"directory descriptor fails on QNX", "O_DIRECTORY", pp.line_state[i])
                continue
            if re.search(r"O_SEARCH|O_PATH", args):
                continue
            if (re.search(r"(?<![\w$])(?:fdopendir|fchdir)\s*\(\s*" + v + r"\b", window)
                    or re.search(r"(?<![\w$])" + AT_FUNCS + r"\s*\(\s*" + v + r"\s*,", window)
                    or re.search(r"(?<![\w$])\w*(?:Dir|dir|DIR)\w*\s*\(\s*(?:\w+\s*\()?\s*" + v + r"\s*\)", window)):
                add("QNX050", i, f"'{var}' is opened without O_DIRECTORY but then used as a directory "
                    f"descriptor", "O_DIRECTORY", pp.line_state[i])

    # ---- string literals: /proc, /sys, "(null)"
    seen_paths = set()
    null_reported = False
    for s in lx.strings:
        st = pp.line_state[s.line] if s.line < len(pp.line_state) else True
        if st is False or s.line in lx.directive_lines:
            continue
        if PROC_RE.match(s.value):
            key = s.value.split("%")[0][:40]
            if key not in seen_paths:
                seen_paths.add(key)
                add("QNX051", s.line, f"Linux procfs/sysfs path \"{s.value[:60]}\"", s.value[:60], st)
        elif s.value == "(null)" and not null_reported:
            null_reported = True
            add("QNX052", s.line, "code or tests rely on glibc printing \"(null)\" for NULL %s arguments",
                "(null)", st)

    # ---- feature-test macros
    if not proj.defines_qnx_source:
        for d in pp.defines:
            if d.state is False or d.name not in ("_XOPEN_SOURCE", "_POSIX_C_SOURCE"):
                continue
            val = parse_int(d.value) if d.value else None
            bad = (d.name == "_XOPEN_SOURCE" and (d.value == "" or (val is not None and val < 700))) or \
                  (d.name == "_POSIX_C_SOURCE" and val is not None and val < 200809)
            if bad:
                add("QNX053", d.line, f"#define {d.name} {d.value}".rstrip() + " restricts the visible API on QNX",
                    d.name, d.state)

    # ---- large stack arrays
    findings.extend(_stack_arrays(ctx, src_lines, proj))

    # ---- select() without <sys/select.h>
    incs = {i.header for i in pp.includes}
    if "sys/select.h" not in incs:
        for i, line in enumerate(lx.lines, 1):
            if pp.line_state[i] is True and i not in lx.directive_lines and re.search(r"(?<![\w$.>])(select\s*\(|fd_set\b)", line):
                if _looks_like_declaration(line[:line.find("select")].rstrip()) and "select(" in line:
                    continue
                add("QNX045", i, "select()/fd_set used without #include <sys/select.h>", "select", True, "info")
                break

    # ---- flock + fork / fork + exec
    for i, line in enumerate(lx.lines, 1):
        if pp.line_state[i] is False or i in lx.directive_lines:
            continue
        if re.search(r"(?<![\w$.>])flock\s*\(", line) and not _looks_like_declaration(line[:line.find("flock")].rstrip()):
            if proj.calls_fork:
                add("QNX046", i, "flock() lock in a program that also forks", "flock", pp.line_state[i])
            break
    return findings


def _stack_arrays(ctx: FileCtx, src_lines: list, proj: ProjectIndex) -> list:
    lx = ctx.lexed
    in_func = _function_scope_lines(lx)
    out = []
    for i, line in enumerate(lx.lines, 1):
        if not in_func[i] or ctx.pp.line_state[i] is False or i in lx.directive_lines or "[" not in line:
            continue
        for m in ARRAY_DECL_RE.finditer(line):
            typ, _name, dim1, dim2 = m.group(1), m.group(2), m.group(3), m.group(4)
            if typ in ("return", "static", "extern", "typedef", "case", "goto", "delete", "new", "else"):
                continue
            if re.search(r"\bstatic\b|\bthread_local\b|\b_Thread_local\b|__thread\b", line[:m.start(2)]):
                continue
            n1 = _const_eval(dim1, proj.numeric_macros)
            n2 = _const_eval(dim2, proj.numeric_macros) if dim2 else 1
            if n1 is None or n2 is None:
                continue
            size = n1 * n2 * ELEM_SIZE.get(typ, 1)
            if size >= proj.stack_threshold:
                rule = kb.RULES_BY_ID["QNX054"]
                out.append(Finding("QNX054", rule.severity, ctx.rel, i,
                                   f"{size // 1024} KiB local array '{_name}' on the stack",
                                   src_lines[i - 1].strip()[:160],
                                   "high" if ctx.pp.line_state[i] is True else "medium", _name, ctx.in_tests))
    return out


def _function_scope_lines(lx: Lexed) -> list:
    """For each line, True if it is inside a function body (approximation)."""
    code = lx.code
    n = len(lx.lines)
    res = [False] * (n + 2)
    stack = []          # 'f' function/control block, 'o' other
    last_break = 0
    line = 1
    depth_func = 0
    res[1] = False
    for idx, ch in enumerate(code):
        if ch == "\n":
            line += 1
            if line <= n:
                res[line] = depth_func > 0
            continue
        if ch == "{":
            head = code[last_break:idx]
            # Ignore preprocessor lines inside the head.
            head = re.sub(r"(?m)^\s*#.*$", "", head)
            if depth_func > 0:
                kind = "f"
            elif re.search(r"\b(struct|class|union|enum|namespace)\b|extern\s*\"|=\s*$|\]\s*$", head):
                kind = "o"
            elif ")" in head:
                kind = "f"
            else:
                kind = "o"
            stack.append(kind)
            if kind == "f":
                depth_func += 1
            last_break = idx + 1
        elif ch == "}":
            if stack:
                k = stack.pop()
                if k == "f":
                    depth_func -= 1
            last_break = idx + 1
        elif ch == ";":
            last_break = idx + 1
    return res


_ALLOWED_AST = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub, ast.Mult,
                ast.FloorDiv, ast.Div, ast.LShift, ast.RShift, ast.USub, ast.UAdd, ast.Mod)


def _const_eval(expr: str, macros: dict):
    if expr is None:
        return None
    e = expr.strip()
    e = re.sub(r"sizeof\s*\(\s*(?:unsigned\s+)?(\w+)\s*\)", lambda m: str(ELEM_SIZE.get(m.group(1), 0) or "x"), e)
    e = re.sub(r"\b(0[xX][0-9a-fA-F]+|\d+)[uUlL]+\b", r"\1", e)

    def sub(m):
        name = m.group(0)
        if re.fullmatch(r"0[xX][0-9a-fA-F]+|\d+", name):
            return str(int(name, 0)) if not name.startswith("0") or name.lower().startswith("0x") or name == "0" else str(int(name, 8))
        v = macros.get(name)
        return str(v) if isinstance(v, int) else "x"
    e = re.sub(r"[A-Za-z_]\w*|0[xX][0-9a-fA-F]+|\d+", sub, e)
    if "x" in e or not re.fullmatch(r"[0-9+\-*/%<>() ]+", e):
        return None
    try:
        tree = ast.parse(e.replace("/", "//"), mode="eval")
        if not all(isinstance(nd, _ALLOWED_AST) for nd in ast.walk(tree)):
            return None
        v = eval(compile(tree, "<dim>", "eval"), {"__builtins__": {}}, {})
        return int(v) if isinstance(v, int) and 0 < v < 1 << 40 else None
    except Exception:
        return None
