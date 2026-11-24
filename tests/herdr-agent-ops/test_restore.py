import unittest
import os
import types
from importlib.machinery import SourceFileLoader

_loader = SourceFileLoader("hao", os.path.join(os.path.dirname(__file__), "..", "..", "herdr-agent-ops", "scripts", "hao"))
hao = types.ModuleType(_loader.name)
_loader.exec_module(hao)

preflight = hao.preflight


class TestRestore(unittest.TestCase):
    def test_per_machine_conflict(self):
        agents = [{"name": "hawk", "pane_id": "w9:p1"}]
        panes = [{"pane_id": "w2:p9", "label": "hao-hawk", "agent": "claude"}]
        plan = preflight(panes, agents, workspace="w2")
        self.assertEqual(plan["conflicts"], ["hawk"])

    def test_no_auto_winner(self):
        panes = [
            {"pane_id": "w2:p9", "label": "hao-hawk", "agent": "claude"},
            {"pane_id": "w2:p10", "label": "hao-hawk", "agent": "claude"},
        ]
        plan = preflight(panes, [], workspace="w2")
        self.assertTrue(plan["ambiguous"])

    def test_skip_non_hao_label(self):
        panes = [{"pane_id": "w2:p1", "label": "yaml", "agent": "claude"}]
        plan = preflight(panes, [], workspace="w2")
        self.assertEqual(plan["plan"], [])

    def test_scope_only_label(self):
        panes = [{"pane_id": "w2:p9", "label": "hao-hawk-api", "agent": "claude"}]
        plan = preflight(panes, [], workspace="w2")
        self.assertEqual(plan["plan"][0][0], "hawk")


if __name__ == "__main__":
    unittest.main()
