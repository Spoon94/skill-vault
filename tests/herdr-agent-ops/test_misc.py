import unittest
import os
import sys
import tempfile
import types
from importlib.machinery import SourceFileLoader

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "herdr-agent-ops", "scripts"))
_loader = SourceFileLoader("hao", os.path.join(os.path.dirname(__file__), "..", "..", "herdr-agent-ops", "scripts", "hao"))
hao = types.ModuleType(_loader.name)
_loader.exec_module(hao)

cmd_status = hao.cmd_status
cmd_result = hao.cmd_result
cmd_say = hao.cmd_say


class TestMisc(unittest.TestCase):
    def test_status_nonexistent(self):
        self.assertEqual(cmd_status("w2:pZZZZ"), 3)  # nonexistent -> exit 3

    def test_result_no_path(self):
        self.assertEqual(cmd_result("nonexistent"), 3)

    def test_say_no_env(self):
        saved = os.environ.pop("HERDR_PANE_ID", None)
        try:
            self.assertEqual(cmd_say(None, "hi"), 3)  # no target and no env -> exit3
        finally:
            if saved is not None:
                os.environ["HERDR_PANE_ID"] = saved


class TestGuards(unittest.TestCase):
    def test_finish_done_degrades_on_write_failure(self):
        # r7#1 (P1): confirmed completion returns done even if ledger write fails
        import contextlib
        import io as _io

        class Boom:
            def write_done(self, *a, **k):
                raise PermissionError("read-only state dir")

        buf = _io.StringIO()
        with contextlib.redirect_stderr(buf):
            r = hao._finish_done(Boom(), "aabb11223344", "HAO_DONE hao-aabb11223344")
        self.assertEqual(r["status"], "done")
        self.assertIn("warning", buf.getvalue())
        hao._LEDGER_WARNED = False

    def test_map_herdr_error_nested(self):
        # herdr stderr JSON nests the code under "error"
        self.assertEqual(hao.map_herdr_error({"error": {"code": "agent_name_taken"}}), 6)
        self.assertEqual(hao.map_herdr_error({"error": {"code": "pane_not_found"}}), 3)
        self.assertEqual(hao.map_herdr_error({"error": {"code": "timeout"}}), 4)
        self.assertEqual(hao.map_herdr_error({"error": {"code": "nope"}}), 8)
        self.assertEqual(hao.map_herdr_error({}), 8)
        self.assertEqual(hao.map_herdr_error({"code": "agent_blocked"}), 5)

    def test_herdr_err_code(self):
        self.assertEqual(hao._herdr_err_code('{"error": {"code": "agent_not_found"}}'),
                         "agent_not_found")
        self.assertIsNone(hao._herdr_err_code("not json"))

    def test_done_invalid_token_exit2(self):
        self.assertEqual(hao.cmd_done("hao-ZZZZ!!", None), 2)

    def test_result_invalid_id_exit2(self):
        self.assertEqual(hao.cmd_result("bad id!", None), 2)

    def test_abort_invalid_allow_env_exit2(self):
        os.environ["HAO_ABORT_ALLOW"] = "yes"
        try:
            self.assertEqual(hao.cmd_abort("abcd12345678", True), 2)
        finally:
            os.environ.pop("HAO_ABORT_ALLOW", None)

    def test_abort_approval_file_needs_0600(self):
        os.environ.pop("HAO_ABORT_ALLOW", None)
        with tempfile.TemporaryDirectory() as d:
            saved = os.environ.get("XDG_CONFIG_HOME")
            os.environ["XDG_CONFIG_HOME"] = d
            try:
                cfg = os.path.join(d, "hao", "abort-approval")
                os.makedirs(os.path.dirname(cfg))
                with open(cfg, "w") as f:
                    f.write("abcd12345678\n")
                os.chmod(cfg, 0o644)
                self.assertFalse(hao._abort_approved("abcd12345678"))
                os.chmod(cfg, 0o600)
                self.assertTrue(hao._abort_approved("abcd12345678"))
            finally:
                if saved is None:
                    os.environ.pop("XDG_CONFIG_HOME", None)
                else:
                    os.environ["XDG_CONFIG_HOME"] = saved


class TestWaitRoundRec(unittest.TestCase):
    def test_degrades_on_unwritable_ledger(self):
        # r6#1 (P1): heartbeat failure must not kill the wait round
        import contextlib
        with tempfile.TemporaryDirectory() as d:
            ro = os.path.join(d, "ro")
            os.makedirs(ro)
            os.chmod(ro, 0o500)
            saved = os.environ.get("XDG_STATE_HOME")
            os.environ["XDG_STATE_HOME"] = ro
            try:
                import ledger as led
                buf = __import__("io").StringIO()
                with contextlib.redirect_stderr(buf):
                    rec = hao._wait_round_rec(led.Ledger(), "aabb11223344")
                self.assertEqual(rec, {})
            finally:
                os.chmod(ro, 0o700)
                if saved is None:
                    os.environ.pop("XDG_STATE_HOME", None)
                else:
                    os.environ["XDG_STATE_HOME"] = saved
                hao._LEDGER_WARNED = False


class TestLoadModuleCache(unittest.TestCase):
    def test_cache_verifies_path(self):
        # r6#3: a same-name module from a different path must not be returned
        m1 = hao._load_module("hao_ledger", "ledger.py")
        self.assertIs(hao._load_module("hao_ledger", "ledger.py"), m1)
        fake = types.ModuleType("hao_ledger")
        fake.__file__ = "/nonexistent/ledger.py"
        saved = sys.modules.get("hao_ledger")
        sys.modules["hao_ledger"] = fake
        try:
            m2 = hao._load_module("hao_ledger", "ledger.py")
            self.assertIsNot(m2, fake)
            self.assertTrue(m2.__file__.endswith("ledger.py"))
        finally:
            if saved is not None:
                sys.modules["hao_ledger"] = saved


if __name__ == "__main__":
    unittest.main()
