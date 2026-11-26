import unittest
import os
import types
from importlib.machinery import SourceFileLoader
from unittest import mock

_loader = SourceFileLoader("hao", os.path.join(os.path.dirname(__file__), "..", "..", "hao", "scripts", "hao"))
hao = types.ModuleType(_loader.name)
_loader.exec_module(hao)
from hao_test_guard import install_offline_guard  # noqa: E402
install_offline_guard(hao)

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
        def stub(args, machine=None):
            if args[:2] == ["agent", "list"]:
                return 0, '{"result":{"agents":[]}}', ""
            if args[:2] == ["pane", "list"]:
                return 0, '{"result":{"panes":[]}}', ""
            if args[:2] == ["pane", "get"]:
                return 0, '{"result":{"pane":{"pane_id":"w2:p9","label":""}}}', ""
            return 0, "{}", ""
        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            self.assertEqual(cmd_name("w2:p9", "hawk", "reviewer", False, True), 0)

    def test_clear_dry_run(self):
        def stub(args, machine=None):
            if args[:2] == ["pane", "get"]:
                return 0, '{"result":{"pane":{"pane_id":"w2:p9","label":""}}}', ""
            return 0, "{}", ""
        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            self.assertEqual(cmd_clear("w2:p9", False, True), 0)  # dry_run=True, no real clear


if __name__ == "__main__":
    unittest.main()
