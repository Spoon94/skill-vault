import json
import os
import subprocess
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


class FakeProc:
    def __init__(self, out="", err="", rc=0, timeout_first=False):
        self.out, self.err, self.returncode = out, err, rc
        self.pid = 12345
        self.timeout_first = timeout_first
        self.calls = 0

    def communicate(self, timeout=None):
        self.calls += 1
        if self.timeout_first and self.calls == 1:
            raise subprocess.TimeoutExpired(["herdr"], timeout)
        return self.out, self.err

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        pass


class TestRunHerdrGaps(unittest.TestCase):
    def test_normal_call(self):
        proc = FakeProc("out", "err", 3)
        with mock.patch.object(hao.subprocess, "Popen", return_value=proc):
            rc, out, err = hao._TEST_REAL_RUN_HERDR(["agent", "get", "w2:p9"])
        self.assertEqual((rc, out, err), (3, "out", "err"))

    def test_start_failure(self):
        with mock.patch.object(hao.subprocess, "Popen",
                               side_effect=OSError("no herdr")):
            rc, _, err = hao._TEST_REAL_RUN_HERDR(["agent", "get"])
        self.assertEqual(rc, 8)
        self.assertIn("herdr unavailable", err)

    def test_timeout_is_capped_message(self):
        proc = FakeProc(timeout_first=True)
        with mock.patch.object(hao.subprocess, "Popen", return_value=proc), \
                mock.patch.object(hao, "_kill_herdr_group"):
            rc, _, err = hao._TEST_REAL_RUN_HERDR(
                ["agent", "wait", "w2:p9", "--timeout", "8000"])
        self.assertEqual(rc, 8)
        self.assertIn("timed out after 13.0s", err)
        self.assertLessEqual(len(err), 120)

    def test_signal_handler_install_failure_is_tolerated(self):
        proc = FakeProc("ok", "", 0)
        with mock.patch.object(hao.subprocess, "Popen", return_value=proc), \
                mock.patch.object(hao.signal, "signal",
                                  side_effect=OSError("nope")):
            rc, out, _ = hao._TEST_REAL_RUN_HERDR(["pane", "get"])
        self.assertEqual((rc, out), (0, "ok"))

    def test_bad_wait_timeout_falls_back(self):
        self.assertEqual(
            hao._herdr_timeout(["pane", "wait-output", "p", "--timeout", "x"]),
            20)
        self.assertEqual(hao._herdr_timeout(["pane", "layout", "p"]), 5)

    def test_summary_uses_option_target(self):
        msg = hao._herdr_summary(["pane", "list", "--workspace", "w2"])
        self.assertIn("w2", msg)

    def test_terminate_handler_raises_system_exit(self):
        proc = FakeProc("ok", "", 0)
        handlers = {}
        def capture(sig, handler):
            if sig not in handlers:
                handlers[sig] = handler
            return handler
        with mock.patch.object(hao.subprocess, "Popen", return_value=proc), \
                mock.patch.object(hao.signal, "signal", side_effect=capture), \
                mock.patch.object(hao, "_kill_herdr_group") as kill:
            hao._TEST_REAL_RUN_HERDR(["pane", "get"])
            with self.assertRaises(SystemExit) as cm:
                handlers[hao.signal.SIGTERM](hao.signal.SIGTERM, None)
        self.assertEqual(cm.exception.code, 128 + hao.signal.SIGTERM)
        kill.assert_called()

    def test_timeout_then_unreadable_output_is_truncated(self):
        class P(FakeProc):
            def communicate(self, timeout=None):
                self.calls += 1
                if self.calls == 1:
                    raise subprocess.TimeoutExpired(["herdr"], timeout)
                raise RuntimeError("gone")
        proc = P()
        with mock.patch.object(hao.subprocess, "Popen", return_value=proc), \
                mock.patch.object(hao, "_kill_herdr_group"):
            rc, _, err = hao._TEST_REAL_RUN_HERDR(
                ["agent" + "x" * 100, "wait" + "y" * 100, "z" * 100])
        self.assertEqual(rc, 8)
        self.assertLessEqual(len(err), 120)
        self.assertTrue(err.endswith("..."))

    def test_finally_reaps_running_process(self):
        class P(FakeProc):
            def poll(self):
                return None
            def wait(self, timeout=None):
                raise RuntimeError("no")
        proc = P("ok", "", 0)
        with mock.patch.object(hao.subprocess, "Popen", return_value=proc), \
                mock.patch.object(hao, "_kill_herdr_group") as kill:
            rc, out, _ = hao._TEST_REAL_RUN_HERDR(["pane", "get"])
        self.assertEqual((rc, out), (0, "ok"))
        kill.assert_called()


class TestSafeReadGaps(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "hao", "tasks")
        self.env = mock.patch.dict(os.environ,
                                   {"HAO_STATE_DIR": self.state})
        self.env.start()
        self.sid = "abcd12345678"
        self.root = os.path.join(self.state, self.sid)
        os.makedirs(os.path.join(self.root, "sub"))

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_nested_regular_file(self):
        path = os.path.join(self.root, "sub", "result.md")
        with open(path, "w") as f:
            f.write("body")
        self.assertEqual(hao.safe_read(self.sid, path), "body")

    def test_path_outside_root_rejected(self):
        path = os.path.join(self.tmp.name, "outside.md")
        with open(path, "w") as f:
            f.write("x")
        self.assertIsNone(hao.safe_read(self.sid, path))

    def test_non_regular_file_rejected(self):
        self.assertIsNone(hao.safe_read(self.sid, os.path.join(self.root,
                                                                "sub")))

    def test_symlink_escape_rejected(self):
        outside = os.path.join(self.tmp.name, "outside.md")
        with open(outside, "w") as f:
            f.write("x")
        link = os.path.join(self.root, "link.md")
        os.symlink(outside, link)
        self.assertIsNone(hao.safe_read(self.sid, link))

    def test_missing_file_rejected(self):
        self.assertIsNone(hao.safe_read(self.sid,
                                        os.path.join(self.root, "nope.md")))


class TestSnapshotAndPreflightGaps(unittest.TestCase):
    def test_snapshot_agent_not_found(self):
        def fake(args, machine=None):
            return 1, "", '{"error":{"code":"agent_not_found"}}'
        with mock.patch.object(hao, "run_herdr", side_effect=fake):
            self.assertEqual(hao._agent_snapshot("w2:p9"),
                             (0, "unknown", None))

    def test_snapshot_error_code_other_than_8(self):
        def fake(args, machine=None):
            return 1, "", '{"error":{"code":"timeout"}}'
        with mock.patch.object(hao, "run_herdr", side_effect=fake):
            self.assertEqual(hao._agent_snapshot("w2:p9")[2], None)

    def test_snapshot_invalid_json(self):
        with mock.patch.object(hao, "run_herdr",
                               return_value=(0, "not json", "")):
            seq, st, rc = hao._agent_snapshot("w2:p9")
        self.assertEqual((seq, st, rc), (0, "unknown", 8))

    def test_machine_preflight_paths(self):
        with mock.patch.object(hao, "run_herdr", side_effect=OSError("x")):
            self.assertEqual(hao._machine_preflight("m"), 8)
        with mock.patch.object(hao, "run_herdr",
                               return_value=(0, "", "")):
            self.assertIsNone(hao._machine_preflight("m"))
        with mock.patch.object(hao, "run_herdr",
                               return_value=(1, "", '{"error":{"code":"unknown_machine"}}')):
            self.assertEqual(hao._machine_preflight("m"), 7)
        with mock.patch.object(hao, "run_herdr",
                               return_value=(1, "", "plain failure")):
            self.assertEqual(hao._machine_preflight("m"), 8)
        with mock.patch.object(hao, "run_herdr",
                               return_value=(1, "", '{"error":{"code":"other"}}')):
            self.assertEqual(hao._machine_preflight("m"), 7)


class TestDoctorGaps(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "hao", "tasks")
        self.env = mock.patch.dict(os.environ, {
            "HAO_STATE_DIR": self.state, "HERDR_ENV": "1"})
        self.env.start()
        self.old_json = hao._JSON_OUTPUT

    def tearDown(self):
        self.env.stop()
        hao._JSON_OUTPUT = self.old_json
        hao._JSON_HANDLED = False
        hao._ERROR_DETAIL = None
        self.tmp.cleanup()

    def test_machine_ok_json_and_text(self):
        def fake_herdr(args, machine=None):
            return 0, "machine output\n", ""
        with mock.patch.object(hao, "run_herdr", side_effect=fake_herdr):
            hao._JSON_OUTPUT = True
            self.assertEqual(hao.cmd_doctor("m"), 0)
            hao._JSON_OUTPUT = False
            self.assertEqual(hao.cmd_doctor("m"), 0)

    def test_machine_down_and_ledger_failure(self):
        with mock.patch.object(hao, "run_herdr",
                               return_value=(1, "", "down")):
            self.assertEqual(hao.cmd_doctor("m"), 7)
        with mock.patch.object(hao, "_load_module",
                               side_effect=RuntimeError("boom")), \
                mock.patch.object(hao, "run_herdr",
                                  return_value=(0, "", "")):
            self.assertEqual(hao.cmd_doctor("m"), 8)

    def test_text_checks_and_pane_width(self):
        class P:
            returncode = 0
            stdout = "ok"
            stderr = ""
        with mock.patch.object(hao.subprocess, "run", return_value=P()), \
                mock.patch.object(hao, "pane_width", return_value=30), \
                mock.patch.dict(os.environ, {"HERDR_PANE_ID": "w2:p9"}):
            rc = hao.cmd_doctor()
        self.assertEqual(rc, 0)

    def test_failed_check(self):
        class P:
            returncode = 1
            stdout = ""
            stderr = ""
        with mock.patch.object(hao.subprocess, "run", return_value=P()):
            self.assertEqual(hao.cmd_doctor(), 8)


if __name__ == "__main__":
    unittest.main()
