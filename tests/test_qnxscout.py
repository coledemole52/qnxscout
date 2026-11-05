import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from qnxscout import buildsys, kb  # noqa: E402
from qnxscout.lexer import lex  # noqa: E402
from qnxscout.ppexpr import evaluate  # noqa: E402
from qnxscout.preproc import MacroEnv, run  # noqa: E402
from qnxscout.scanner import platform_of_path, scan  # noqa: E402
from qnxscout.sdp import elf_exports  # noqa: E402

SAMPLE = os.path.join(HERE, "fixtures", "sample")


def resolver(table):
    def r(name):
        if name in table:
            v = table[name]
            return ("undef", None) if v is None else ("def", v)
        return ("unknown", None)
    return r


def no_headers(_h):
    return None


class LexerTests(unittest.TestCase):
    def test_comments_and_strings_are_blanked_but_positions_kept(self):
        src = 'int a; /* epoll_wait( */ const char *s = "epoll_ctl("; // x(\nint b;\n'
        lx = lex(src)
        self.assertEqual(len(lx.code), len(src))
        self.assertNotIn("epoll", lx.code)
        self.assertEqual(lx.lines[1], "int b;")
        self.assertEqual([s.value for s in lx.strings], ["epoll_ctl("])

    def test_raw_strings_and_digit_separators(self):
        src = 'auto r = R"x(a "quoted" epoll_wait( )x"; int n = 1\'000\'000; int m = epoll;\n'
        lx = lex(src)
        self.assertNotIn("epoll_wait", lx.code)
        self.assertIn("int m = epoll;", lx.code)

    def test_directive_continuation(self):
        lx = lex("#if defined(A) && \\\n    defined(B)\nx\n#endif\n")
        self.assertEqual(lx.directives[0].name, "if")
        self.assertIn("defined(B)", lx.directives[0].text)
        self.assertEqual(lx.directives[1].line, 4)


class ExprTests(unittest.TestCase):
    def ev(self, text, table=None, cpp=False):
        return evaluate(text, resolver(table or {}), no_headers, cpp)[0]

    def test_short_circuit_with_unknowns(self):
        t = {"__linux__": None, "__QNX__": 1}
        self.assertEqual(self.ev("defined(__linux__) && HAVE_FOO", t), 0)
        self.assertEqual(self.ev("defined(__QNX__) || HAVE_FOO", t), 1)
        self.assertIsNone(self.ev("defined(__QNX__) && HAVE_FOO", t))
        self.assertIsNone(self.ev("HAVE_FOO || defined(__linux__)", t))

    def test_arithmetic_and_comparison(self):
        t = {"__GNUC__": 12, "__GNUC_MINOR__": 2}
        self.assertEqual(self.ev("__GNUC__ > 4 || (__GNUC__ == 4 && __GNUC_MINOR__ >= 6)", t), 1)
        self.assertEqual(self.ev("(1 << 4) == 0x10 && 07 == 7 && -1 < 0", t), 1)
        self.assertEqual(self.ev("1 ? 2 : 0"), 1)

    def test_function_like_and_has_include(self):
        self.assertIsNone(self.ev("__has_feature(address_sanitizer)"))
        r = evaluate("__has_include(<sys/epoll.h>)", resolver({}), lambda h: h != "sys/epoll.h")[0]
        self.assertEqual(r, 0)
        self.assertEqual(self.ev("true", cpp=True), 1)

    def test_garbage_is_unknown(self):
        self.assertIsNone(self.ev("defined("))


class PreprocTests(unittest.TestCase):
    def test_platform_chain_and_error(self):
        with open(os.path.join(SAMPLE, "src", "platform.h")) as fh:
            lx = lex(fh.read())
        pp = run(lx, MacroEnv())
        self.assertEqual(pp.guard_macro, "PLATFORM_H")
        self.assertEqual(len(pp.errors), 1)
        self.assertIs(pp.errors[0].state, True)
        futex = [i for i in pp.includes if i.header == "linux/futex.h"][0]
        self.assertIs(futex.state, False)

    def test_have_macros_follow_configure_predictions(self):
        lx = lex("#ifdef HAVE_GETRANDOM\nA\n#endif\n#ifdef HAVE_PIPE2\nB\n#endif\n#ifdef HAVE_CUSTOM\nC\n#endif\n")
        pp = run(lx, MacroEnv())
        self.assertIs(pp.line_state[2], False)   # getrandom does not exist on QNX
        self.assertIs(pp.line_state[5], True)    # pipe2 does
        self.assertIsNone(pp.line_state[8])      # unknown project option

    def test_local_defines(self):
        lx = lex("#if defined(__QNX__)\n#define OS_QNX 1\n#endif\n#if OS_QNX\nyes\n#else\nno\n#endif\n")
        pp = run(lx, MacroEnv())
        self.assertIs(pp.line_state[5], True)
        self.assertIs(pp.line_state[7], False)

    def test_arch_model(self):
        src = "#if defined(__x86_64__)\nx\n#elif defined(__aarch64__)\na\n#elif defined(__powerpc__)\np\n#endif\n"
        pp_any = run(lex(src), MacroEnv("any"))
        pp_x86 = run(lex(src), MacroEnv("x86_64"))
        self.assertIsNone(pp_any.line_state[2])
        self.assertIs(pp_x86.line_state[2], True)
        self.assertIs(pp_x86.line_state[4], False)
        self.assertIs(pp_any.line_state[6], False)


class BuildSystemTests(unittest.TestCase):
    def test_cmake(self):
        with open(os.path.join(SAMPLE, "CMakeLists.txt")) as fh:
            txt = fh.read()
        f = buildsys.analyze_cmake("CMakeLists.txt", txt)
        rules = sorted({x.rule for x in f})
        self.assertIn("QNX074", rules)   # C90
        self.assertIn("QNX075", rules)   # Linux-only branch
        self.assertIn("QNX076", rules)   # FATAL_ERROR reached
        self.assertIn("QNX070", rules)   # pthread
        self.assertIn("QNX071", rules)   # dl
        self.assertNotIn("QNX073", rules)  # rt is only linked on WIN32

    def test_meson(self):
        txt = ("project('x','c', default_options: ['c_std=gnu89'])\n"
               "sys = host_machine.system()\n"
               "if sys == 'linux'\n  dep = cc.find_library('rt')\nelif sys == 'darwin'\n  x = 1\n"
               "else\n  error('unsupported system')\nendif\n"
               "if host_machine.system() != 'windows'\n  m = cc.find_library('dl')\nendif\n")
        f = buildsys.analyze_meson("meson.build", txt)
        rules = sorted({x.rule for x in f})
        self.assertEqual(rules, ["QNX071", "QNX074", "QNX075", "QNX076"])

    def test_config_sub(self):
        self.assertEqual(buildsys.analyze_config_sub("config.sub", "timestamp='2016-01-01'\nnto-qnx*)")[0].rule,
                         "QNX079")
        self.assertEqual(buildsys.analyze_config_sub("config.sub", "timestamp='2024-01-01'\nnto-qnx*)"), [])


class ScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = scan(SAMPLE)
        cls.by_rule = {}
        for f in cls.result.findings:
            cls.by_rule.setdefault(f.rule, []).append(f)

    def rules(self, severity_not="info"):
        return {r for r, fs in self.by_rule.items() if any(f.severity != severity_not for f in fs)}

    def test_expected_rules(self):
        expected = {"QNX001", "QNX030", "QNX032", "QNX037", "QNX038", "QNX050", "QNX054", "QNX060",
                    "QNX061", "QNX074", "QNX075", "QNX076", "QNX070", "QNX071", "QNX080"}
        self.assertTrue(expected <= self.rules(), sorted(expected - self.rules()))

    def test_no_false_positives(self):
        got = self.rules()
        self.assertNotIn("QNX031", got)       # IOV_MAX is provided by the project
        self.assertNotIn("QNX043", got)       # <linux/futex.h> only on __linux__
        msgs = " ".join(f.message for f in self.result.findings)
        self.assertNotIn("epoll_wait", msgs)  # only inside a string literal
        getrandom = self.by_rule.get("QNX011", [])
        self.assertTrue(all(f.severity == "info" for f in getrandom))

    def test_platform_specific_files_are_downgraded(self):
        bsd = [f for f in self.result.findings if f.file.endswith("osdep-freebsd.c") and f.rule != "QNX063"]
        self.assertTrue(bsd and all(f.severity == "info" for f in bsd))
        linux = [f for f in self.result.findings if f.file.endswith("osdep-linux.c") and f.rule == "QNX013"]
        self.assertTrue(linux and all(f.confidence == "medium" for f in linux))

    def test_score(self):
        sc = self.result.score
        self.assertIn(sc["grade"], "ABCDE")
        self.assertGreater(sc["points"], 0)
        self.assertIn("-lepoll", sc["link_flags"])

    def test_reports_render(self):
        from qnxscout.report import html, jsonreport, markdown, sarif, text
        import json
        for mod in (html, markdown, text):
            self.assertTrue(mod.render(self.result))
        sar = json.loads(sarif.render(self.result))
        self.assertEqual(sar["version"], "2.1.0")
        self.assertEqual(len(sar["runs"][0]["results"]), len(self.result.findings))
        self.assertEqual(json.loads(jsonreport.render(self.result))["score"]["grade"], self.result.score["grade"])


class MiscTests(unittest.TestCase):
    def test_platform_of_path(self):
        self.assertEqual(platform_of_path("src/osdep-freebsd.c"), "freebsd")
        self.assertEqual(platform_of_path("win32/thread.c"), "windows")
        self.assertIsNone(platform_of_path("src/window.c"))
        self.assertIsNone(platform_of_path("src/mac.c"))

    def test_every_rule_has_evidence_and_valid_severity(self):
        for r in kb.RULES:
            self.assertIn(r.severity, kb.SEVERITIES, r.id)
            self.assertTrue(r.evidence, r.id)
            for label, url in r.evidence_links():
                self.assertTrue(url.startswith("https://"), (r.id, url))

    def test_libc_index_facts(self):
        idx = kb.libc_index()
        self.assertEqual(idx["inotify_init"][1], "libfsnotify")
        self.assertIn("unix.h", idx["forkpty"][0])
        self.assertNotIn("epoll_create", idx)

    def test_elf_exports(self):
        lib = None
        for cand in ("/lib/x86_64-linux-gnu/libc.so.6", "/usr/lib/x86_64-linux-gnu/libc.so.6", "/lib64/libc.so.6"):
            if os.path.exists(cand):
                lib = cand
                break
        if not lib:
            self.skipTest("no host libc to read")
        syms = elf_exports(lib)
        self.assertIn("printf", syms)
        self.assertNotIn("this_symbol_does_not_exist", syms)

    def test_sdp_refinement(self):
        from qnxscout.sdp import SDP
        tmp = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(tmp, "usr", "include", "sys"))
            with open(os.path.join(tmp, "usr", "include", "signal.h"), "w") as fh:
                fh.write("#define SA_RESTART 0x0040\n")
            open(os.path.join(tmp, "usr", "include", "sys", "epoll.h"), "w").close()
            res = scan(SAMPLE, sdp=SDP(tmp))
            sa = [f for f in res.findings if f.rule == "QNX030"]
            self.assertTrue(sa and all(f.severity == "info" for f in sa))
            ep = [f for f in res.findings if f.rule == "QNX001" and f.message.startswith("#include")]
            self.assertTrue(ep and all(f.severity == "info" for f in ep))
        finally:
            shutil.rmtree(tmp)

    def test_cli(self):
        missing = os.path.join(HERE, "does-not-exist")
        out = subprocess.run([sys.executable, "-m", "qnxscout", "scan", missing],
                             cwd=os.path.dirname(HERE), capture_output=True, text=True)
        self.assertEqual(out.returncode, 1)
        self.assertIn("source path does not exist", out.stderr)
        self.assertNotIn("Grade A", out.stdout)
        out = subprocess.run([sys.executable, "-m", "qnxscout", "scan", SAMPLE, "--fail-on", "blocker"],
                             cwd=os.path.dirname(HERE), capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)
        self.assertIn("Grade", out.stdout)
        out = subprocess.run([sys.executable, "-m", "qnxscout", "explain", "QNX001"],
                             cwd=os.path.dirname(HERE), capture_output=True, text=True)
        self.assertIn("epoll", out.stdout)


class NewerRuleTests(unittest.TestCase):
    def _proj(self, files):
        tmp = tempfile.mkdtemp()
        for rel, text in files.items():
            path = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as fh:
                fh.write(text)
        self.addCleanup(shutil.rmtree, tmp)
        return scan(tmp)

    def test_socketcan_is_a_link_fix(self):
        r = self._proj({"cand.c": "#include <linux/can.h>\n#include <linux/sockios.h>\n"
                        "int s(void){ return socket(PF_CAN, 3, 1); }\n", "Makefile": "all:\n\tcc cand.c -lsocket\n"})
        rules = {(f.rule, f.symbol) for f in r.findings if f.severity != "info"}
        self.assertIn(("QNX048", "linux/can.h"), rules)
        self.assertIn(("QNX048", "linux/sockios.h"), rules)
        self.assertFalse(any(f.rule == "QNX043" for f in r.findings))

    def test_makefile_os_conditionals(self):
        mk = ("UNAME := $(shell uname -s)\nifeq ($(UNAME),Linux)\nLIBS += -lrt -ldl\nelse\nLIBS += -lm\nendif\n"
              "ifneq ($(OSTYPE),Darwin)\nLIBS += -lpthread\nendif\n")
        r = self._proj({"a.c": "int x;\n", "Makefile": mk})
        rules = {f.rule for f in r.findings}
        self.assertNotIn("QNX073", rules)
        self.assertNotIn("QNX071", rules)
        self.assertIn("QNX070", rules)

    def test_prefixed_have_macros(self):
        r = self._proj({"a.c": "#if (NGX_HAVE_SCHED_SETAFFINITY)\nvoid f(void){ sched_setaffinity(0,0,0); }\n#endif\n"})
        self.assertFalse([f for f in r.findings if f.rule == "QNX012"])

    def test_linux_file_with_generic_sibling(self):
        r = self._proj({"os/sys_linux.c": "#include <sys/prctl.h>\n", "os/sys_posix.c": "int y;\n",
                        "os/sys_freebsd.c": "int z;\n"})
        lin = [f for f in r.findings if f.file == "os/sys_linux.c"]
        self.assertTrue(lin and all(f.severity == "info" for f in lin))

    def test_rtos_platform_files_are_downgraded(self):
        r = self._proj({"port/vxworks/net.c": "#include <sys/epoll.h>\n", "port/zephyr_glue.c": "#include <sys/epoll.h>\n"})
        self.assertTrue(r.findings and all(f.severity == "info" for f in r.findings))

    def test_examples_count_half(self):
        r = self._proj({"examples/demo.c": "int main(void){ return prctl(1); }\n"})
        f = [x for x in r.findings if x.rule == "QNX013"]
        self.assertTrue(f and f[0].in_tests)


if __name__ == "__main__":
    unittest.main()
