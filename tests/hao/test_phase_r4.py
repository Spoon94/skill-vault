import contextlib
import io
import json
import os
import sys
import tempfile
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
from ledger import Ledger  # noqa: E402


def run_cli(argv, env=None):
    out, err = io.StringIO(), io.StringIO()
    saved = {k: os.environ.get(k) for k in
             ("HAO_STATE_DIR", "HERDR_PANE_ID", "HAO_ABORT_ALLOW")}
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


def stateful_stub(before, after):
    state = {"value": before}

    def stub(args, machine=None):
        if args[:2] == ["agent", "get"]:
            return 0, json.dumps({"result": {"agent": {
                "agent_status": state["value"]}}}), ""
        if args[:2] == ["agent", "send-keys"]:
            if args[3] == "ctrl+c":
                state["value"] = after
            return 0, "{}", ""
        return 0, "{}", ""
    return stub


class TestR4SettledStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "hao", "tasks")
        self.env = {"HAO_STATE_DIR": self.state, "HERDR_PANE_ID": None,
                    "HAO_ABORT_ALLOW": None}
        os.environ["HAO_STATE_DIR"] = self.state

    def tearDown(self):
        os.environ.pop("HAO_STATE_DIR", None)
        self.tmp.cleanup()

    def test_stop_reports_changed_status(self):
        with mock.patch.object(hao, "run_herdr",
                               side_effect=stateful_stub("working", "idle")), \
                mock.patch.object(hao.time, "sleep", return_value=None):
            rc, out, err = run_cli(["stop", "w2:p9", "--json"], self.env)
        self.assertEqual(rc, 0, err)
        data = json.loads(out)
        self.assertEqual(data["agent_status_before"], "working")
        self.assertEqual(data["agent_status_after"], "idle")
        self.assertNotIn("did not change", err)

    def test_stop_warns_when_status_unchanged_for_3s(self):
        with mock.patch.object(hao, "run_herdr",
                               side_effect=stateful_stub("working", "working")), \
                mock.patch.object(hao.time, "sleep", return_value=None):
            rc, out, err = run_cli(["stop", "w2:p9", "--json"], self.env)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["agent_status_after"], "working")
        self.assertIn("did not change within 3s", err)
        self.assertIn("may not have responded", err)

    def test_abort_interrupt_reports_changed_status(self):
        sid = "abcd12345678"
        Ledger().write_running(sid, target="w2:p9")
        with mock.patch.object(hao, "run_herdr",
                               side_effect=stateful_stub("working", "idle")), \
                mock.patch.object(hao.time, "sleep", return_value=None):
            rc, out, err = run_cli(
                ["abort", sid, "--interrupt", "--json"],
                {**self.env, "HAO_ABORT_ALLOW": "1"})
        self.assertEqual(rc, 0, err)
        data = json.loads(out)
        self.assertEqual(data["agent_status_before"], "working")
        self.assertEqual(data["agent_status_after"], "idle")
        self.assertNotIn("did not change", err)
        self.assertTrue(Ledger().get(sid)["interrupted"])

    def test_abort_interrupt_warns_when_status_unchanged(self):
        sid = "abcd12345678"
        Ledger().write_running(sid, target="w2:p9")
        with mock.patch.object(hao, "run_herdr",
                               side_effect=stateful_stub("working", "working")), \
                mock.patch.object(hao.time, "sleep", return_value=None):
            rc, out, err = run_cli(
                ["abort", sid, "--interrupt", "--json"],
                {**self.env, "HAO_ABORT_ALLOW": "1"})
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertEqual(data["agent_status_after"], "working")
        self.assertIn("did not change within 3s", err)


if __name__ == "__main__":
    unittest.main()
