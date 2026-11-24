import unittest
import os
import types
from importlib.machinery import SourceFileLoader

_loader = SourceFileLoader("hao", os.path.join(os.path.dirname(__file__), "..", "..", "herdr-agent-ops", "scripts", "hao"))
hao = types.ModuleType(_loader.name)
_loader.exec_module(hao)

validate_name = hao.validate_name
make_label = hao.make_label
cmd_name = hao.cmd_name
cmd_clear = hao.cmd_clear


class TestName(unittest.TestCase):
    def test_validate_ok(self):
        self.assertTrue(validate_name("hawk"))

    def test_validate_len(self):
        self.assertFalse(validate_name("reviewer"))

    def test_validate_chars(self):
        self.assertFalse(validate_name("Hawk"))
        self.assertFalse(validate_name("hawk-"))

    def test_make_label(self):
        self.assertEqual(make_label("hawk", "api"), "hao-hawk-api")
        self.assertEqual(make_label("hawk"), "hao-hawk")

    def test_name_dry_run(self):
        self.assertEqual(cmd_name("w2:p9", "hawk", "api", False, True), 0)

    def test_clear_dry_run(self):
        self.assertEqual(cmd_clear("w2:p9", False, True), 0)  # dry_run=True, no real clear


if __name__ == "__main__":
    unittest.main()
