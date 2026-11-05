"""Verify findings against an installed QNX SDP (``--sdp $QNX_TARGET``).

The built-in knowledge base is derived from public documentation and QNX's
own ports.  With an SDP on disk we can do better: check every reported header
against ``$QNX_TARGET/usr/include`` and every reported function against the
symbols the target libraries actually export (read straight from the ELF
``.dynsym`` sections; no QNX tools needed, so this works on any host).
"""
from __future__ import annotations

import os
import re
import struct
from collections import defaultdict

from . import kb

ARCH_DIRS = {"x86_64": ["x86_64"], "aarch64le": ["aarch64le"], "any": ["x86_64", "aarch64le"]}


def elf_exports(path: str) -> set:
    """Names of defined, global/weak dynamic symbols in an ELF shared object."""
    out = set()
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return out
    if data[:4] != b"\x7fELF":
        return out
    is64 = data[4] == 2
    end = "<" if data[5] == 1 else ">"
    if is64:
        shoff, = struct.unpack_from(end + "Q", data, 0x28)
        shentsize, shnum = struct.unpack_from(end + "HH", data, 0x3A)
    else:
        shoff, = struct.unpack_from(end + "I", data, 0x20)
        shentsize, shnum = struct.unpack_from(end + "HH", data, 0x2E)
    sections = []
    for i in range(shnum):
        off = shoff + i * shentsize
        if off + shentsize > len(data):
            break
        if is64:
            name, typ, flags, addr, offset, size, link, info, align, entsize = struct.unpack_from(
                end + "IIQQQQIIQQ", data, off)
        else:
            name, typ, flags, addr, offset, size, link, info, align, entsize = struct.unpack_from(
                end + "IIIIIIIIII", data, off)
        sections.append((typ, offset, size, link, entsize))
    for typ, offset, size, link, entsize in sections:
        if typ != 11 or link >= len(sections):          # SHT_DYNSYM
            continue
        str_off, str_size = sections[link][1], sections[link][2]
        entsize = entsize or (24 if is64 else 16)
        for k in range(size // entsize):
            o = offset + k * entsize
            if is64:
                st_name, st_info, st_other, st_shndx = struct.unpack_from(end + "IBBH", data, o)
            else:
                st_name, _val, _sz, st_info, st_other, st_shndx = struct.unpack_from(end + "IIIBBH", data, o)
            bind = st_info >> 4
            if st_shndx == 0 or bind not in (1, 2):      # undefined, or not GLOBAL/WEAK
                continue
            s = str_off + st_name
            e = data.find(b"\0", s, str_off + str_size)
            if e > s:
                out.add(data[s:e].decode("ascii", "replace"))
    return out


class SDP:
    def __init__(self, root: str, arch: str = "any"):
        self.root = os.path.abspath(os.path.expanduser(root))
        if not os.path.isdir(os.path.join(self.root, "usr", "include")):
            raise SystemExit(f"--sdp: {self.root} does not look like $QNX_TARGET (no usr/include)")
        self.headers = set()
        inc = os.path.join(self.root, "usr", "include")
        for dp, _dn, fns in os.walk(inc):
            for fn in fns:
                self.headers.add(os.path.relpath(os.path.join(dp, fn), inc).replace(os.sep, "/"))
        self.symbols = defaultdict(set)      # symbol -> {libname}
        self.libs = set()
        for a in ARCH_DIRS.get(arch, ARCH_DIRS["any"]):
            for sub in ("lib", "usr/lib"):
                d = os.path.join(self.root, a, sub)
                if not os.path.isdir(d):
                    continue
                for fn in os.listdir(d):
                    if ".so" not in fn:
                        continue
                    lib = re.sub(r"^lib|\.so.*$", "", fn)
                    self.libs.add(lib)
                    for sym in elf_exports(os.path.join(d, fn)):
                        self.symbols[sym].add(lib)
        self._macro_cache: dict = {}

    def header_defines(self, macro: str) -> bool:
        if macro in self._macro_cache:
            return self._macro_cache[macro]
        rx = re.compile(r"^\s*#\s*define\s+" + re.escape(macro) + r"\b", re.M)
        found = False
        inc = os.path.join(self.root, "usr", "include")
        for h in self.headers:
            if not h.endswith(".h"):
                continue
            try:
                with open(os.path.join(inc, h), errors="replace") as fh:
                    if rx.search(fh.read()):
                        found = True
                        break
            except OSError:
                continue
        self._macro_cache[macro] = found
        return found

    def refine(self, findings: list) -> list:
        out = []
        for f in findings:
            rule = kb.RULES_BY_ID[f.rule]
            sym = f.symbol
            if f.message.startswith("#include <") and sym:
                if sym in self.headers:
                    f.severity, f.note = "info", f"<{sym}> exists in your SDP ({self.root})"
                else:
                    f.note = f"confirmed: <{sym}> is not in your SDP"
            elif sym and sym in rule.calls:
                libs = self.symbols.get(sym)
                if libs and "c" in libs:
                    f.severity, f.note = "info", f"your SDP's libc exports {sym}()"
                elif libs:
                    f.severity = "link"
                    f.note = f"{sym}() is exported by " + ", ".join("lib" + l for l in sorted(libs)) + \
                             " in your SDP: link " + " ".join("-l" + l for l in sorted(libs))
                elif self.symbols:
                    f.note = f"confirmed: no library in your SDP exports {sym}()"
            elif sym and sym in rule.words and re.fullmatch(r"[A-Z_][A-Z0-9_]+", sym):
                if self.header_defines(sym):
                    f.severity, f.note = "info", f"{sym} is defined by your SDP headers"
                else:
                    f.note = f"confirmed: {sym} is not defined in your SDP headers"
            if rule.severity == "link" and rule.link.startswith("-l") and self.libs:
                if rule.link[2:] not in self.libs:
                    f.note = (f.note + "; " if f.note else "") + \
                        f"lib{rule.link[2:]} is not in this SDP: install the QNX package that provides it on the target"
            out.append(f)
        return out
