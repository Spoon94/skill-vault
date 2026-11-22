import unittest
import os
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


if __name__ == "__main__":
    unittest.main()
