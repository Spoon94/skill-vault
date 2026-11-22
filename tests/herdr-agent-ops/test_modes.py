import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "herdr-agent-ops", "scripts"))
import os
import types
from importlib.machinery import SourceFileLoader

_loader = SourceFileLoader("hao", os.path.join(os.path.dirname(__file__), "..", "..", "herdr-agent-ops", "scripts", "hao"))
hao = types.ModuleType(_loader.name)
_loader.exec_module(hao)

lifecycle_gate = hao.lifecycle_gate
safe_result_path = hao.safe_result_path
from ledger import state_dir
import os


class TestModes(unittest.TestCase):
    def test_lifecycle_gate_needs_seq_and_final(self):
        self.assertFalse(lifecycle_gate(submit_seq=5, final="working"))
        self.assertTrue(lifecycle_gate(submit_seq=6, final="idle"))
        self.assertTrue(lifecycle_gate(submit_seq=6, final="done"))

    def test_file_partial_rejected(self):
        self.assertFalse(safe_result_path("abc", "/etc/passwd"))
        self.assertTrue(safe_result_path("abc", os.path.join(state_dir(), "abc", "result.md")))

    def test_file_traversal_rejected(self):
        self.assertFalse(safe_result_path("abc", "/tmp/hao/tasks/abc/../../etc/passwd"))


if __name__ == "__main__":
    unittest.main()
