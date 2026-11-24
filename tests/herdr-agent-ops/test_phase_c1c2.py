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
from unittest import mock

HERE = os.path.dirname(__file__)
SKILL = os.path.join(HERE, "..", "..", "herdr-agent-ops")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
_loader = SourceFileLoader("hao", os.path.join(SKILL, "scripts", "hao"))
hao = types.ModuleType("hao")
_loader.exec_module(hao)
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


def state_stub(status):
    def stub(args, machine=None):
        if args[:2] == ["agent", "get"]:
            return 0, json.dumps({"result": {"agent": {
                "agent_status": status}}}), ""
        if args[:2] == ["machine", "status"]:
            return 0, "{}", ""
        return 0, "{}", ""
    return stub


def one_json(test, text):
    lines = [line for line in text.splitlines() if line.strip()]
    test.assertEqual(len(lines), 1, text)
    return json.loads(lines[0])


class TestC1CancelPeer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "hao", "tasks")
        os.environ["HAO_STATE_DIR"] = self.state
        self.sid = "abcd12345678"
        self.env = {"HAO_STATE_DIR": self.state}

    def tearDown(self):
        os.environ.pop("HAO_STATE_DIR", None)
        self.tmp.cleanup()

    def _record(self, target="w2:p9"):
        Ledger().write_running(self.sid, target=target,
                               token="hao-" + self.sid + "9900")

    def test_cancel_working_reports_peer_and_next(self):
        self._record()
        with mock.patch.object(hao, "run_herdr",
                               side_effect=state_stub("working")):
            rc, out, err = run_cli(["cancel", self.sid, "--json"], self.env)
        self.assertEqual(rc, 0)
        data = one_json(self, out)
        self.assertTrue(data["peer_running"])
        self.assertEqual(data["next"],
                         f"{hao.hao_command()} abort {self.sid} --interrupt")
        self.assertIn("still running", err)
        self.assertIn("--interrupt", err)
        self.assertEqual(Ledger().get(self.sid)["status"], "cancelled")

    def test_cancel_idle_has_no_next_or_hint(self):
        self._record()
        with mock.patch.object(hao, "run_herdr",
                               side_effect=state_stub("idle")):
            rc, out, err = run_cli(["cancel", self.sid, "--json"], self.env)
        self.assertEqual(rc, 0)
        data = one_json(self, out)
        self.assertFalse(data["peer_running"])
        self.assertNotIn("next", data)
        self.assertEqual(err, "")

    def test_cancel_no_target_has_no_next(self):
        self._record(target=None)
        rc, out, _err = run_cli(["cancel", self.sid, "--json"], self.env)
        self.assertEqual(rc, 0)
        data = one_json(self, out)
        self.assertFalse(data["peer_running"])
        self.assertNotIn("next", data)

    def test_cancel_text_mode_prints_hint(self):
        self._record()
        with mock.patch.object(hao, "run_herdr",
                               side_effect=state_stub("working")):
            rc, out, err = run_cli(["cancel", self.sid], self.env)
        self.assertEqual(rc, 0)
        self.assertIn("still running", err)
        self.assertIn("--interrupt", err)

    def test_abort_without_interrupt_reports_peer(self):
        self._record()
        with mock.patch.object(hao, "run_herdr",
                               side_effect=state_stub("working")):
            rc, out, err = run_cli(["abort", self.sid, "--json"], self.env)
        self.assertEqual(rc, 0)
        data = one_json(self, out)
        self.assertTrue(data["peer_running"])
        self.assertTrue(data["next"].endswith(
            f"abort {self.sid} --interrupt"))
        self.assertIn("still running", err)


class TestC2CancelledRetention(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "hao", "tasks")
        os.environ["HAO_STATE_DIR"] = self.state
        self.sid = "abcd12345678"
        self.env = {"HAO_STATE_DIR": self.state, "HAO_ABORT_ALLOW": "1"}

    def tearDown(self):
        os.environ.pop("HAO_STATE_DIR", None)
        self.tmp.cleanup()

    def test_wait_does_not_consume_cancelled_tombstone(self):
        Ledger().write_running(self.sid, target="w2:p9")
        Ledger().cancel(self.sid)
        rc, _out, _err = run_cli(["wait", "w2:p9", self.sid], self.env)
        self.assertEqual(rc, 10)
        self.assertEqual(Ledger().get(self.sid)["status"], "cancelled")

    def test_abort_interrupt_consumes_tombstone(self):
        Ledger().write_running(self.sid, target="w2:p9")
        Ledger().cancel(self.sid)
        with mock.patch.object(hao, "run_herdr",
                               side_effect=state_stub("working")), \
                mock.patch.object(hao.time, "sleep", return_value=None):
            rc, _out, err = run_cli(
                ["abort", self.sid, "--interrupt", "--json"], self.env)
        self.assertEqual(rc, 0, err)
        self.assertIsNone(Ledger().get(self.sid))
        self.assertFalse(os.path.exists(self.state))

    def test_clean_removes_cancelled_when_target_not_working(self):
        Ledger().write_running(self.sid, target="w2:p9")
        Ledger().cancel(self.sid)
        with mock.patch.object(hao, "run_herdr",
                               side_effect=state_stub("idle")):
            rc, _out, _err = run_cli(["clean", "--json"], self.env)
        self.assertEqual(rc, 0)
        self.assertIsNone(Ledger().get(self.sid))

    def test_clean_removes_cancelled_even_while_target_working(self):
        Ledger().write_running(self.sid, target="w2:p9")
        Ledger().cancel(self.sid)
        with mock.patch.object(hao, "run_herdr",
                               side_effect=state_stub("working")):
            rc, _out, _err = run_cli(["clean", "--json"], self.env)
        self.assertEqual(rc, 0)
        self.assertIsNone(Ledger().get(self.sid))

    def test_cancelled_older_than_one_hour_is_cleaned(self):
        Ledger().write_running(self.sid, target="w2:p9")
        Ledger().cancel(self.sid)
        from ledger import _path
        with open(_path(self.sid)) as f:
            rec = json.load(f)
        rec["cancelled_at"] = time.time() - 3700
        rec["updated"] = rec["cancelled_at"]
        with open(_path(self.sid), "w") as f:
            json.dump(rec, f)
        with mock.patch.object(hao, "run_herdr",
                               side_effect=state_stub("working")):
            rc, _out, _err = run_cli(["clean", "--json"], self.env)
        self.assertEqual(rc, 0)
        self.assertIsNone(Ledger().get(self.sid))

    def test_status_is_read_only_for_cancelled(self):
        Ledger().write_running(self.sid, target="w2:p9")
        Ledger().cancel(self.sid)
        with mock.patch.object(hao, "run_herdr",
                               side_effect=state_stub("idle")):
            rc, _out, _err = run_cli(["status", "w2:p9", "--json"], self.env)
        self.assertEqual(rc, 0)
        self.assertEqual(Ledger().get(self.sid)["status"], "cancelled")

    def test_doctor_removes_cancelled_when_target_not_working(self):
        Ledger().write_running(self.sid, target="w2:p9")
        Ledger().cancel(self.sid)
        run = types.SimpleNamespace(returncode=0, stdout="ok", stderr="")
        with mock.patch.object(hao, "run_herdr",
                               side_effect=state_stub("idle")), \
                mock.patch.object(hao.subprocess, "run", return_value=run):
            rc, _out, _err = run_cli(
                ["doctor", "--json"], {"HAO_STATE_DIR": self.state,
                                       "HERDR_ENV": "1"})
        self.assertEqual(rc, 0)
        self.assertIsNone(Ledger().get(self.sid))

    def test_clean_dry_run_keeps_cancelled(self):
        Ledger().write_running(self.sid, target="w2:p9")
        Ledger().cancel(self.sid)
        with mock.patch.object(hao, "run_herdr",
                               side_effect=state_stub("idle")):
            rc, _out, _err = run_cli(["clean", "--dry-run", "--json"], self.env)
        self.assertEqual(rc, 0)
        self.assertEqual(Ledger().get(self.sid)["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
