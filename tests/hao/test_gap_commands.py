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

ERR = '{"error":{"code":"%s"}}'


def run(fn, *args, **kwargs):
    out, err = io.StringIO(), io.StringIO()
    hao._ERROR_DETAIL = None
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = fn(*args, **kwargs)
    finally:
        hao._JSON_OUTPUT = False
        hao._JSON_HANDLED = False
    return rc, out.getvalue(), err.getvalue()


class CmdGapCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "hao", "tasks")
        self.env = mock.patch.dict(os.environ, {"HAO_STATE_DIR": self.state})
        self.env.start()
        self.led = Ledger()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()
        hao._ERROR_DETAIL = None
        hao._JSON_OUTPUT = False
        hao._JSON_HANDLED = False


def clear_stub(label="hao-moth", pane_rc=0, agent_rc=0, rename_rc=0):
    def fake(args, machine=None):
        if args[:2] == ["pane", "get"]:
            return pane_rc, json.dumps({"result": {"pane": {
                "pane_id": args[2], "label": label}}}), ""
        if args[:2] == ["agent", "get"]:
            return agent_rc, "", ERR % "agent_not_found" if agent_rc else ""
        if args[:2] == ["pane", "rename"]:
            return rename_rc, "", "" if not rename_rc else "boom"
        if args[:2] == ["agent", "rename"]:
            return rename_rc, "", "" if not rename_rc else "boom"
        return 0, '{"result":{}}', ""
    return fake


class TestClearGaps(CmdGapCase):
    def test_clear_success_text_and_json(self):
        with mock.patch.object(hao, "run_herdr",
                               side_effect=clear_stub(agent_rc=1)):
            self.assertEqual(run(hao.cmd_clear, "w2:p9", False)[0], 0)
            hao._JSON_OUTPUT = True
            rc, out, _ = run(hao.cmd_clear, "w2:p9", False)
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(out)["ok"])

    def test_clear_pane_get_failure(self):
        with mock.patch.object(hao, "run_herdr",
                               return_value=(1, "", ERR % "server_error")):
            self.assertEqual(run(hao.cmd_clear, "w2:p9", False)[0], 8)

    def test_clear_bad_pane_json(self):
        def fake(args, machine=None):
            return 0, "not json", ""
        with mock.patch.object(hao, "run_herdr", side_effect=fake):
            self.assertEqual(run(hao.cmd_clear, "w2:p9", False)[0], 8)

    def test_clear_dry_run_json(self):
        with mock.patch.object(hao, "run_herdr",
                               side_effect=clear_stub()):
            hao._JSON_OUTPUT = True
            rc, out, _ = run(hao.cmd_clear, "w2:p9", False, dry_run=True)
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(out)["dry_run"])

    def test_clear_rename_failures(self):
        with mock.patch.object(hao, "run_herdr",
                               side_effect=clear_stub(rename_rc=1)):
            self.assertEqual(run(hao.cmd_clear, "w2:p9", False)[0], 8)

    def test_clear_agent_get_other_error(self):
        def fake(args, machine=None):
            if args[:2] == ["pane", "get"]:
                return 0, '{"result":{"pane":{"label":"hao-moth"}}}', ""
            if args[:2] == ["agent", "get"]:
                return 1, "", ERR % "server_error"
            return 0, "{}", ""
        with mock.patch.object(hao, "run_herdr", side_effect=fake):
            self.assertEqual(run(hao.cmd_clear, "w2:p9", False)[0], 8)

    def test_clear_agent_rename_failure(self):
        def fake(args, machine=None):
            if args[:2] == ["pane", "get"]:
                return 0, '{"result":{"pane":{"label":"hao-moth"}}}', ""
            if args[:2] == ["agent", "get"]:
                return 0, '{"result":{"agent":{"agent_status":"idle"}}}', ""
            if args[:2] == ["agent", "rename"]:
                return 1, "", "boom"
            return 0, "{}", ""
        with mock.patch.object(hao, "run_herdr", side_effect=fake):
            self.assertEqual(run(hao.cmd_clear, "w2:p9", False)[0], 8)


class TestAbortGaps(CmdGapCase):
    def test_invalid_id_and_env(self):
        self.assertEqual(run(hao.cmd_abort, "bad", False)[0], 2)
        with mock.patch.dict(os.environ, {"HAO_ABORT_ALLOW": "yes"}):
            self.assertEqual(run(hao.cmd_abort, "abcd12345678", False)[0], 2)

    def test_missing_record(self):
        self.assertEqual(run(hao.cmd_abort, "abcd12345678", False)[0], 3)

    def test_cancel_only_paths(self):
        self.led.write_running("abcd12345678", target="w2:p9")
        with mock.patch.object(hao, "run_herdr",
                               return_value=(1, "", "boom")):
            self.assertEqual(run(hao.cmd_abort, "abcd12345678", False)[0], 8)
        self.led.write_done("deadbeef0000", target="w2:p9")
        with mock.patch.object(hao, "run_herdr",
                               return_value=(0, '{"result":{"agent":{}}}', "")):
            self.assertEqual(run(hao.cmd_abort, "deadbeef0000", False)[0], 6)
            hao._JSON_OUTPUT = True
            rc, out, _ = run(hao.cmd_abort, "abcd12345678", False)
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(out)["cancelled"])

    def test_interrupt_blocked_requires_approval(self):
        self.led.write_running("abcd12345678", target="w2:p9")
        with mock.patch.object(hao, "run_herdr",
                               return_value=(0, '{"result":{"agent":'
                                                '{"agent_status":"blocked"}}}', "")):
            self.assertEqual(run(hao.cmd_abort, "abcd12345678", True)[0], 5)

    def test_interrupt_success_json(self):
        self.led.write_running("abcd12345678", target="w2:p9")
        statuses = iter(["working", "idle"])

        def fake(args, machine=None):
            if args[:2] == ["agent", "get"]:
                return 0, json.dumps({"result": {"agent": {
                    "agent_status": next(statuses)}}}), ""
            if args[:2] == ["agent", "send-keys"]:
                return 0, "", ""
            return 0, "{}", ""
        with mock.patch.object(hao, "run_herdr", side_effect=fake), \
                mock.patch.dict(os.environ, {"HAO_ABORT_ALLOW": "1"}):
            hao._JSON_OUTPUT = True
            rc, out, _ = run(hao.cmd_abort, "abcd12345678", True)
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertTrue(data["interrupted"])

    def test_interrupt_no_target_and_send_failure(self):
        self.led.write_running("abcd12345678")
        self.assertEqual(run(hao.cmd_abort, "abcd12345678", True)[0], 3)

        self.led.write_running("deadbeef0000", target="w2:p9")
        with mock.patch.object(hao, "run_herdr",
                               return_value=(1, "", ERR % "server_error")):
            self.assertEqual(run(hao.cmd_abort, "deadbeef0000", True)[0], 8)

    def test_approval_file_and_tty(self):
        cfg = os.path.join(self.tmp.name, "cfg")
        os.makedirs(os.path.join(cfg, "hao"))
        path = os.path.join(cfg, "hao", "abort-approval")
        with open(path, "w") as f:
            f.write("abcd12345678")
        os.chmod(path, 0o600)
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": cfg,
                                          "HAO_ABORT_ALLOW": ""}):
            self.assertTrue(hao._abort_approved("abcd12345678"))
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": cfg,
                                          "HAO_ABORT_ALLOW": ""}), \
                mock.patch.object(hao.sys.stdin, "isatty",
                                  return_value=True), \
                mock.patch("builtins.input", return_value="yes"):
            self.assertTrue(hao._abort_approved("other"))
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": cfg,
                                          "HAO_ABORT_ALLOW": ""}), \
                mock.patch.object(hao.sys.stdin, "isatty",
                                  return_value=True), \
                mock.patch("builtins.input", side_effect=EOFError):
            self.assertFalse(hao._abort_approved("other"))


class TestStopGaps(CmdGapCase):
    def _stub(self, status="working", fail=None):
        def fake(args, machine=None):
            if fail and args[:2] == fail:
                return 1, "", ERR % "server_error"
            if args[:2] == ["agent", "get"]:
                return 0, json.dumps({"result": {"agent": {
                    "agent_status": status}}}), ""
            return 0, "{}", ""
        return fake

    def test_invalid_env(self):
        with mock.patch.dict(os.environ, {"HAO_ABORT_ALLOW": "no"}):
            self.assertEqual(run(hao.cmd_stop, "w2:p9")[0], 2)

    def test_agent_get_failures_and_bad_shape(self):
        with mock.patch.object(hao, "run_herdr",
                               return_value=(1, "", ERR % "server_error")):
            self.assertEqual(run(hao.cmd_stop, "w2:p9")[0], 8)
        with mock.patch.object(hao, "run_herdr",
                               return_value=(0, "not json", "")):
            self.assertEqual(run(hao.cmd_stop, "w2:p9")[0], 3)
        with mock.patch.object(hao, "run_herdr",
                               return_value=(0, '{"result":{"agent":[]}}', "")):
            self.assertEqual(run(hao.cmd_stop, "w2:p9")[0], 3)
        with mock.patch.object(hao, "run_herdr",
                               return_value=(1, "", ERR % "agent_not_found")):
            self.assertEqual(run(hao.cmd_stop, "w2:p9")[0], 3)

    def test_status_refusals(self):
        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._stub("unknown")):
            self.assertEqual(run(hao.cmd_stop, "w2:p9")[0], 9)
        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._stub("weird")):
            self.assertEqual(run(hao.cmd_stop, "w2:p9")[0], 9)
        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._stub("blocked")):
            self.assertEqual(run(hao.cmd_stop, "w2:p9")[0], 5)

    def test_idle_dry_run_and_success(self):
        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._stub("idle")):
            self.assertEqual(run(hao.cmd_stop, "w2:p9")[0], 0)
            hao._JSON_OUTPUT = True
            rc, out, _ = run(hao.cmd_stop, "w2:p9")
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["sent"], [])

        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._stub("working")), \
                mock.patch.object(hao.time, "sleep", return_value=None):
            self.assertEqual(run(hao.cmd_stop, "w2:p9", dry_run=True)[0], 0)
            hao._JSON_OUTPUT = True
            rc, out, _ = run(hao.cmd_stop, "w2:p9", dry_run=True)
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(out)["dry_run"])

    def test_send_failures_and_success(self):
        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._stub("working",
                                                      fail=["agent", "send-keys"])):
            self.assertEqual(run(hao.cmd_stop, "w2:p9")[0], 8)
        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._stub("working")), \
                mock.patch.object(hao, "_settled_status",
                                  return_value=("working", False)):
            hao._JSON_OUTPUT = True
            rc, out, _ = run(hao.cmd_stop, "w2:p9")
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["sent"], ["esc", "ctrl+c"])


class TestResultGaps(CmdGapCase):
    def test_file_allow_any_path_success_and_failure(self):
        path = os.path.join(self.tmp.name, "x.txt")
        with open(path, "w") as f:
            f.write("body")
        hao._JSON_OUTPUT = True
        rc, out, _ = run(hao.cmd_result, "abcd12345678", file=path,
                         allow_any_path=True)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["content"], "body")
        rc, _, _ = run(hao.cmd_result, "abcd12345678",
                       file=os.path.join(self.tmp.name, "missing"),
                       allow_any_path=True)
        self.assertEqual(rc, 2)

    def test_file_safe_path_rejected(self):
        rc, _, _ = run(hao.cmd_result, "abcd12345678",
                       file=os.path.join(self.tmp.name, "x"))
        self.assertEqual(rc, 2)

    def test_record_paths(self):
        self.assertEqual(run(hao.cmd_result, "abcd12345678")[0], 3)
        self.led.write_done("deadbeef0000")
        self.assertEqual(run(hao.cmd_result, "deadbeef0000")[0], 3)
        rp = os.path.join(self.state, "deadbeef0000", "result.md")
        os.makedirs(os.path.dirname(rp), exist_ok=True)
        with open(rp, "w") as f:
            f.write("body")
        self.led.write_done("deadbeef0000", result_path=rp)
        rc, out, _ = run(hao.cmd_result, "deadbeef0000")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "body\n")
        self.led.write_done("cafebabe0000", result_path=rp)
        rc, _, _ = run(hao.cmd_result, "cafebabe0000")
        self.assertEqual(rc, 2)


class TestListAndCleanGaps(CmdGapCase):
    def test_list_error_and_invalid_json(self):
        with mock.patch.object(hao, "run_herdr",
                               return_value=(1, "", ERR % "server_error")):
            self.assertEqual(run(hao.cmd_list)[0], 8)
        with mock.patch.object(hao, "run_herdr",
                               return_value=(0, "not json", "")):
            self.assertEqual(run(hao.cmd_list)[0], 8)

    def test_list_json_and_text(self):
        panes = [{"pane_id": "w2:p1", "label": "hao-moth-developer",
                  "agent": "claude", "cwd": "/tmp"},
                 {"pane_id": "w2:p2", "label": "yaml",
                  "agent": "x", "cwd": "/"}]
        with mock.patch.object(hao, "run_herdr",
                               return_value=(0, json.dumps(
                                   {"result": {"panes": panes}}), "")):
            hao._JSON_OUTPUT = True
            rc, out, _ = run(hao.cmd_list, json_out=True)
            self.assertEqual(rc, 0)
            self.assertEqual(len(json.loads(out)["panes"]), 1)
            rc, out, _ = run(hao.cmd_list, json_out=False)
        self.assertEqual(rc, 0)
        self.assertIn("hao-moth-developer", out)

    def test_clean_text_and_json(self):
        with mock.patch.object(hao, "_tidy_cancelled", return_value=0):
            self.assertEqual(run(hao.cmd_clean)[0], 0)
            hao._JSON_OUTPUT = True
            rc, out, _ = run(hao.cmd_clean)
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(out)["ok"])


if __name__ == "__main__":
    unittest.main()
