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
    saved = {}
    for key in ("HAO_STATE_DIR", "HERDR_PANE_ID", "HAO_ABORT_ALLOW"):
        saved[key] = os.environ.get(key)
    if env:
        for key, value in env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
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
    return rc, out.getvalue(), err.getvalue()


class TestPhaseAErrors(unittest.TestCase):
    def assert_error(self, rc, err, cmd, code):
        self.assertEqual(rc, code)
        lines = [l for l in err.splitlines() if l.strip()]
        self.assertTrue(lines)
        self.assertTrue(lines[-1].startswith(f"hao {cmd}:"), lines)
        self.assertIn(f"(exit {code})", lines[-1])

    def test_name_invalid(self):
        rc, _, err = run_cli(["name", "w2:p9", "BAD_NAME"])
        self.assert_error(rc, err, "name", 2)
        self.assertIn("^[a-z]{4,6}$", err)

    def test_clear_conflict(self):
        def stub(args, machine=None):
            if args[:2] == ["pane", "get"]:
                return 0, json.dumps({"result": {"pane": {"label": "yaml"}}}), ""
            return 0, "{}", ""

        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc, _, err = run_cli(["clear", "w2:p1"])
        self.assert_error(rc, err, "clear", 6)

    def test_restore_backend_error(self):
        err_json = '{"error":{"code":"unknown_machine"}}'
        with mock.patch.object(hao, "run_herdr",
                               return_value=(1, "", err_json)):
            rc, _, err = run_cli(["restore", "--dry-run"])
        self.assert_error(rc, err, "restore", 7)

    def test_ask_mode_error(self):
        def stub(args, machine=None):
            if args[:2] == ["pane", "layout"]:
                return 0, '{"result":{"layout":{"panes":[]}}}', ""
            if args[:2] == ["agent", "get"]:
                return 0, '{"result":{"agent":{"agent_status":"idle"}}}', ""
            return 0, "{}", ""
        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc, _, err = run_cli(["ask", "w2:p9", "task", "--mode", "lifecycle"])
        self.assert_error(rc, err, "ask", 2)

    def test_wait_invalid_token(self):
        rc, _, err = run_cli(["wait", "w2:p9", "not-a-token", "--timeout", "2"])
        self.assert_error(rc, err, "wait", 2)

    def test_wait_timeout_reason(self):
        with mock.patch.object(hao, "_wait_sentinel", return_value=4):
            rc, _, err = run_cli(["wait", "w2:p9", "deadbeef0000", "--timeout", "2"])
        self.assert_error(rc, err, "wait", 4)
        self.assertIn("timeout after 2s", err)

    def test_done_invalid_token(self):
        rc, _, err = run_cli(["done", "bad id!"])
        self.assert_error(rc, err, "done", 2)

    def test_cancel_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            rc, _, err = run_cli(["cancel", "deadbeef0000"],
                                 {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
        self.assert_error(rc, err, "cancel", 3)

    def test_abort_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            rc, _, err = run_cli(["abort", "deadbeef0000"],
                                 {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
        self.assert_error(rc, err, "abort", 3)

    def test_suggest_missing_arg(self):
        rc, _, err = run_cli(["suggest"])
        self.assertEqual(rc, 2)
        self.assertIn("required", err)

    def test_list_backend_error(self):
        err_json = '{"error":{"code":"unknown_machine"}}'
        with mock.patch.object(hao, "run_herdr",
                               return_value=(1, "", err_json)):
            rc, _, err = run_cli(["list"])
        self.assert_error(rc, err, "list", 7)

    def test_status_not_found(self):
        err_json = '{"error":{"code":"agent_not_found"}}'
        with mock.patch.object(hao, "run_herdr",
                               return_value=(1, "", err_json)):
            rc, _, err = run_cli(["status", "w2:pX"])
        self.assert_error(rc, err, "status", 3)

    def test_say_no_target(self):
        rc, _, err = run_cli(["say", "hello"], {"HERDR_PANE_ID": None})
        self.assert_error(rc, err, "say", 3)

    def test_result_task_not_found(self):
        with tempfile.TemporaryDirectory() as d:
            rc, _, err = run_cli(["result", "deadbeef0000"],
                                 {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
        self.assert_error(rc, err, "result", 3)
        self.assertIn("task not found", err)

    def test_doctor_machine_error(self):
        with mock.patch.object(hao, "run_herdr", return_value=(1, "", "")):
            rc, _, err = run_cli(["doctor", "--machine", "nope"])
        self.assert_error(rc, err, "doctor", 7)

    def test_alias_uses_canonical_reason(self):
        rc, _, err = run_cli(["w", "w2:p9", "not-a-token"])
        self.assert_error(rc, err, "wait", 2)


class TestPhaseAIds(unittest.TestCase):
    def test_bare_id_requires_12_hex(self):
        self.assertEqual(hao.normalize_id("deadbeef0000"), "deadbeef0000")
        with self.assertRaises(ValueError):
            hao.normalize_id("not-a-token")
        with self.assertRaises(ValueError):
            hao.normalize_id("run1")

    def test_full_token_unchanged(self):
        self.assertEqual(hao.normalize_id("hao-abcdef1234567890"),
                         "abcdef123456")
        with self.assertRaises(ValueError):
            hao.normalize_id("hao-abc")

    def test_wait_rejects_bare_nonhex(self):
        rc, _, err = run_cli(["wait", "w2:p9", "not-a-token", "--timeout", "1"])
        self.assertEqual(rc, 2)
        self.assertIn("invalid token", err)

    def test_cancel_rejects_bare_nonhex(self):
        rc, _, err = run_cli(["cancel", "zzzz99999999"])
        self.assertEqual(rc, 2)
        self.assertIn("invalid id", err)


class TestPhaseASuggest(unittest.TestCase):
    def test_default_is_one_human_line(self):
        rc, out, err = run_cli(["suggest", "审查 PR", "--live-names", "--label-roles"])
        self.assertEqual(rc, 0)
        self.assertEqual(out, "验证审阅: hawk, lens, prism\n")
        self.assertEqual(err, "")

    def test_json_is_json_only(self):
        rc, out, err = run_cli(["suggest", "审查 PR", "--json",
                                "--live-names", "--label-roles"])
        self.assertEqual(rc, 0)
        self.assertEqual(len(out.splitlines()), 1)
        self.assertIsInstance(json.loads(out), dict)
        self.assertEqual(err, "")

    def test_json_has_no_human_prefix(self):
        rc, out, _ = run_cli(["suggest", "审查 PR", "--json",
                              "--live-names", "--label-roles"])
        self.assertEqual(rc, 0)
        self.assertFalse(out.startswith("验证审阅"))


class TestPhaseAStatus(unittest.TestCase):
    def _stub(self, agent_rc=0, pane_rc=0):
        def stub(args, machine=None):
            if args[:2] == ["agent", "get"] and agent_rc:
                return 1, "", '{"error":{"code":"agent_not_found"}}'
            if args[:2] == ["pane", "get"] and pane_rc:
                return 1, "", '{"error":{"code":"pane_not_found"}}'
            if args[:2] == ["agent", "get"]:
                return 0, json.dumps({"result": {"agent": {
                    "agent": "claude", "agent_status": "idle", "name": "forge"}}}), ""
            if args[:2] == ["pane", "get"]:
                return 0, json.dumps({"result": {"pane": {
                    "pane_id": args[2], "label": "hao-forge-ops",
                    "agent": None if agent_rc else "claude"}}}), ""
            return 0, "{}", ""
        return stub

    def test_json_schema_and_tasks(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                Ledger().write_running("abcd12345678", target="w2:p9")
                Ledger().write_done("deadbeef0000", target="w2:p9")
                Ledger().write_running("cafebabe0000", target="w2:p9")
                Ledger().cancel("cafebabe0000")
                Ledger().write_done("feed12345678", target="w2:pX")
                with mock.patch.object(hao, "run_herdr", side_effect=self._stub()):
                    rc, out, err = run_cli(["status", "w2:p9"])
                data = json.loads(out)
                self.assertEqual(rc, 0)
                self.assertEqual(set(data), {"pane_id", "label", "agent",
                                             "agent_status", "name", "scope", "tasks"})
                self.assertEqual(data["scope"], "ops")
                self.assertEqual(data["tasks"]["running"][0]["shortid"],
                                 "abcd12345678")
                self.assertEqual(data["tasks"]["done"], 1)
                self.assertEqual(data["tasks"]["cancelled"], 1)
                self.assertEqual(err, "")
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_orphan_flag(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                sid = "abcd12345678"
                Ledger().write_running(sid, target="w2:p9")
                rec = json.load(open(_path(sid)))
                rec["updated"] = time.time() - 90000
                with open(_path(sid), "w") as f:
                    json.dump(rec, f)
                with mock.patch.object(hao, "run_herdr", side_effect=self._stub()):
                    _, out, _ = run_cli(["status", "w2:p9"])
                self.assertTrue(json.loads(out)["tasks"]["running"][0]["orphan"])
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_shell_pane_has_null_agent(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                with mock.patch.object(hao, "run_herdr",
                                       side_effect=self._stub(agent_rc=1)):
                    rc, out, _ = run_cli(["status", "w2:p9"])
                data = json.loads(out)
                self.assertEqual(rc, 0)
                self.assertIsNone(data["agent"])
                self.assertIsNone(data["agent_status"])
                self.assertIsNone(data["name"])
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_text_mode(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                with mock.patch.object(hao, "run_herdr", side_effect=self._stub()):
                    rc, out, _ = run_cli(["status", "w2:p9", "--text"])
                self.assertEqual(rc, 0)
                self.assertTrue(out.startswith("pane: w2:p9"))
                self.assertFalse(out.lstrip().startswith("{"))
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_status_error_path(self):
        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._stub(agent_rc=1, pane_rc=1)):
            rc, _, err = run_cli(["status", "w2:pX"])
        self.assertEqual(rc, 3)
        self.assertIn("hao status:", err)

    def test_status_no_target(self):
        rc, _, err = run_cli(["status"], {"HERDR_PANE_ID": None})
        self.assertEqual(rc, 3)
        self.assertIn("hao status:", err)


if __name__ == "__main__":
    unittest.main()
