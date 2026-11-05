"""Walk the preprocessor directives of one file under the QNX target model.

Produces, for every physical line, whether the QNX build compiles it:
``True`` (yes), ``False`` (no - excluded by #if), or ``None`` (depends on
something only the real build knows, e.g. a configure result).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import kb
from .lexer import Lexed
from .ppexpr import evaluate

Tri = Optional[bool]


def and3(a: Tri, b: Tri) -> Tri:
    if a is False or b is False:
        return False
    if a is True and b is True:
        return True
    return None


@dataclass
class Branch:
    line: int
    kind: str            # if | elif | else
    text: str
    value: Tri           # value of this branch's own condition
    taken: Tri           # whether QNX compiles this branch (chain logic applied)
    names: set
    end_line: int = 0
    win_include: bool = False


@dataclass
class Chain:
    start: int
    branches: list = field(default_factory=list)
    end: int = 0
    parent_eff: Tri = True

    def platform_names(self) -> set:
        out = set()
        for b in self.branches:
            out |= {n for n in b.names if kb.PLATFORM_MACRO_RE.match(n)}
        return out


@dataclass
class Include:
    line: int
    header: str
    angled: bool
    state: Tri
    guards: frozenset


@dataclass
class ErrorDirective:
    line: int
    text: str
    state: Tri
    platform: bool


@dataclass
class Define:
    line: int
    name: str
    value: str
    state: Tri
    function_like: bool


@dataclass
class PPResult:
    line_state: list          # index 1..N -> Tri
    line_guards: list         # index 1..N -> frozenset of macro names in enclosing conditions
    includes: list
    errors: list
    defines: list
    chains: list
    guard_macro: Optional[str]


_PREFIXED_HAVE = re.compile(r"^[A-Z][A-Z0-9]*_+HAVE_([A-Z0-9_]+)$")
_INT_RE = re.compile(r"^\(?\s*(-?)(0[xX][0-9A-Fa-f]+|\d+)[uUlL]*\s*\)?$")


def parse_int(text: str):
    m = _INT_RE.match(text.strip())
    if not m:
        return None
    v = int(m.group(2), 0) if m.group(2).lower().startswith("0x") else int(m.group(2), 8 if m.group(2).startswith("0") and len(m.group(2)) > 1 else 10)
    return -v if m.group(1) else v


class MacroEnv:
    """Layered macro knowledge: file-local > project facts > target model > configure predictions."""

    def __init__(self, arch: str = "any", project_facts: Optional[dict] = None,
                 never_defined: Optional[Callable[[str], bool]] = None):
        self.target = dict(kb.TARGET_DEFINED)
        if arch in kb.ARCH_MACROS:
            self.target.update(kb.ARCH_MACROS[arch])
            self.arch_undef = kb.ALL_ARCH_MACROS - set(kb.ARCH_MACROS[arch])
        else:
            self.arch_undef = set()
        self.project = project_facts or {}
        self.never_defined = never_defined

    def resolve(self, name: str, local: dict):
        if name in local:
            return local[name]
        if name in self.project:
            return self.project[name]
        if name in self.target:
            return ("def", self.target[name])
        if name in kb.TARGET_UNDEFINED or name in self.arch_undef:
            return ("undef", None)
        fact = kb.HAVE_FACTS.get(name)
        if fact is None:
            m = _PREFIXED_HAVE.match(name)
            if m:
                fact = kb.HAVE_FACTS.get("HAVE_" + m.group(1))
        if fact == "def":
            return ("def", 1)
        if fact == "undef":
            return ("undef", None)
        if self.never_defined and self.never_defined(name):
            return ("undef", None)
        return ("unknown", None)


def run(lexed: Lexed, env: MacroEnv, cplusplus: bool = False,
        header_oracle: Callable[[str], Optional[bool]] = kb.header_known) -> PPResult:
    n = len(lexed.lines)
    line_state: list = [True] * (n + 2)
    line_guards: list = [frozenset()] * (n + 2)
    includes, errors, defines, chains = [], [], [], []
    local: dict = {}

    def resolve(name):
        return env.resolve(name, local)

    # Include-guard detection: first directive '#ifndef X' immediately followed by '#define X'.
    dirs = lexed.directives
    guard_macro = None
    if len(dirs) >= 2 and dirs[0].name == "ifndef" and dirs[1].name == "define":
        g = dirs[0].text.split()[0] if dirs[0].text.split() else ""
        d = dirs[1].text.split()[0] if dirs[1].text.split() else ""
        if g and g == d:
            guard_macro = g
    elif len(dirs) >= 2 and dirs[0].name == "if" and dirs[1].name == "define":
        m = re.match(r"!\s*defined\s*\(?\s*([A-Za-z_]\w*)\s*\)?\s*$", dirs[0].text)
        d = dirs[1].text.split()[0] if dirs[1].text.split() else ""
        if m and m.group(1) == d:
            guard_macro = d

    stack: list = []   # list of (Chain, frame dict)
    eff: Tri = True
    guards_now: frozenset = frozenset()
    platform_ctx = False
    pos = 1

    def fill(upto: int):
        nonlocal pos
        while pos <= upto and pos <= n:
            line_state[pos] = eff
            line_guards[pos] = guards_now
            pos += 1

    def recompute():
        nonlocal eff, guards_now, platform_ctx
        e: Tri = True
        names = set()
        plat = False
        for chain, fr in stack:
            e = and3(e, fr["branch"])
            names |= fr["names"]
            if chain.platform_names():
                plat = True
        eff = e
        guards_now = frozenset(names)
        platform_ctx = plat

    def close_branch(chain: Chain, end_line: int):
        if chain.branches:
            chain.branches[-1].end_line = end_line

    for idx, d in enumerate(dirs):
        fill(d.line - 1)
        name = d.name
        if name in ("if", "ifdef", "ifndef"):
            if name == "if":
                val, names = evaluate(d.text, resolve, header_oracle, cplusplus)
            else:
                macro = d.text.split()[0] if d.text.split() else ""
                names = {macro} if macro else set()
                if name == "ifndef" and idx == 0 and macro and macro == guard_macro:
                    val = 1
                else:
                    st, _ = resolve(macro) if macro else ("unknown", None)
                    val = {"def": 1, "undef": 0}.get(st)
                    if name == "ifndef" and val is not None:
                        val = 1 - val
            tv: Tri = None if val is None else bool(val)
            chain = Chain(start=d.line, parent_eff=eff)
            chain.branches.append(Branch(d.line, "if", d.text, tv, tv, set(names)))
            fr = {"branch": tv, "taken": tv is True, "maybe": tv is None, "names": set(names)}
            stack.append((chain, fr))
            recompute()
            line_state[d.line] = eff
            line_guards[d.line] = guards_now
            pos = d.end_line + 1
            continue
        if name in ("elif", "elifdef", "elifndef", "else"):
            if not stack:
                pos = max(pos, d.end_line + 1)
                continue
            chain, fr = stack[-1]
            close_branch(chain, d.line - 1)
            if name == "else":
                val, names = 1, set()
            elif name == "elif":
                val, names = evaluate(d.text, resolve, header_oracle, cplusplus)
            else:
                macro = d.text.split()[0] if d.text.split() else ""
                names = {macro} if macro else set()
                st, _ = resolve(macro) if macro else ("unknown", None)
                val = {"def": 1, "undef": 0}.get(st)
                if name == "elifndef" and val is not None:
                    val = 1 - val
            v: Tri = None if val is None else bool(val)
            if fr["taken"]:
                bv: Tri = False
            elif not fr["maybe"]:
                bv = v
            else:
                bv = False if v is False else None
            fr["taken"] = fr["taken"] or bv is True
            fr["maybe"] = fr["maybe"] or bv is None
            fr["branch"] = bv
            fr["names"] |= set(names)
            chain.branches.append(Branch(d.line, "else" if name == "else" else "elif", d.text, v, bv, set(names)))
            recompute()
            line_state[d.line] = eff
            line_guards[d.line] = guards_now
            pos = d.end_line + 1
            continue
        if name == "endif":
            if stack:
                chain, fr = stack.pop()
                close_branch(chain, d.line - 1)
                chain.end = d.line
                chain.parent_eff = chain.parent_eff
                chains.append(chain)
            recompute()
            line_state[d.line] = eff
            line_guards[d.line] = guards_now
            pos = d.end_line + 1
            continue

        # Non-conditional directives take the current state.
        for ln in range(d.line, d.end_line + 1):
            if ln <= n:
                line_state[ln] = eff
                line_guards[ln] = guards_now
        pos = d.end_line + 1
        if name in ("include", "include_next", "import"):
            m = re.search(r"#\s*(?:include_next|include|import)\s*([<\"])([^>\"]+)[>\"]", d.raw)
            if m:
                inc = Include(d.line, m.group(2).strip(), m.group(1) == "<", eff, guards_now)
                includes.append(inc)
                if stack and eff is not False and kb.WINDOWS_HEADERS.match(inc.header):
                    stack[-1][0].branches[-1].win_include = True
        elif name == "define":
            m = re.match(r"([A-Za-z_]\w*)(\()?\s*(.*)$", d.text, re.S)
            if m:
                mname, fnlike, value = m.group(1), bool(m.group(2)), m.group(3).strip()
                defines.append(Define(d.line, mname, value, eff, fnlike))
                if eff is True:
                    local[mname] = ("def", None if fnlike else parse_int(value) if value else 1)
                elif eff is None:
                    local[mname] = ("unknown", None)
        elif name == "undef":
            mname = d.text.split()[0] if d.text.split() else ""
            if mname:
                if eff is True:
                    local[mname] = ("undef", None)
                elif eff is None:
                    local[mname] = ("unknown", None)
        elif name in ("error",):
            errors.append(ErrorDirective(d.line, re.sub(r'^\s*#\s*error\s*', '', d.raw).strip(), eff, platform_ctx))
    fill(n)
    # Unterminated conditionals: close them so the analysis still reports.
    while stack:
        chain, fr = stack.pop()
        close_branch(chain, n)
        chain.end = n
        chains.append(chain)
    return PPResult(line_state, line_guards, includes, errors, defines, chains, guard_macro)
