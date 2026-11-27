import contextlib
import io
import json
import os
import sys
import types
import unittest
from importlib.machinery import SourceFileLoader
from unittest import mock

HERE = os.path.dirname(__file__)
SKILL = os.path.join(HERE, "..", "..", "hao")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
_loader = SourceFileLoader("hao", os.path.join(SKILL, "scripts", "hao"))
hao = types.ModuleType("hao")
_loader.exec_module(hao)
from hao_test_guard import install_offline_guard  # noqa: E402
install_offline_guard(hao)

ERR = '{"error":{"code":"%s"}}'


def stub(agents=(), all_panes=(), ws_panes=None, pane_rename=0,
         agent_rename=0, ws_rc=0, ws_err=""):
    def fake(args, machine=None):
        if args[:2] == ["agent", "list"]:
            return 0, json.dumps({"result": {"agents": list(agents)}}), ""
        if args[:2] == ["pane", "list"]:
            if "--workspace" in args:
                if ws_rc:
                    return ws_rc, "", ws_err
                rows = all_panes if ws_panes is None else ws_panes
                return 0, json.dumps({"result": {"panes": list(rows)}}), ""
            return 0, json.dumps({"result": {"panes": list(all_panes)}}), ""
        if args[:2] == ["pane", "rename"]:
            return pane_rename, "", ""
        if args[:2] == ["agent", "rename"]:
            return agent_rename, "", ""
        return 0, '{"result":{}}', ""
    return fake


def pane(pid, label, agent="claude"):
    return {"pane_id": pid, "label": label, "agent": agent}


class RestoreGapCase(unittest.TestCase):
    def run_restore(self, fake, **kwargs):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(hao, "run_herdr", side_effect=fake), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            rc = hao.cmd_restore(**kwargs)
        return rc, out.getvalue(), err.getvalue()

    def tearDown(self):
        hao._JSON_OUTPUT = False
        hao._JSON_HANDLED = False
        hao._ERROR_DETAIL = None


class TestRestoreGaps(RestoreGapCase):
    def test_success_text_and_json(self):
        panes = [pane("w2:p1", "hao-moth-developer"),
                 pane("w2:p2", "hao-lens")]
        rc, out, _ = self.run_restore(stub(all_panes=panes))
        self.assertEqual(rc, 0)
        self.assertIn("restored 2, skipped 0", out)
        rc, out, _ = self.run_restore(stub(all_panes=panes), all_=True)
        self.assertEqual(rc, 0)
        self.assertIn("restored 2", out)

        hao._JSON_OUTPUT = True
        rc, out, _ = self.run_restore(stub(all_panes=panes))
        data = json.loads(out)
        self.assertEqual(rc, 0)
        self.assertEqual(data["restored"], 2)
        self.assertEqual(data["workspace"], hao.default_workspace())

    def test_pane_rename_failure_reports_partial(self):
        panes = [pane("w2:p1", "hao-moth-developer")]
        rc, _, _ = self.run_restore(stub(all_panes=panes, pane_rename=1))
        self.assertEqual(rc, 6)
        self.assertIn("w2:p1:pane", hao._ERROR_DETAIL)

        hao._JSON_OUTPUT = True
        rc, out, _ = self.run_restore(stub(all_panes=panes, pane_rename=1))
        data = json.loads(out)
        self.assertEqual(rc, 6)
        self.assertFalse(data["ok"])
        self.assertEqual(data["exit"], 6)
        self.assertTrue(hao._JSON_HANDLED)

    def test_agent_rename_failure_text(self):
        panes = [pane("w2:p1", "hao-moth-developer")]
        rc, out, _ = self.run_restore(stub(all_panes=panes, agent_rename=1))
        self.assertEqual(rc, 6)
        self.assertIn("partial failures", out)
        self.assertIn("w2:p1:agent", hao._ERROR_DETAIL)

    def test_shell_only_and_named_are_skipped(self):
        panes = [pane("w2:p1", "hao-moth-developer", agent=None),
                 pane("w2:p2", "hao-lens-reviewer", agent="lens")]
        agents = [{"name": "lens", "pane_id": "w2:p2"}]
        rc, out, _ = self.run_restore(stub(agents=agents, all_panes=panes),
                                      adopt=False)
        self.assertEqual(rc, 0)
        self.assertIn("skipped 2", out)
        self.assertIn("shell-only 1, named 1", out)

    def test_pick_skips_other_panes(self):
        panes = [pane("w2:p1", "hao-moth-developer"),
                 pane("w2:p2", "hao-lens-reviewer")]
        rc, out, _ = self.run_restore(stub(all_panes=panes),
                                      pick="w2:p2")
        self.assertEqual(rc, 0)
        self.assertIn("restored 1", out)

    def test_dry_run_role_and_no_role_text(self):
        panes = [pane("w2:p1", "hao-moth-developer"),
                 pane("w2:p2", "hao-lens")]
        rc, out, _ = self.run_restore(stub(all_panes=panes), dry_run=True)
        self.assertEqual(rc, 0)
        self.assertIn("would restore name moth (role developer) on w2:p1", out)
        self.assertIn("would restore name lens (no role) on w2:p2", out)

    def test_workspace_not_found_is_empty(self):
        rc, out, _ = self.run_restore(
            stub(ws_rc=1, ws_err=ERR % "workspace_not_found"),
            workspace="wZZ")
        self.assertEqual(rc, 0)
        self.assertIn("no hao- panes in workspace wZZ", out)

    def test_workspace_other_error_exits_8(self):
        rc, _, _ = self.run_restore(
            stub(ws_rc=1, ws_err=ERR % "server_error"),
            workspace="w2")
        self.assertEqual(rc, 8)

    def test_no_hao_panes_json(self):
        hao._JSON_OUTPUT = True
        rc, out, _ = self.run_restore(stub(all_panes=[pane("w2:p1", "yaml")]))
        data = json.loads(out)
        self.assertEqual(rc, 0)
        self.assertIn("no hao- panes", data["message"])

    def test_name_conflict_exits_6(self):
        agents = [{"name": "moth", "pane_id": "w9:p1"}]
        panes = [pane("w2:p1", "hao-moth-developer")]
        rc, out, _ = self.run_restore(stub(agents=agents, all_panes=panes))
        self.assertEqual(rc, 6)
        self.assertIn("name conflicts", out)

    def test_ambiguous_names_exits_6(self):
        panes = [pane("w2:p1", "hao-moth-developer"),
                 pane("w2:p2", "hao-moth-reviewer")]
        rc, _, _ = self.run_restore(stub(all_panes=panes))
        self.assertEqual(rc, 6)
        self.assertEqual(hao._ERROR_DETAIL, "ambiguous names across workspaces")

    def test_invalid_agent_and_pane_json_exit_8(self):
        def bad_agents(args, machine=None):
            if args[:2] == ["agent", "list"]:
                return 0, '{"result":{}}', ""
            return 0, '{"result":{"panes":[]}}', ""

        self.assertEqual(self.run_restore(bad_agents)[0], 8)
        hao._ERROR_DETAIL = None

        def bad_panes(args, machine=None):
            if args[:2] == ["agent", "list"]:
                return 0, '{"result":{"agents":[]}}', ""
            return 0, '{"result":{}}', ""

        self.assertEqual(self.run_restore(bad_panes)[0], 8)
        hao._ERROR_DETAIL = None

    def test_agent_list_failure_exits_8(self):
        def fake(args, machine=None):
            return (1, "", ERR % "server_error")
        self.assertEqual(self.run_restore(fake)[0], 8)

    def test_all_pane_list_failure_exits_8(self):
        def fake(args, machine=None):
            if args[:2] == ["agent", "list"]:
                return 0, '{"result":{"agents":[]}}', ""
            return 1, "", ERR % "server_error"
        self.assertEqual(self.run_restore(fake)[0], 8)

    def test_invalid_workspace_pane_json_exits_8(self):
        def fake(args, machine=None):
            if args[:2] == ["agent", "list"]:
                return 0, '{"result":{"agents":[]}}', ""
            if args[:2] == ["pane", "list"] and "--workspace" not in args:
                return 0, '{"result":{"panes":[]}}', ""
            if args[:2] == ["pane", "list"]:
                return 0, '{"result":{}}', ""
            return 0, "{}", ""
        self.assertEqual(self.run_restore(fake)[0], 8)


if __name__ == "__main__":
    unittest.main()
