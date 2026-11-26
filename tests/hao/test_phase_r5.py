import contextlib
import io
import json
import os
import sys
import tempfile
import time
import types
import unittest
from importlib.machinery import SourceFileLoader
from types import SimpleNamespace
from unittest import mock

HERE = os.path.dirname(__file__)
SKILL = os.path.join(HERE, "..", "..", "hao")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
_loader = SourceFileLoader("hao", os.path.join(SKILL, "scripts", "hao"))
hao = types.ModuleType("hao")
_loader.exec_module(hao)
from hao_test_guard import install_offline_guard  # noqa: E402
install_offline_guard(hao)
from ledger import Ledger, _path  # noqa: E402


def run_cli(argv, env=None):
    out, err = io.StringIO(), io.StringIO()
    saved = {k: os.environ.get(k) for k in
             ("HAO_STATE_DIR", "HERDR_PANE_ID", "HERDR_ENV")}
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


def status_stub(status):
    def stub(args, machine=None):
        if args[:2] == ["agent", "get"]:
            return 0, json.dumps({"result": {"agent": {
                "agent_status": status}}}), ""
        return 0, "{}", ""
    return stub


class TestR5RunningCleanup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "hao", "tasks")
        os.environ["HAO_STATE_DIR"] = self.state
        self.sid = "abcd12345678"
        self.env = {"HAO_STATE_DIR": self.state, "HERDR_PANE_ID": None,
                    "HERDR_ENV": "1"}
        Ledger().write_running(self.sid, target="w2:p9")
        with open(_path(self.sid)) as f:
            rec = json.load(f)
        rec["updated"] = time.time() - 90000
        with open(_path(self.sid), "w") as f:
            json.dump(rec, f)

    def tearDown(self):
        os.environ.pop("HAO_STATE_DIR", None)
        self.tmp.cleanup()

    def test_clean_keeps_aged_running_while_working(self):
        with mock.patch.object(hao, "run_herdr",
                               side_effect=status_stub("working")):
            rc, out, _err = run_cli(["clean", "--json"], self.env)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["kept_running"], 1)
        self.assertEqual(Ledger().get(self.sid)["status"], "running")

    def test_clean_keeps_aged_running_while_blocked(self):
        with mock.patch.object(hao, "run_herdr",
                               side_effect=status_stub("blocked")):
            rc, _out, _err = run_cli(["clean", "--json"], self.env)
        self.assertEqual(rc, 0)
        self.assertIsNotNone(Ledger().get(self.sid))

    def test_clean_removes_aged_running_when_idle(self):
        with mock.patch.object(hao, "run_herdr",
                               side_effect=status_stub("idle")):
            rc, _out, _err = run_cli(["clean", "--json"], self.env)
        self.assertEqual(rc, 0)
        self.assertIsNone(Ledger().get(self.sid))

    def test_clean_keeps_record_when_state_read_fails(self):
        with mock.patch.object(hao, "run_herdr", side_effect=OSError("boom")):
            rc, _out, _err = run_cli(["clean", "--json"], self.env)
        self.assertEqual(rc, 0)
        self.assertIsNotNone(Ledger().get(self.sid))

    def test_clean_removes_when_pane_is_gone(self):
        with mock.patch.object(
                hao, "run_herdr", return_value=(
                    1, "", '{"error":{"code":"pane_not_found"}}')):
            rc, _out, _err = run_cli(["clean", "--ttl", "0", "--json"],
                                     self.env)
        self.assertEqual(rc, 0)
        self.assertIsNone(Ledger().get(self.sid))

    def test_clean_removes_when_agent_is_gone(self):
        with mock.patch.object(
                hao, "run_herdr", return_value=(
                    1, "", '{"error":{"code":"agent_not_found"}}')):
            rc, _out, _err = run_cli(["clean", "--ttl", "0", "--json"],
                                     self.env)
        self.assertEqual(rc, 0)
        self.assertIsNone(Ledger().get(self.sid))

    def test_clean_removes_when_pane_has_no_agent(self):
        with mock.patch.object(
                hao, "run_herdr",
                return_value=(0, json.dumps({"result": {"agent": None}}), "")):
            rc, _out, _err = run_cli(["clean", "--ttl", "0", "--json"],
                                     self.env)
        self.assertEqual(rc, 0)
        self.assertIsNone(Ledger().get(self.sid))

    def test_clean_all_removes_when_pane_is_gone(self):
        with mock.patch.object(
                hao, "run_herdr", return_value=(
                    1, "", '{"error":{"code":"pane_not_found"}}')):
            rc, _out, _err = run_cli(["clean", "--all", "--json"], self.env)
        self.assertEqual(rc, 0)
        self.assertIsNone(Ledger().get(self.sid))

    def test_clean_all_keeps_working_agent(self):
        with mock.patch.object(hao, "run_herdr",
                               side_effect=status_stub("working")):
            rc, _out, _err = run_cli(["clean", "--all", "--json"], self.env)
        self.assertEqual(rc, 0)
        self.assertIsNotNone(Ledger().get(self.sid))

    def test_clean_removes_when_agent_key_is_absent(self):
        with mock.patch.object(
                hao, "run_herdr",
                return_value=(0, json.dumps({"result": {}}), "")):
            rc, _out, _err = run_cli(["clean", "--ttl", "0", "--json"],
                                     self.env)
        self.assertEqual(rc, 0)
        self.assertIsNone(Ledger().get(self.sid))

    def test_clean_keeps_unknown_agent_state(self):
        with mock.patch.object(hao, "run_herdr",
                               side_effect=status_stub("unknown")):
            rc, _out, _err = run_cli(["clean", "--ttl", "0", "--json"],
                                     self.env)
        self.assertEqual(rc, 0)
        self.assertIsNotNone(Ledger().get(self.sid))

    def test_clean_keeps_other_herdr_errors(self):
        with mock.patch.object(
                hao, "run_herdr", return_value=(
                    1, "", '{"error":{"code":"connection_failure"}}')):
            rc, _out, _err = run_cli(["clean", "--ttl", "0", "--json"],
                                     self.env)
        self.assertEqual(rc, 0)
        self.assertIsNotNone(Ledger().get(self.sid))

    def test_doctor_keeps_aged_running_while_working(self):
        run = SimpleNamespace(returncode=0, stdout="ok", stderr="")
        with mock.patch.object(hao, "run_herdr",
                               side_effect=status_stub("working")), \
                mock.patch.object(hao.subprocess, "run", return_value=run):
            rc, out, _err = run_cli(["doctor", "--json"], self.env)
        self.assertEqual(rc, 0)
        data = json.loads(out)
        ledger = next(c for c in data["checks"] if c["name"] == "ledger")
        self.assertEqual(ledger["kept"], 1)
        self.assertIsNotNone(Ledger().get(self.sid))

    def test_doctor_removes_when_pane_is_gone(self):
        run = SimpleNamespace(returncode=0, stdout="ok", stderr="")
        with mock.patch.object(
                hao, "run_herdr", return_value=(
                    1, "", '{"error":{"code":"pane_not_found"}}')), \
                mock.patch.object(hao.subprocess, "run", return_value=run):
            rc, _out, _err = run_cli(["doctor", "--json"], self.env)
        self.assertEqual(rc, 0)
        self.assertIsNone(Ledger().get(self.sid))

    def test_doctor_removes_aged_running_when_idle(self):
        run = SimpleNamespace(returncode=0, stdout="ok", stderr="")
        with mock.patch.object(hao, "run_herdr",
                               side_effect=status_stub("idle")), \
                mock.patch.object(hao.subprocess, "run", return_value=run):
            rc, _out, _err = run_cli(["doctor", "--json"], self.env)
        self.assertEqual(rc, 0)
        self.assertIsNone(Ledger().get(self.sid))


if __name__ == "__main__":
    unittest.main()
