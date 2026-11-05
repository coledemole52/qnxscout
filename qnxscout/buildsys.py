"""Build-system analysis: CMake, Meson, Autotools and plain Makefiles.

CMake and Meson conditions are evaluated with the same three-valued logic as
the C preprocessor, using what CMake/Meson report on QNX:
``CMAKE_SYSTEM_NAME`` is ``QNX`` (and the ``QNX`` and ``UNIX`` variables are
set); Meson's ``host_machine.system()`` is ``'qnx'`` (QNX's own cross files).
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Optional

from . import kb
from .model import Finding

Tri = Optional[bool]

CMAKE_TRUE = {"1", "ON", "YES", "TRUE", "Y"}
CMAKE_FALSE = {"0", "OFF", "NO", "FALSE", "N", "IGNORE", "NOTFOUND", ""}
CMAKE_KNOWN = {
    "CMAKE_SYSTEM_NAME": "QNX", "QNX": "1", "UNIX": "1",
    "APPLE": "", "WIN32": "", "MSVC": "", "MINGW": "", "CYGWIN": "", "ANDROID": "", "IOS": "",
    "LINUX": "", "BSD": "", "EMSCRIPTEN": "", "MSYS": "", "WINCE": "", "WINDOWS_PHONE": "",
    "WINDOWS_STORE": "", "HAIKU": "", "XCODE": "", "CMAKE_SYSTEM_NAME_LINUX": "",
}
PLATFORM_VARS = set(CMAKE_KNOWN) | {"CMAKE_HOST_SYSTEM_NAME", "CMAKE_SYSTEM", "CMAKE_HOST_UNIX",
                                    "CMAKE_HOST_WIN32", "CMAKE_HOST_APPLE", "CMAKE_HOST_LINUX"}
UNARY = {"EXISTS", "COMMAND", "DEFINED", "TARGET", "POLICY", "TEST", "IS_DIRECTORY", "IS_ABSOLUTE",
         "IS_SYMLINK", "IS_READABLE", "IS_WRITABLE", "IS_EXECUTABLE"}
BINARY = {"STREQUAL", "MATCHES", "LESS", "GREATER", "EQUAL", "LESS_EQUAL", "GREATER_EQUAL", "STRLESS",
          "STRGREATER", "STRLESS_EQUAL", "STRGREATER_EQUAL", "VERSION_LESS", "VERSION_GREATER",
          "VERSION_EQUAL", "VERSION_LESS_EQUAL", "VERSION_GREATER_EQUAL", "IN_LIST", "PATH_EQUAL",
          "IS_NEWER_THAN"}

LIB_RULES = [  # (regex on a link item, rule)
    (re.compile(r"^(?:-l)?pthread$"), "QNX070"),
    (re.compile(r"^(?:-l)?dl$"), "QNX071"),
    (re.compile(r"^(?:-l)?util$"), "QNX072"),
    (re.compile(r"^(?:-l)?rt$"), "QNX073"),
]
LINK_COMMANDS = {"target_link_libraries", "link_libraries", "target_link_options", "link_directories"}
C90_RE = re.compile(r"(?<![\w-])-std=(?:c89|c90|gnu89|gnu90|iso9899:1990|iso9899:199409)\b")


@dataclass
class Cmd:
    name: str
    args: list          # list of (text, quoted)
    line: int
    raw: str


def _tokenize_cmake(text: str) -> list:
    cmds = []
    i, n, line = 0, len(text), 1
    name_re = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c == "#":
            m = re.match(r"#\[(=*)\[", text[i:])
            if m:
                end = text.find("]" + m.group(1) + "]", i)
                end = n if end < 0 else end + len(m.group(1)) + 2
                line += text.count("\n", i, end)
                i = end
            else:
                j = text.find("\n", i)
                i = n if j < 0 else j
            continue
        if c.isspace():
            i += 1
            continue
        m = name_re.match(text, i)
        if not m:
            i += 1
            continue
        j = m.end()
        while j < n and text[j] in " \t":
            j += 1
        if j >= n or text[j] != "(":
            i = m.end()
            continue
        start_line = line
        name = m.group(0).lower()
        k = j + 1
        depth = 1
        args = []
        cur = []
        quoted = False

        def flush():
            nonlocal cur, quoted
            if cur or quoted:
                args.append(("".join(cur), quoted))
            cur = []
            quoted = False
        while k < n and depth > 0:
            ch = text[k]
            if ch == "\n":
                line += 1
                flush()
                k += 1
                continue
            if ch == "#" and not cur:
                bm = re.match(r"#\[(=*)\[", text[k:])
                if bm:
                    end = text.find("]" + bm.group(1) + "]", k)
                    end = n if end < 0 else end + len(bm.group(1)) + 2
                    line += text.count("\n", k, end)
                    k = end
                else:
                    e = text.find("\n", k)
                    k = n if e < 0 else e
                continue
            if ch == '"':
                e = k + 1
                buf = []
                while e < n and text[e] != '"':
                    if text[e] == "\\" and e + 1 < n:
                        buf.append(text[e:e + 2])
                        e += 2
                        continue
                    if text[e] == "\n":
                        line += 1
                    buf.append(text[e])
                    e += 1
                cur.append("".join(buf))
                quoted = True
                k = e + 1
                continue
            if ch == "[":
                bm = re.match(r"\[(=*)\[", text[k:])
                if bm:
                    end = text.find("]" + bm.group(1) + "]", k)
                    end = n if end < 0 else end
                    cur.append(text[k + len(bm.group(0)):end])
                    line += text.count("\n", k, end)
                    quoted = True
                    k = end + len(bm.group(1)) + 2
                    continue
            if ch == "(":
                depth += 1
                if depth > 1:
                    flush()
                    args.append(("(", False))
                k += 1
                continue
            if ch == ")":
                depth -= 1
                flush()
                if depth > 0:
                    args.append((")", False))
                k += 1
                continue
            if ch in " \t\r":
                flush()
                k += 1
                continue
            cur.append(ch)
            k += 1
        cmds.append(Cmd(name, args, start_line, text[m.start():k]))
        i = k
    return cmds


class CMakeEval:
    def __init__(self):
        self.vars = dict(CMAKE_KNOWN)
        self.unknown_vars: set = set()

    def expand(self, s: str):
        """Expand ${VAR}; None if any variable is unknown."""
        unknown = False

        def rep(m):
            nonlocal unknown
            v = m.group(1)
            if v.startswith("ENV{") or v.startswith("CACHE{"):
                unknown = True
                return ""
            if v in self.vars:
                return self.vars[v]
            unknown = True
            return ""
        for _ in range(4):
            if "${" not in s:
                break
            s = re.sub(r"\$\{([^${}]*)\}", rep, s)
        return None if unknown else s

    def operand(self, tok, quoted) -> Optional[str]:
        val = self.expand(tok)
        if val is None:
            return None
        if not quoted and val in self.vars:
            return self.vars[val]
        if not quoted and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", val) and val not in self.vars \
                and val.upper() not in CMAKE_TRUE | CMAKE_FALSE and not val.isdigit():
            return None
        return val

    def truth(self, tok, quoted) -> Tri:
        val = self.expand(tok)
        if val is None:
            return None
        up = val.upper()
        if up in CMAKE_TRUE:
            return True
        if up in CMAKE_FALSE or up.endswith("-NOTFOUND"):
            return False
        if re.fullmatch(r"-?\d+(\.\d+)?", val):
            return float(val) != 0
        if quoted:
            return False
        if val in self.vars:
            v = self.vars[val].upper()
            return not (v in CMAKE_FALSE or v.endswith("-NOTFOUND"))
        return None

    def condition(self, args: list):
        """Evaluate if() arguments. Returns (Tri, names_used)."""
        names: set = set()
        for t, q in args:
            for m in re.finditer(r"[A-Za-z_][A-Za-z0-9_]*", t):
                names.add(m.group(0))
        try:
            v, _ = self._or(args, 0)
            return v, names
        except (IndexError, ValueError):
            return None, names

    def _or(self, a, i):
        v, i = self._and(a, i)
        while i < len(a) and a[i] == ("OR", False):
            w, i = self._and(a, i + 1)
            v = True if (v is True or w is True) else (False if (v is False and w is False) else None)
        return v, i

    def _and(self, a, i):
        v, i = self._not(a, i)
        while i < len(a) and a[i] == ("AND", False):
            w, i = self._not(a, i + 1)
            v = False if (v is False or w is False) else (True if (v is True and w is True) else None)
        return v, i

    def _not(self, a, i):
        if i < len(a) and a[i] == ("NOT", False):
            v, i = self._not(a, i + 1)
            return (None if v is None else not v), i
        return self._binary(a, i)

    def _binary(self, a, i):
        if a[i] == ("(", False):
            v, i = self._or(a, i + 1)
            if i < len(a) and a[i] == (")", False):
                i += 1
            return v, i
        if a[i][0] in UNARY and not a[i][1]:
            op = a[i][0]
            arg, q = a[i + 1]
            if op == "DEFINED":
                name = self.expand(arg)
                if name is None:
                    return None, i + 2
                if name in self.vars:
                    return self.vars[name] != "" or name not in CMAKE_KNOWN, i + 2
                return None, i + 2
            return None, i + 2
        if i + 2 < len(a) + 1 and i + 1 < len(a) and a[i + 1][0] in BINARY and not a[i + 1][1]:
            lhs = self.operand(*a[i])
            op = a[i + 1][0]
            rhs_tok = a[i + 2]
            rhs = self.operand(*rhs_tok) if op != "MATCHES" else self.expand(rhs_tok[0])
            if lhs is None or rhs is None:
                return None, i + 3
            if op == "STREQUAL":
                return lhs == rhs, i + 3
            if op == "MATCHES":
                try:
                    return re.search(rhs, lhs) is not None, i + 3
                except re.error:
                    return None, i + 3
            if op == "IN_LIST":
                return lhs in self.vars.get(rhs_tok[0], "").split(";"), i + 3
            return None, i + 3
        return self.truth(*a[i]), i + 1


def _rel_finding(rule_id, rel, line, message, state=True, severity="", snippet="", symbol=""):
    rule = kb.RULES_BY_ID[rule_id]
    return Finding(rule_id, severity or rule.severity, rel, line, message, snippet[:160],
                   "high" if state is True else "medium", symbol)


def analyze_cmake(rel: str, text: str, reachable: list = None) -> list:
    cmds = _tokenize_cmake(text)
    ev = CMakeEval()
    out: list = []
    src_lines = text.split("\n")
    # stack frames: dict(branch=Tri, taken=bool, maybe=bool, plat=bool, linux_false=bool, has_qnx=bool)
    stack: list = []
    fn_depth = 0
    linux_reports = 0
    proc_reported = False

    def state() -> Tri:
        s: Tri = True
        for fr in stack:
            b = fr["branch"]
            s = False if (s is False or b is False) else (True if (s is True and b is True) else None)
        if fn_depth and s is True:
            return True
        return s

    def plat_ctx() -> bool:
        return any(fr["plat"] for fr in stack)

    def snip(line):
        return src_lines[line - 1].strip() if 0 < line <= len(src_lines) else ""

    for c in cmds:
        name = c.name
        argtoks = [(t if q else t, q) for t, q in c.args]
        if name in ("function", "macro"):
            fn_depth += 1
            continue
        if name in ("endfunction", "endmacro"):
            fn_depth = max(0, fn_depth - 1)
            continue
        if name == "if":
            v, names = ev.condition(argtoks)
            plat = bool(names & PLATFORM_VARS) or "CMAKE_SYSTEM_NAME" in " ".join(t for t, _ in argtoks)
            stack.append({"branch": v, "taken": v is True, "maybe": v is None, "plat": plat,
                          "has_qnx": "QNX" in " ".join(t for t, _ in argtoks), "line": c.line})
            _check_condition(rel, c, argtoks, v, stack, out, snip, state)
            continue
        if name == "elseif" and stack:
            fr = stack[-1]
            v, names = ev.condition(argtoks)
            fr["plat"] = fr["plat"] or bool(names & PLATFORM_VARS)
            fr["has_qnx"] = fr["has_qnx"] or "QNX" in " ".join(t for t, _ in argtoks)
            bv = False if fr["taken"] else (v if not fr["maybe"] else (False if v is False else None))
            fr["taken"] = fr["taken"] or bv is True
            fr["maybe"] = fr["maybe"] or bv is None
            fr["branch"] = bv
            _check_condition(rel, c, argtoks, v, stack, out, snip, state)
            continue
        if name == "else" and stack:
            fr = stack[-1]
            fr["branch"] = False if fr["taken"] else (True if not fr["maybe"] else None)
            continue
        if name == "endif" and stack:
            stack.pop()
            continue
        st = state()
        if st is False:
            continue
        if reachable is not None:
            reachable.append(c.raw)
        joined = " ".join(t for t, _ in argtoks)
        if name == "set" and argtoks and argtoks[0][0] not in CMAKE_KNOWN and not fn_depth:
            var = argtoks[0][0]
            toks = [t for t, _ in argtoks[1:]]
            expanded = None
            if st is True and "CACHE" not in toks:
                expanded = ev.expand(";".join(t for t in toks if t not in ("PARENT_SCOPE", "FORCE")))
            if expanded is not None:
                ev.vars[var] = expanded
            else:
                ev.vars.pop(var, None)
        if name == "message" and argtoks and argtoks[0][0] in ("FATAL_ERROR", "SEND_ERROR"):
            if st is True and plat_ctx():
                out.append(_rel_finding("QNX076", rel, c.line,
                                        "message(FATAL_ERROR) is reached for QNX: " + " ".join(t for t, _ in argtoks[1:])[:100],
                                        True, snippet=snip(c.line)))
            continue
        # link items
        if name in LINK_COMMANDS or (name in ("set", "list") and re.search(r"LIB|LINK|LDFLAGS", argtoks[0][0] if argtoks else "", re.I)) \
                or name in ("find_library",):
            items = []
            for t, q in argtoks:
                for part in re.split(r"[;\s]+", t):
                    items.append(part)
            for it in items:
                for rx, rid in LIB_RULES:
                    if rx.match(it):
                        if name == "find_library":
                            continue
                        out.append(_rel_finding(rid, rel, c.line, f"links '{it}' ({name})", st,
                                                snippet=snip(c.line), symbol=it))
                        break
        if name in ("set", "set_property", "set_target_properties", "target_compile_features") and argtoks:
            if re.search(r"(?:^|\s)(?:CMAKE_)?C_STANDARD\s+(?:90|89)\b", joined) or \
                    re.search(r"\bc_std_90\b", joined):
                out.append(_rel_finding("QNX074", rel, c.line, "C standard set to C90", st, snippet=snip(c.line)))
        if C90_RE.search(joined):
            out.append(_rel_finding("QNX074", rel, c.line, f"compiles with {C90_RE.search(joined).group(0)}", st,
                                    snippet=snip(c.line)))
        if "-fsplit-stack" in joined:
            out.append(_rel_finding("QNX078", rel, c.line, "-fsplit-stack", st, snippet=snip(c.line)))
    return out


def _check_condition(rel, c, argtoks, v, stack, out, snip, state):
    joined = " ".join(t for t, _ in argtoks)
    fr = stack[-1]
    if re.search(r"(?i)(?<![A-Za-z])linux(?![A-Za-z])", joined) and v is False and not fr["has_qnx"]:
        out.append(_rel_finding("QNX075", rel, c.line, f"QNX skips this Linux-only branch: if({joined[:90]})",
                                True, snippet=snip(c.line)))
    if "CMAKE_SYSTEM_PROCESSOR" in joined and re.search(r"STREQUAL|MATCHES", joined):
        out.append(_rel_finding("QNX077", rel, c.line, f"architecture check: if({joined[:90]})", None,
                                snippet=snip(c.line)))


# ----------------------------------------------------------------------------- Meson
class _MesonEval(ast.NodeVisitor):
    def __init__(self, vars_):
        self.vars = vars_

    def ev(self, node):
        if isinstance(node, ast.Expression):
            return self.ev(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in ("true", "True"):
                return True
            if node.id in ("false", "False"):
                return False
            return self.vars.get(node.id, _UNK)
        if isinstance(node, ast.List):
            vals = [self.ev(e) for e in node.elts]
            return _UNK if any(v is _UNK for v in vals) else vals
        if isinstance(node, ast.BoolOp):
            vals = [self.ev(v) for v in node.values]
            if isinstance(node.op, ast.And):
                if any(v is False for v in vals):
                    return False
                return True if all(v is True for v in vals) else _UNK
            if any(v is True for v in vals):
                return True
            return False if all(v is False for v in vals) else _UNK
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            v = self.ev(node.operand)
            return _UNK if v is _UNK else (not v)
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            a, b = self.ev(node.left), self.ev(node.comparators[0])
            if a is _UNK or b is _UNK:
                return _UNK
            op = node.ops[0]
            try:
                if isinstance(op, ast.Eq):
                    return a == b
                if isinstance(op, ast.NotEq):
                    return a != b
                if isinstance(op, ast.In):
                    return a in b
                if isinstance(op, ast.NotIn):
                    return a not in b
            except TypeError:
                return _UNK
        return _UNK


_UNK = object()


def _meson_expr(text: str, vars_: dict):
    t = re.sub(r"\bhost_machine\s*\.\s*system\s*\(\s*\)", "'qnx'", text)
    t = re.sub(r"\btarget_machine\s*\.\s*system\s*\(\s*\)", "'qnx'", t)
    t = t.replace("\n", " ")
    try:
        v = _MesonEval(vars_).ev(ast.parse(t.strip(), mode="eval"))
    except (SyntaxError, ValueError, RecursionError):
        return None
    if v is _UNK:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v
    return None


def analyze_meson(rel: str, text: str, reachable: list = None) -> list:
    out: list = []
    lines = text.split("\n")
    vars_: dict = {}
    plat_vars: set = set()
    stack: list = []

    def state() -> Tri:
        s: Tri = True
        for fr in stack:
            b = fr["branch"]
            s = False if (s is False or b is False) else (True if (s is True and b is True) else None)
        return s

    # join continued lines (open parens/brackets)
    logical = []
    buf, start, depth = "", 0, 0
    for i, raw in enumerate(lines, 1):
        code = re.sub(r"#.*$", "", raw) if "'" not in raw else _strip_meson_comment(raw)
        if not buf:
            start = i
        buf += (" " if buf else "") + code
        depth += code.count("(") + code.count("[") - code.count(")") - code.count("]")
        if depth <= 0:
            logical.append((start, buf.strip()))
            buf, depth = "", 0
    if buf:
        logical.append((start, buf.strip()))

    for ln, code in logical:
        if not code:
            continue
        m = re.match(r"^(if|elif)\s+(.*)$", code)
        if m:
            v = _meson_expr(m.group(2), vars_)
            v = v if isinstance(v, bool) else None
            names = set(re.findall(r"[A-Za-z_]\w*", m.group(2)))
            plat = "system()" in m.group(2) or bool(names & plat_vars)
            if m.group(1) == "if":
                stack.append({"branch": v, "taken": v is True, "maybe": v is None, "plat": plat,
                              "has_qnx": "'qnx'" in m.group(2)})
            elif stack:
                fr = stack[-1]
                fr["plat"] = fr["plat"] or plat
                fr["has_qnx"] = fr["has_qnx"] or "'qnx'" in m.group(2)
                bv = False if fr["taken"] else (v if not fr["maybe"] else (False if v is False else None))
                fr["taken"] = fr["taken"] or bv is True
                fr["maybe"] = fr["maybe"] or bv is None
                fr["branch"] = bv
            fr = stack[-1] if stack else None
            if fr and re.search(r"'linux'|\"linux\"", m.group(2)) and v is False and not fr["has_qnx"]:
                out.append(_rel_finding("QNX075", rel, ln, f"QNX skips this Linux-only branch: {code[:100]}",
                                        True, snippet=lines[ln - 1].strip()))
            continue
        if code == "else" and stack:
            fr = stack[-1]
            fr["branch"] = False if fr["taken"] else (True if not fr["maybe"] else None)
            continue
        if code == "endif" and stack:
            stack.pop()
            continue
        st = state()
        if st is False:
            continue
        if reachable is not None:
            reachable.append(code)
        am = re.match(r"^([A-Za-z_]\w*)\s*=\s*(.+)$", code)
        if am and not stack:
            v = _meson_expr(am.group(2), vars_)
            if v is not None:
                vars_[am.group(1)] = v
            else:
                vars_.pop(am.group(1), None)
            if "system()" in am.group(2) or set(re.findall(r"[A-Za-z_]\w*", am.group(2))) & plat_vars:
                plat_vars.add(am.group(1))
        if re.match(r"^error\s*\(", code) and any(fr["plat"] for fr in stack) and st is True:
            out.append(_rel_finding("QNX076", rel, ln, "error() is reached for QNX: " + code[:100], True,
                                    snippet=lines[ln - 1].strip()))
        for fm in re.finditer(r"find_library\s*\(\s*'(pthread|dl|util|rt)'([^)]*)\)", code):
            if re.search(r"required\s*:\s*false", fm.group(2)):
                continue
            rid = {"pthread": "QNX070", "dl": "QNX071", "util": "QNX072", "rt": "QNX073"}[fm.group(1)]
            out.append(_rel_finding(rid, rel, ln, f"find_library('{fm.group(1)}') is required", st,
                                    snippet=lines[ln - 1].strip(), symbol=fm.group(1)))
        for lm in re.finditer(r"'-l(pthread|dl|util|rt)'", code):
            rid = {"pthread": "QNX070", "dl": "QNX071", "util": "QNX072", "rt": "QNX073"}[lm.group(1)]
            out.append(_rel_finding(rid, rel, ln, f"links '-l{lm.group(1)}'", st, snippet=lines[ln - 1].strip(),
                                    symbol="-l" + lm.group(1)))
        if re.search(r"c_std\s*=\s*(?:c89|c90|gnu89|gnu90)\b", code):
            out.append(_rel_finding("QNX074", rel, ln, "Meson c_std is C89/C90", st, snippet=lines[ln - 1].strip()))
        if "-fsplit-stack" in code:
            out.append(_rel_finding("QNX078", rel, ln, "-fsplit-stack", st, snippet=lines[ln - 1].strip()))
    return out


def _strip_meson_comment(line: str) -> str:
    out, q = [], False
    for ch in line:
        if ch == "'":
            q = not q
        if ch == "#" and not q:
            break
        out.append(ch)
    return "".join(out)


# ----------------------------------------------------------------------------- Autotools / Make
def analyze_config_sub(rel: str, text: str) -> list:
    m = re.search(r"timestamp='(\d{4})-(\d{2})-(\d{2})'", text)
    year = int(m.group(1)) if m else None
    if not re.search(r"nto-qnx|qnx", text):
        return [_rel_finding("QNX079", rel, 1, "config.sub has no QNX support at all", True, "blocker")]
    if year is not None and year < 2021:
        line = text[:m.start()].count("\n") + 1
        return [_rel_finding("QNX079", rel, line, f"config.sub is from {year}; QNX ports refresh "
                             "helper scripts this old", None)]
    return []


def analyze_autoconf(rel: str, text: str) -> list:
    out = []
    lines = text.split("\n")
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("#") or s.startswith("dnl"):
            continue
        for lm in re.finditer(r"(?:LIBS|LDFLAGS|_LDADD|_LIBADD)\s*=.*?-l(pthread|dl|util|rt)\b", line):
            rid = {"pthread": "QNX070", "dl": "QNX071", "util": "QNX072", "rt": "QNX073"}[lm.group(1)]
            out.append(_rel_finding(rid, rel, i, f"hard-codes -l{lm.group(1)}", None, "review", s,
                                    "-l" + lm.group(1)))
        if C90_RE.search(line):
            out.append(_rel_finding("QNX074", rel, i, f"compiles with {C90_RE.search(line).group(0)}", None,
                                    snippet=s))
        if "-fsplit-stack" in line:
            out.append(_rel_finding("QNX078", rel, i, "-fsplit-stack", None, snippet=s))
    # case "$host_os" ... *) AC_MSG_ERROR  without a qnx/nto pattern
    for m in re.finditer(r"case\s+\"?\$\{?(host_os|host|target_os|host_cpu_os)\}?\"?\s+in(.*?)\besac\b", text, re.S):
        body = m.group(2)
        if re.search(r"linux", body) and not re.search(r"qnx|nto", body, re.I) and \
                re.search(r"\*\)\s*(?:\n\s*)?AC_MSG_ERROR", body):
            line = text[:m.start()].count("\n") + 1
            out.append(_rel_finding("QNX076", rel, line, f"case ${m.group(1)} has no QNX entry and errors out "
                                    "for unknown systems", None, "review", lines[line - 1].strip()))
    return out


def analyze_makefile(rel: str, text: str) -> list:
    out = []
    for i, line in enumerate(text.split("\n"), 1):
        s = line.strip()
        if s.startswith("#"):
            continue
        for lm in re.finditer(r"(?<![\w-])-l(pthread|dl|util|rt)\b", line):
            rid = {"pthread": "QNX070", "dl": "QNX071", "util": "QNX072", "rt": "QNX073"}[lm.group(1)]
            out.append(_rel_finding(rid, rel, i, f"Makefile links -l{lm.group(1)}", None, "review", s,
                                    "-l" + lm.group(1)))
        if C90_RE.search(line):
            out.append(_rel_finding("QNX074", rel, i, f"compiles with {C90_RE.search(line).group(0)}", None,
                                    snippet=s))
        if "-fsplit-stack" in line:
            out.append(_rel_finding("QNX078", rel, i, "-fsplit-stack", None, snippet=s))
    return out
