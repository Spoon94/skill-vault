import unittest
import os
import contextlib
import io
import json
import types
from importlib.machinery import SourceFileLoader
from unittest import mock

_loader = SourceFileLoader("hao", os.path.join(os.path.dirname(__file__), "..", "..", "hao", "scripts", "hao"))
hao = types.ModuleType(_loader.name)
_loader.exec_module(hao)
from hao_test_guard import install_offline_guard  # noqa: E402
install_offline_guard(hao)

preflight = hao.preflight


def restore_stub(panes):
    def stub(args, machine=None):
        if args[:2] == ["agent", "list"]:
            return 0, json.dumps({"result": {"agents": []}}), ""
        if args[:2] == ["pane", "list"]:
            return 0, json.dumps({"result": {"panes": panes}}), ""
        return 0, '{"result":{}}', ""
    return stub


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

    def test_ambiguous_names_exit_6(self):
        panes = [
            {"pane_id": "w2:p1", "label": "hao-moth-developer", "agent": "claude"},
            {"pane_id": "w2:p2", "label": "hao-moth-reviewer", "agent": "claude"},
        ]
        out = io.StringIO()
        with mock.patch.object(hao, "run_herdr",
                               side_effect=restore_stub(panes)), \
                contextlib.redirect_stdout(out):
            rc = hao.cmd_restore(dry_run=True)
        self.assertEqual(rc, 6)
        self.assertIn("ambiguous names", out.getvalue())
        self.assertIn("ambiguous names", hao._ERROR_DETAIL)
        hao._ERROR_DETAIL = None

    def test_dry_run_uses_name_role_vocabulary(self):
        panes = [
            {"pane_id": "w2:p1", "label": "hao-hawk-developer", "agent": "claude"},
            {"pane_id": "w2:p2", "label": "hao-lens", "agent": "claude"},
        ]
        out = io.StringIO()
        with mock.patch.object(hao, "run_herdr",
                               side_effect=restore_stub(panes)), \
                contextlib.redirect_stdout(out):
            rc = hao.cmd_restore(dry_run=True)
        self.assertEqual(rc, 0)
        lines = out.getvalue().splitlines()
        self.assertIn("would restore name hawk (role developer) on w2:p1", lines)
        self.assertIn("would restore name lens (no role) on w2:p2", lines)

    def test_name_exit_hint_has_new_wording(self):
        self.assertEqual(
            hao._EXIT_REASON[("name", 2)],
            "invalid name or unknown role; expected name ^[a-z]{4,6}$ "
            "and a role from references/roles.md")


if __name__ == "__main__":
    unittest.main()
