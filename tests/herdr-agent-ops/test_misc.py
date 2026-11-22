import unittest
import os
import tempfile
import types
from importlib.machinery import SourceFileLoader

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


if __name__ == "__main__":
    unittest.main()
