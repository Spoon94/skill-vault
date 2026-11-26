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


class TestR8AgentNameResolution(unittest.TestCase):
    def test_name_after_label_and_agent_type_miss(self):
        calls = []

        def stub(args, machine=None):
            calls.append(args)
            if args[:2] == ["pane", "list"]:
                return 0, json.dumps({"result": {"panes": [
                    {"pane_id": "w2:p1", "label": "other", "agent": "pi"}]}}), ""
            if args[:2] == ["agent", "list"]:
                return 0, json.dumps({"result": {"agents": [
                    {"name": "verse", "pane_id": "w2:p9"}]}}), ""
            return 0, "{}", ""
        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            self.assertEqual(hao.resolve_target("verse"), "w2:p9")
        self.assertIn(["agent", "list"], calls)

    def test_label_pane_and_wtp_unchanged(self):
        calls = []

        def stub(args, machine=None):
            calls.append(args)
            if args[:2] == ["pane", "list"]:
                return 0, json.dumps({"result": {"panes": [
                    {"pane_id": "w2:p9", "label": "hao-verse"}]}}), ""
            return 0, "{}", ""
        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            self.assertEqual(hao.resolve_target("hao-verse"), "w2:p9")
        self.assertNotIn(["agent", "list"], calls)
        self.assertEqual(hao.resolve_target("w2:p9"), "w2:p9")
        self.assertEqual(hao.resolve_target("w2:t1:p9"), "w2:p9")

    def test_unknown_name_returns_input(self):
        def stub(args, machine=None):
            if args[:2] == ["pane", "list"]:
                return 0, json.dumps({"result": {"panes": []}}), ""
            if args[:2] == ["agent", "list"]:
                return 0, json.dumps({"result": {"agents": []}}), ""
            return 0, "{}", ""
        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            self.assertEqual(hao.resolve_target("ghost"), "ghost")

    def test_ask_name_target_gets_width_and_pane_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            state = os.path.join(d, "hao", "tasks")
            os.environ["HAO_STATE_DIR"] = state

            def stub(args, machine=None):
                if args[:2] == ["pane", "list"]:
                    return 0, json.dumps({"result": {"panes": []}}), ""
                if args[:2] == ["agent", "list"]:
                    return 0, json.dumps({"result": {"agents": [
                        {"name": "verse", "pane_id": "w2:p9"}]}}), ""
                if args[:2] == ["pane", "layout"]:
                    return 0, json.dumps({"result": {"layout": {"panes": [
                        {"pane_id": "w2:p9", "rect": {"width": 25}}]}}}), ""
                if args[:2] == ["agent", "get"]:
                    return 0, json.dumps({"result": {"agent": {
                        "agent_status": "idle", "state_change_seq": 0}}}), ""
                return 0, "{}", ""
            try:
                with mock.patch.object(hao, "run_herdr", side_effect=stub):
                    rc, out, err = run_cli(
                        ["ask", "verse", "task", "--json"],
                        {"HAO_STATE_DIR": state})
                self.assertEqual(rc, 0, err)
                data = json.loads(out)
                self.assertEqual(data["target_cols"], 25)
                rec = Ledger().get(data["shortid"])
                self.assertEqual(rec["target"], "w2:p9")
                self.assertIn("warning", err)
            finally:
                os.environ.pop("HAO_STATE_DIR", None)


class TestR9WaiterAndTidy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "hao", "tasks")
        os.environ["HAO_STATE_DIR"] = self.state
        self.sid = "abcd12345678"

    def tearDown(self):
        os.environ.pop("HAO_STATE_DIR", None)
        self.tmp.cleanup()

    def test_wait_in_fallback_stage_sees_interrupt_as_10(self):
        Ledger().write_running(self.sid, target="w2:p9")
        saw_wait = []

        def stub(args, machine=None):
            if args[:2] == ["agent", "get"]:
                return 0, json.dumps({"result": {"agent": {
                    "agent_status": "idle"}}}), ""
            if args[:2] == ["agent", "wait"]:
                saw_wait.append(args)
                Ledger().cancel(self.sid)
                Ledger().mark_interrupted(self.sid)
            return 0, "{}", ""

        with mock.patch.object(hao, "FAST_PATH_SECONDS", 0), \
                mock.patch.object(hao, "run_herdr", side_effect=stub), \
                mock.patch.object(hao, "_sentinel_scan_tail",
                                  return_value=(None, None)), \
                mock.patch.object(hao.time, "sleep", return_value=None):
            rc = hao.cmd_wait("w2:p9", self.sid, 2)
        self.assertEqual(rc, 10)
        self.assertTrue(saw_wait)
        self.assertIsNone(Ledger().get(self.sid))

    def _mark_interrupted(self, interrupted_age=0, heartbeat_age=0):
        import time
        Ledger().write_running(self.sid, target="w2:p9")
        Ledger().cancel(self.sid)
        Ledger().mark_interrupted(self.sid)
        rec = Ledger().get(self.sid)
        rec["interrupted_at"] = time.time() - interrupted_age
        rec["updated"] = time.time() - heartbeat_age
        from ledger import _path
        with open(_path(self.sid), "w") as f:
            json.dump(rec, f)

    def test_tidy_removes_interrupted_without_fresh_heartbeat_after_60s(self):
        self._mark_interrupted(interrupted_age=61, heartbeat_age=61)
        Ledger().tidy_cancelled(lambda rec: True)
        self.assertIsNone(Ledger().get(self.sid))

    def test_tidy_keeps_interrupted_with_fresh_heartbeat(self):
        self._mark_interrupted(interrupted_age=61, heartbeat_age=0)
        Ledger().tidy_cancelled(lambda rec: True)
        self.assertIsNotNone(Ledger().get(self.sid))

    def test_tidy_keeps_recent_interrupt_mark(self):
        self._mark_interrupted(interrupted_age=10, heartbeat_age=10)
        Ledger().tidy_cancelled(lambda rec: True)
        self.assertIsNotNone(Ledger().get(self.sid))


if __name__ == "__main__":
    unittest.main()
