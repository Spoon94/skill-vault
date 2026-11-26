import unittest
import os
import types
from importlib.machinery import SourceFileLoader

_loader = SourceFileLoader("hao", os.path.join(os.path.dirname(__file__), "..", "..", "hao", "scripts", "hao"))
hao = types.ModuleType(_loader.name)
_loader.exec_module(hao)
from hao_test_guard import install_offline_guard  # noqa: E402
install_offline_guard(hao)

map_herdr_error = hao.map_herdr_error
cmd_doctor = hao.cmd_doctor


class TestDoctor(unittest.TestCase):
    def test_map(self):
        self.assertEqual(map_herdr_error({"code": "agent_name_taken"}), 6)
        self.assertEqual(map_herdr_error({"code": "pane_not_found"}), 3)
        self.assertEqual(map_herdr_error({"code": "unknown_machine"}), 7)
        self.assertEqual(map_herdr_error({"code": "invalid_agent_name"}), 2)

    def test_no_profile(self):
        self.assertEqual(cmd_doctor("no-such-machine"), 7)


if __name__ == "__main__":
    unittest.main()
