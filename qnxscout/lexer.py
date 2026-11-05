"""Position-preserving C/C++ lexer.

The scanner never needs a full C++ parser, but it must not be fooled by
comments, string literals or ``#if 0`` blocks.  ``lex()`` returns a copy of the
source in which comments and the *contents* of string/char literals are
replaced by spaces.  Every other byte (including newlines) is kept, so a match
at offset ``i`` in the cleaned text is at the same line and column in the
original file.

It also returns the preprocessor directives (with backslash continuations
joined) and the string literals, which a few rules inspect.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = ["Directive", "StrLit", "Lexed", "lex"]


@dataclass
class Directive:
    line: int        # 1-based physical line of the '#'
    end_line: int    # last physical line (continuations included)
    name: str        # if, ifdef, ifndef, elif, else, endif, define, include, error, ...
    text: str        # everything after the directive name, comments removed, joined
    raw: str         # the original physical line(s), joined (used for #include paths)


@dataclass
class StrLit:
    line: int
    value: str


@dataclass
class Lexed:
    code: str
    lines: list[str]
    directives: list[Directive]
    strings: list[StrLit]
    directive_lines: set[int] = field(default_factory=set)
    line_offsets: list[int] = field(default_factory=list)

    def line_of(self, offset: int) -> int:
        """1-based line number of a character offset in ``code``."""
        lo, hi = 0, len(self.line_offsets) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.line_offsets[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1


_IDENT_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
_RAW_PREFIX = re.compile(r"(?:u8|[uUL])?R$")
_DIRECTIVE_RE = re.compile(r"^[ \t]*#[ \t]*([A-Za-z_]+)?(.*)$", re.S)


def _is_digit_separator(src: str, i: int) -> bool:
    """True if the quote at src[i] is a C++14 digit separator (1'000'000)."""
    j = i - 1
    while j >= 0 and (src[j].isalnum() or src[j] in "'._"):
        j -= 1
    start = j + 1
    return start < i and src[start].isdigit() and i + 1 < len(src) and src[i + 1].isalnum()


def lex(src: str) -> Lexed:
    n = len(src)
    out = list(src)
    strings: list[StrLit] = []
    i = 0
    line = 1

    def blank(a: int, b: int) -> None:
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c == "/" and i + 1 < n:
            nxt = src[i + 1]
            if nxt == "/":
                j = i + 2
                # A line comment continues across backslash-newline.
                while j < n and src[j] != "\n":
                    if src[j] == "\\" and j + 1 < n and src[j + 1] == "\n":
                        j += 2
                        line += 1
                        continue
                    j += 1
                blank(i, j)
                i = j
                continue
            if nxt == "*":
                j = src.find("*/", i + 2)
                j = n if j < 0 else j + 2
                line += src.count("\n", i, j)
                blank(i, j)
                i = j
                continue
        if c == '"':
            prefix_start = i
            while prefix_start > 0 and src[prefix_start - 1] in "u8ULR":
                prefix_start -= 1
            prefix = src[prefix_start:i]
            before = src[prefix_start - 1] if prefix_start > 0 else ""
            if prefix and _RAW_PREFIX.search(prefix) and before not in _IDENT_CHARS:
                # Raw string literal R"delim( ... )delim"
                paren = src.find("(", i + 1, i + 20)
                if paren > 0:
                    delim = src[i + 1:paren]
                    end = src.find(")" + delim + '"', paren + 1)
                    end = n if end < 0 else end
                    strings.append(StrLit(line, src[paren + 1:end]))
                    line += src.count("\n", i, end)
                    blank(i + 1, min(end + len(delim) + 1, n))
                    i = min(end + len(delim) + 2, n)
                    continue
            j = i + 1
            while j < n and src[j] != '"' and src[j] != "\n":
                if src[j] == "\\" and j + 1 < n:
                    if src[j + 1] == "\n":
                        line += 1
                    j += 2
                    continue
                j += 1
            strings.append(StrLit(line, src[i + 1:j]))
            blank(i + 1, j)
            i = j + 1 if j < n and src[j] == '"' else j
            continue
        if c == "'":
            if _is_digit_separator(src, i):
                i += 1
                continue
            j = i + 1
            while j < n and src[j] != "'" and src[j] != "\n":
                if src[j] == "\\" and j + 1 < n and src[j + 1] != "\n":
                    j += 2
                    continue
                j += 1
            blank(i + 1, j)
            i = j + 1 if j < n and src[j] == "'" else j
            continue
        i += 1

    code = "".join(out)
    lines = code.split("\n")
    raw_lines = src.split("\n")
    offsets = [0]
    for ln in lines[:-1]:
        offsets.append(offsets[-1] + len(ln) + 1)

    directives: list[Directive] = []
    directive_lines: set[int] = set()
    k = 0
    total = len(lines)
    while k < total:
        stripped = lines[k].lstrip()
        if stripped.startswith("#"):
            start = k
            parts = [lines[k]]
            raw_parts = [raw_lines[k] if k < len(raw_lines) else ""]
            while parts[-1].rstrip().endswith("\\") and k + 1 < total:
                parts[-1] = parts[-1].rstrip()[:-1]
                raw_parts[-1] = raw_parts[-1].rstrip()[:-1]
                k += 1
                parts.append(lines[k])
                raw_parts.append(raw_lines[k] if k < len(raw_lines) else "")
            joined = " ".join(p.strip() for p in parts)
            m = _DIRECTIVE_RE.match(joined)
            name = (m.group(1) or "") if m else ""
            text = (m.group(2) if m else "").strip()
            directives.append(Directive(start + 1, k + 1, name, text, " ".join(r.strip() for r in raw_parts)))
            directive_lines.update(range(start + 1, k + 2))
        k += 1

    return Lexed(code, lines, directives, strings, directive_lines, offsets)
