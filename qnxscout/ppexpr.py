"""Tri-state evaluation of C preprocessor ``#if`` expressions.

Values are ``int`` when the result is known for the QNX target model and
``None`` when it depends on something the scanner cannot know (a configure
result, a compiler flag, a macro defined in a generated header, ...).

Unknowns propagate, but logical operators short-circuit exactly like the real
preprocessor, so ``defined(__linux__) && HAVE_FOO`` is known to be 0 on QNX
even though ``HAVE_FOO`` is unknown.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

Val = Optional[int]

# A resolver answers "what do we know about macro NAME?" with one of
#   ("def", value_or_None)  - defined (value None when not an integer)
#   ("undef", None)         - known to be undefined
#   ("unknown", None)       - can't tell
Resolver = Callable[[str], tuple]
HeaderOracle = Callable[[str], Optional[bool]]

_TOKEN = re.compile(
    r"""\s*(?:
        (?P<num>0[xX][0-9A-Fa-f']+|0[bB][01']+|\d[\d']*)(?P<suf>[uUlL]*)
      | (?P<id>[A-Za-z_][A-Za-z0-9_]*)
      | (?P<hdr><[^>\n]*>)
      | (?P<chr>'[^'\n]*')
      | (?P<str>"[^"\n]*")
      | (?P<op>\|\||&&|==|!=|<=|>=|<<|>>|[-+*/%<>!~&|^?:(),])
    )""",
    re.X,
)

_UNKNOWN_FUNCS = {
    "__has_feature", "__has_extension", "__has_builtin", "__has_attribute",
    "__has_cpp_attribute", "__has_c_attribute", "__has_declspec_attribute",
    "__has_warning", "__is_identifier", "__building_module",
}


class _Unparsable(Exception):
    pass


def _tokenize(text: str) -> list:
    toks = []
    pos = 0
    text = text.strip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            if text[pos:].strip() == "":
                break
            raise _Unparsable(text[pos:])
        pos = m.end()
        if m.group("num") is not None:
            s = m.group("num").replace("'", "")
            try:
                if s[:2] in ("0x", "0X"):
                    v = int(s, 16)
                elif s[:2] in ("0b", "0B"):
                    v = int(s[2:], 2)
                elif len(s) > 1 and s[0] == "0":
                    v = int(s, 8)
                else:
                    v = int(s)
            except ValueError:
                raise _Unparsable(s)
            toks.append(("num", v))
        elif m.group("id") is not None:
            toks.append(("id", m.group("id")))
        elif m.group("hdr") is not None:
            toks.append(("hdr", m.group("hdr")[1:-1].strip()))
        elif m.group("chr") is not None:
            body = m.group("chr")[1:-1]
            toks.append(("num", ord(body) if len(body) == 1 and body != " " else None))
        elif m.group("str") is not None:
            toks.append(("str", m.group("str")[1:-1].strip()))
        else:
            toks.append(("op", m.group("op")))
    return toks


class _Parser:
    def __init__(self, toks, resolve: Resolver, headers: HeaderOracle, cplusplus: bool):
        self.t = toks
        self.i = 0
        self.resolve = resolve
        self.headers = headers
        self.cpp = cplusplus
        self.used_names: set[str] = set()

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self, kind=None, val=None):
        tok = self.peek()
        if tok[0] is None or (kind and tok[0] != kind) or (val is not None and tok[1] != val):
            raise _Unparsable(str(tok))
        self.i += 1
        return tok

    def at_op(self, *ops):
        k, v = self.peek()
        return k == "op" and v in ops

    # Grammar, lowest precedence first.
    def expr(self) -> Val:
        v = self.ternary()
        while self.at_op(","):
            self.take()
            v = self.ternary()
        return v

    def ternary(self) -> Val:
        c = self.lor()
        if self.at_op("?"):
            self.take()
            a = self.expr()
            self.take("op", ":")
            b = self.ternary()
            if c is None:
                return a if (a is not None and a == b) else None
            return a if c else b
        return c

    def lor(self) -> Val:
        a = self.land()
        while self.at_op("||"):
            self.take()
            b = self.land()
            if a is not None and a != 0:
                a = 1
            elif a == 0:
                a = None if b is None else int(b != 0)
            else:
                a = 1 if (b is not None and b != 0) else None
        return a

    def land(self) -> Val:
        a = self.bor()
        while self.at_op("&&"):
            self.take()
            b = self.bor()
            if a == 0:
                a = 0
            elif a is not None:
                a = None if b is None else int(b != 0)
            else:
                a = 0 if b == 0 else None
        return a

    def _binary(self, sub, ops):
        a = sub()
        while self.at_op(*ops):
            op = self.take()[1]
            b = sub()
            a = _apply(op, a, b)
        return a

    def bor(self):
        return self._binary(self.bxor, ("|",))

    def bxor(self):
        return self._binary(self.band, ("^",))

    def band(self):
        return self._binary(self.equality, ("&",))

    def equality(self):
        return self._binary(self.relational, ("==", "!="))

    def relational(self):
        return self._binary(self.shift, ("<", ">", "<=", ">="))

    def shift(self):
        return self._binary(self.additive, ("<<", ">>"))

    def additive(self):
        return self._binary(self.mult, ("+", "-"))

    def mult(self):
        return self._binary(self.unary, ("*", "/", "%"))

    def unary(self) -> Val:
        if self.at_op("!"):
            self.take()
            v = self.unary()
            return None if v is None else int(v == 0)
        if self.at_op("-"):
            self.take()
            v = self.unary()
            return None if v is None else -v
        if self.at_op("+"):
            self.take()
            return self.unary()
        if self.at_op("~"):
            self.take()
            v = self.unary()
            return None if v is None else ~v
        return self.primary()

    def _skip_parens(self):
        depth = 0
        while True:
            k, v = self.take()
            if k == "op" and v == "(":
                depth += 1
            elif k == "op" and v == ")":
                depth -= 1
                if depth == 0:
                    return

    def primary(self) -> Val:
        k, v = self.peek()
        if k == "num":
            self.take()
            return v
        if k == "op" and v == "(":
            self.take()
            r = self.expr()
            self.take("op", ")")
            return r
        if k == "id":
            self.take()
            if v == "defined":
                if self.at_op("("):
                    self.take()
                    name = self.take("id")[1]
                    self.take("op", ")")
                else:
                    name = self.take("id")[1]
                self.used_names.add(name)
                state, _ = self.resolve(name)
                return {"def": 1, "undef": 0}.get(state)
            if v in ("__has_include", "__has_include_next"):
                self.take("op", "(")
                hk, hv = self.take()
                if hk == "hdr":
                    res = self.headers(hv)
                    self.take("op", ")")
                    return None if res is None else int(res)
                # "quoted" or macro-expanded include: unknown
                while not self.at_op(")"):
                    self.take()
                self.take("op", ")")
                return None
            if self.cpp and v in ("true", "false"):
                return int(v == "true")
            self.used_names.add(v)
            if self.at_op("("):
                # Function-like macro invocation.
                self._skip_parens()
                if v in _UNKNOWN_FUNCS:
                    return None
                state, val = self.resolve(v)
                if state == "undef":
                    # Using an undefined function-like macro in #if is an
                    # error in real compilers; such uses are virtually always
                    # protected by a short-circuiting defined() check.
                    return 0
                return None
            state, val = self.resolve(v)
            if state == "undef":
                return 0
            if state == "def":
                return val
            return None
        raise _Unparsable(str((k, v)))


def _apply(op: str, a: Val, b: Val) -> Val:
    if a is None or b is None:
        return None
    try:
        if op == "|":
            return a | b
        if op == "^":
            return a ^ b
        if op == "&":
            return a & b
        if op == "==":
            return int(a == b)
        if op == "!=":
            return int(a != b)
        if op == "<":
            return int(a < b)
        if op == ">":
            return int(a > b)
        if op == "<=":
            return int(a <= b)
        if op == ">=":
            return int(a >= b)
        if op == "<<":
            return a << b if 0 <= b < 128 else None
        if op == ">>":
            return a >> b if 0 <= b < 128 else None
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            return None if b == 0 else int(a / b)
        if op == "%":
            return None if b == 0 else a - b * int(a / b)
    except (OverflowError, ValueError):
        return None
    return None


def evaluate(text: str, resolve: Resolver, headers: HeaderOracle, cplusplus: bool = False):
    """Evaluate an #if/#elif expression.

    Returns ``(value, names)`` where value is 1/0/None and ``names`` is the set
    of macro names the expression referred to.
    """
    try:
        toks = _tokenize(text)
        if not toks:
            return None, set()
        p = _Parser(toks, resolve, headers, cplusplus)
        v = p.expr()
        if p.i != len(toks):
            return None, p.used_names
        return (None if v is None else int(v != 0)), p.used_names
    except (_Unparsable, RecursionError):
        names = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)) - {"defined"}
        return None, names
