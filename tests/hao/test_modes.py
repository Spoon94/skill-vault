import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hao", "scripts"))
import os
import types
from importlib.machinery import SourceFileLoader

_loader = SourceFileLoader("hao", os.path.join(os.path.dirname(__file__), "..", "..", "hao", "scripts", "hao"))
hao = types.ModuleType(_loader.name)
_loader.exec_module(hao)
from hao_test_guard import install_offline_guard  # noqa: E402
install_offline_guard(hao)

lifecycle_gate = hao.lifecycle_gate
safe_result_path = hao.safe_result_path
from ledger import state_dir
import os


class TestModes(unittest.TestCase):
    def test_lifecycle_gate_needs_seq_and_final(self):
        self.assertFalse(lifecycle_gate(submit_seq=5, current_seq=5, final="idle"))
        self.assertFalse(lifecycle_gate(submit_seq=5, current_seq=6, final="working"))
        self.assertTrue(lifecycle_gate(submit_seq=5, current_seq=6, final="idle"))
        self.assertTrue(lifecycle_gate(submit_seq=5, current_seq=6, final="done"))

    def test_file_partial_rejected(self):
        self.assertFalse(safe_result_path("deadbeef0000", "/etc/passwd"))
        self.assertTrue(safe_result_path("deadbeef0000", os.path.join(state_dir(), "deadbeef0000", "result.md")))

    def test_file_traversal_rejected(self):
        self.assertFalse(safe_result_path("deadbeef0000", "/tmp/hao/tasks/deadbeef0000/../../etc/passwd"))


if __name__ == "__main__":
    unittest.main()
