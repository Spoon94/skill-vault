import contextlib
import io
import json
import os
import sys
import tempfile
import types
import unittest
from importlib.machinery import SourceFileLoader
from types import SimpleNamespace
from unittest import mock

HERE = os.path.dirname(__file__)
SKILL = os.path.join(HERE, "..", "..", "herdr-agent-ops")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
_loader = SourceFileLoader("hao", os.path.join(SKILL, "scripts", "hao"))
hao = types.ModuleType("hao")
_loader.exec_module(hao)
from hao_test_guard import install_offline_guard  # noqa: E402
install_offline_guard(hao)


def run_cli(argv, env=None):
    out, err = io.StringIO(), io.StringIO()
    saved = {k: os.environ.get(k) for k in
             ("HAO_STATE_DIR", "HERDR_PANE_ID", "HERDR_ENV",
              "HAO_ABORT_ALLOW", "XDG_CONFIG_HOME")}
    if env:
        for key, value in env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = hao.main(argv)
    except SystemExit as exc:
        rc = exc.code
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        hao._ERROR_DETAIL = None
        hao._JSON_OUTPUT = False
        hao._JSON_HANDLED = False
        hao._LEDGER_WARNED = False
    return rc, out.getvalue(), err.getvalue()


def layout(width):
    return json.dumps({"result": {"layout": {"panes": [
        {"pane_id": "w2:p9", "rect": {"width": width}}]}}})


def ask_stub(width=None, layout_rc=0, calls=None):
    def stub(args, machine=None):
        if calls is not None:
            calls.append(args)
        if args[:2] == ["pane", "layout"]:
            if layout_rc != 0:
                return layout_rc, "", ""
            return 0, layout(width), ""
        if args[:2] == ["agent", "prompt"]:
            return 0, "{}", ""
        if args[:2] == ["agent", "get"]:
            return 0, json.dumps({"result": {"agent": {
                "agent_status": "idle", "state_change_seq": 0}}}), ""
        return 0, "{}", ""
    return stub


class TestR1Stop(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = {"HAO_STATE_DIR": os.path.join(self.tmp.name, "hao", "tasks"),
                    "HERDR_PANE_ID": None, "HAO_ABORT_ALLOW": None,
                    "XDG_CONFIG_HOME": os.path.join(self.tmp.name, "cfg")}

    def tearDown(self):
        self.tmp.cleanup()

    def _stub(self, status, sent, after="idle"):
        state = {"status": status}

        def stub(args, machine=None):
            if args[:2] == ["agent", "get"]:
                return 0, json.dumps({"result": {"agent": {
                    "agent_status": state["status"]}}}), ""
            if args[:2] == ["agent", "send-keys"]:
                sent.append(args[3])
                if args[3] == "ctrl+c":
                    state["status"] = after
                return 0, "{}", ""
            return 0, "{}", ""
        return stub

    def test_working_sends_esc_and_ctrl_c(self):
        sent = []
        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._stub("working", sent)):
            rc, out, err = run_cli(["stop", "w2:p9", "--json"], self.env)
        self.assertEqual(rc, 0, err)
        data = json.loads(out)
        self.assertEqual(data["agent_status_before"], "working")
        self.assertEqual(data["agent_status_after"], "idle")
        self.assertEqual(data["sent"], ["esc", "ctrl+c"])
        self.assertEqual(sent, ["esc", "ctrl+c"])
        self.assertFalse(os.path.exists(self.env["HAO_STATE_DIR"]))

    def test_idle_does_not_send(self):
        sent = []
        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._stub("idle", sent)):
            rc, out, _err = run_cli(["stop", "w2:p9", "--json"], self.env)
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertEqual(data["sent"], [])
        self.assertEqual(data["agent_status_after"], "idle")
        self.assertEqual(sent, [])

    def test_text_idle_says_already_idle(self):
        sent = []
        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._stub("idle", sent)):
            rc, out, _err = run_cli(["stop", "w2:p9"], self.env)
        self.assertEqual(rc, 0)
        self.assertIn("already idle", out)
        self.assertEqual(sent, [])

    def test_non_working_statuses_do_not_send(self):
        for status in ("done", "exited", "closed"):
            with self.subTest(status=status):
                sent = []
                with mock.patch.object(
                        hao, "run_herdr",
                        side_effect=self._stub(status, sent)):
                    rc, _out, _err = run_cli(
                        ["stop", "w2:p9", "--json"], self.env)
                self.assertEqual(rc, 0)
                self.assertEqual(sent, [])

    def test_unknown_refuses_and_exits_9(self):
        sent = []
        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._stub("unknown", sent)):
            rc, out, err = run_cli(["stop", "w2:p9", "--json"], self.env)
        self.assertEqual(rc, 9)
        self.assertEqual(json.loads(out)["exit"], 9)
        self.assertIn("unknown", err)
        self.assertEqual(sent, [])

    def test_no_agent_exits_3(self):
        def stub(args, machine=None):
            return 1, "", '{"error":{"code":"agent_not_found"}}'
        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc, out, err = run_cli(["stop", "w2:p9", "--json"], self.env)
        self.assertEqual(rc, 3)
        self.assertEqual(json.loads(out)["exit"], 3)
        self.assertIn("no agent", err)

    def test_blocked_without_auth_does_not_send(self):
        sent = []
        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._stub("blocked", sent)):
            rc, _out, err = run_cli(["stop", "w2:p9", "--json"], self.env)
        self.assertEqual(rc, 5)
        self.assertIn("requires TTY or 0600 approval", err)
        self.assertEqual(sent, [])

    def test_blocked_with_env_approval_sends(self):
        sent = []
        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._stub("blocked", sent)):
            rc, out, err = run_cli(
                ["stop", "w2:p9", "--json"],
                {**self.env, "HAO_ABORT_ALLOW": "1"})
        self.assertEqual(rc, 0, err)
        self.assertEqual(json.loads(out)["sent"], ["esc", "ctrl+c"])
        self.assertEqual(sent, ["esc", "ctrl+c"])

    def test_blocked_with_approval_file_for_pane_sends(self):
        cfg = os.path.join(self.env["XDG_CONFIG_HOME"], "hao",
                           "abort-approval")
        os.makedirs(os.path.dirname(cfg))
        with open(cfg, "w") as f:
            f.write("w2:p9\n")
        os.chmod(cfg, 0o600)
        sent = []
        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._stub("blocked", sent)):
            rc, _out, err = run_cli(["stop", "w2:p9", "--json"], self.env)
        self.assertEqual(rc, 0, err)
        self.assertEqual(sent, ["esc", "ctrl+c"])

    def test_dry_run_does_not_send(self):
        sent = []
        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._stub("working", sent)):
            rc, out, _err = run_cli(
                ["stop", "w2:p9", "--dry-run", "--json"], self.env)
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertEqual(data["sent"], [])
        self.assertTrue(data["dry_run"])
        self.assertEqual(sent, [])


class TestR2PaneWidth(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "hao", "tasks")
        self.env = {"HAO_STATE_DIR": self.state, "HERDR_PANE_ID": None}

    def tearDown(self):
        self.tmp.cleanup()

    def test_ask_narrow_warns_and_reports_width(self):
        with mock.patch.object(hao, "run_herdr",
                               side_effect=ask_stub(width=25)):
            rc, out, err = run_cli(["ask", "w2:p9", "task", "--json"],
                                   self.env)
        self.assertEqual(rc, 0, err)
        self.assertEqual(json.loads(out)["target_cols"], 25)
        self.assertIn("25", err)
        self.assertIn("40", err)
        self.assertIn("ledger", err)
        self.assertIn("sentinel", err)

    def test_ask_wide_has_no_warning(self):
        with mock.patch.object(hao, "run_herdr",
                               side_effect=ask_stub(width=80)):
            rc, out, err = run_cli(["ask", "w2:p9", "task", "--json"],
                                   self.env)
        self.assertEqual(rc, 0, err)
        self.assertEqual(json.loads(out)["target_cols"], 80)
        self.assertNotIn("warning", err)

    def test_ask_layout_failure_is_silent(self):
        with mock.patch.object(hao, "run_herdr",
                               side_effect=ask_stub(layout_rc=1)):
            rc, out, err = run_cli(["ask", "w2:p9", "task", "--json"],
                                   self.env)
        self.assertEqual(rc, 0, err)
        self.assertNotIn("target_cols", json.loads(out))
        self.assertNotIn("warning", err)

    def test_doctor_reports_narrow_pane_without_state(self):
        run = SimpleNamespace(returncode=0, stdout="ok", stderr="")
        env = {"HAO_STATE_DIR": self.state, "HERDR_PANE_ID": "w2:p9",
               "HERDR_ENV": "1"}
        with mock.patch.object(hao, "run_herdr",
                               side_effect=ask_stub(width=25)), \
                mock.patch.object(hao.subprocess, "run", return_value=run):
            rc, out, _err = run_cli(["doctor", "--json"], env)
        self.assertEqual(rc, 0)
        data = json.loads(out)
        check = next(c for c in data["checks"] if c["name"] == "pane width")
        self.assertEqual(check["cols"], 25)
        self.assertTrue(check["warn"])
        self.assertFalse(os.path.exists(self.state))

    def test_doctor_wide_pane_is_not_warn(self):
        run = SimpleNamespace(returncode=0, stdout="ok", stderr="")
        env = {"HAO_STATE_DIR": self.state, "HERDR_PANE_ID": "w2:p9",
               "HERDR_ENV": "1"}
        with mock.patch.object(hao, "run_herdr",
                               side_effect=ask_stub(width=80)), \
                mock.patch.object(hao.subprocess, "run", return_value=run):
            rc, out, _err = run_cli(["doctor", "--json"], env)
        self.assertEqual(rc, 0)
        check = next(c for c in json.loads(out)["checks"]
                     if c["name"] == "pane width")
        self.assertFalse(check["warn"])


if __name__ == "__main__":
    unittest.main()
