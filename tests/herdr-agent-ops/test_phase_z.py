import contextlib
import io
import json
import os
import stat
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
import ledger as led  # noqa: E402


def run_cli(argv, env=None):
    out, err = io.StringIO(), io.StringIO()
    saved = {k: os.environ.get(k) for k in
             ("HAO_STATE_DIR", "HERDR_ENV", "HERDR_PANE_ID")}
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
        hao._JSON_OUTPUT = False
        hao._JSON_HANDLED = False
        hao._LEDGER_WARNED = False
    return rc, out.getvalue(), err.getvalue()


def herdr_stub(args, machine=None):
    if args[:2] == ["agent", "list"]:
        return 0, json.dumps({"result": {"agents": []}}), ""
    if args[:2] == ["pane", "list"]:
        return 0, json.dumps({"result": {"panes": []}}), ""
    if args[:2] == ["pane", "get"]:
        return 0, json.dumps({"result": {"pane": {
            "pane_id": args[2], "label": "hao-hawk", "agent": None}}}), ""
    if args[:2] == ["agent", "get"]:
        return 0, json.dumps({"result": {"agent": {
            "agent_status": "idle", "state_change_seq": 0}}}), ""
    return 0, "{}", ""


class TestZ1Location(unittest.TestCase):
    def test_hao_state_dir_override_is_direct(self):
        with tempfile.TemporaryDirectory() as d:
            state = os.path.join(d, "custom-tasks")
            with mock.patch.dict(os.environ, {"HAO_STATE_DIR": state}):
                self.assertEqual(led.state_dir(), os.path.abspath(state))
            self.assertFalse(os.path.exists(state))

    def test_linux_uses_xdg_runtime_dir(self):
        saved = os.environ.pop("HAO_STATE_DIR", None)
        try:
            with mock.patch.dict(os.environ,
                                 {"XDG_RUNTIME_DIR": "/run/user/42"}):
                with mock.patch.object(led.sys, "platform", "linux"):
                    self.assertEqual(led.state_dir(), "/run/user/42/hao/tasks")
        finally:
            if saved is not None:
                os.environ["HAO_STATE_DIR"] = saved

    def test_fallback_is_per_user_temp(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(led.sys, "platform", "darwin"), \
                mock.patch.object(led.tempfile, "gettempdir", return_value=d):
            os.environ.pop("HAO_STATE_DIR", None)
            expected = os.path.join(d, f"hao-{os.getuid()}", "tasks")
            self.assertEqual(led.state_dir(), expected)
            self.assertFalse(os.path.exists(expected))

    def test_created_dir_is_0700(self):
        with tempfile.TemporaryDirectory() as outer:
            state = os.path.join(outer, "hao", "tasks")
            with mock.patch.dict(os.environ, {"HAO_STATE_DIR": state}):
                led.Ledger().write_running("abcd12345678")
                mode = stat.S_IMODE(os.stat(state).st_mode)
                self.assertEqual(mode, 0o700)
                self.assertEqual(stat.S_IMODE(os.stat(os.path.dirname(state)).st_mode),
                                 0o700)


class TestZ2ReadOnlyNoCreate(unittest.TestCase):
    def test_readonly_and_missing_task_commands_create_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            state = os.path.join(d, "hao", "tasks")
            env = {"HAO_STATE_DIR": state, "HERDR_ENV": "1",
                   "HERDR_PANE_ID": None}
            run = SimpleNamespace(returncode=0, stdout="ok", stderr="")
            commands = [
                ["doctor", "--json"],
                ["status", "w2:p9", "--json"],
                ["list", "--json"],
                ["restore", "--dry-run", "--json"],
                ["suggest", "task", "--live-names", "--label-roles", "--json"],
                ["clean", "--dry-run", "--json"],
                ["cancel", "deadbeef0000", "--json"],
                ["result", "deadbeef0000", "--json"],
                ["done", "hao-" + "deadbeef0000" + "0011", "--json"],
            ]
            with mock.patch.object(hao, "run_herdr", side_effect=herdr_stub), \
                    mock.patch.object(hao.subprocess, "run", return_value=run):
                for argv in commands:
                    with self.subTest(argv=argv):
                        rc, _out, _err = run_cli(argv, env)
                        self.assertNotIn(rc, (4, 9), argv)
                        self.assertEqual(os.listdir(d), [], argv)
                with mock.patch.object(hao, "_wait_sentinel", return_value=4):
                    rc, _out, _err = run_cli(
                        ["wait", "w2:p9", "deadbeef0000", "--timeout", "1"], env)
                self.assertEqual(rc, 4)
                self.assertEqual(os.listdir(d), [])
                with mock.patch.object(hao, "_wait_sentinel",
                                       return_value={"status": "done"}):
                    rc, _out, _err = run_cli(
                        ["wait", "w2:p9", "deadbeef0000", "--json"], env)
                self.assertEqual(rc, 0)
                self.assertEqual(os.listdir(d), [])
            self.assertFalse(os.path.exists(state))


class TestZ3Consume(unittest.TestCase):
    def _state(self, d):
        return os.path.join(d, "hao", "tasks")

    def test_wait_done_consumes_record_and_tree(self):
        with tempfile.TemporaryDirectory() as d:
            state = self._state(d)
            os.environ["HAO_STATE_DIR"] = state
            try:
                led.Ledger().write_running("abcd12345678", target="w2:p9")
                with mock.patch.object(
                        hao, "_wait_sentinel",
                        return_value={"status": "done", "summary": "ok"}):
                    rc, out, err = run_cli(
                        ["wait", "w2:p9", "abcd12345678", "--json"],
                        {"HAO_STATE_DIR": state})
                self.assertEqual(rc, 0, err)
                self.assertEqual(json.loads(out)["status"], "done")
                self.assertFalse(os.path.exists(os.path.join(state, "abcd12345678.json")))
                self.assertFalse(os.path.exists(state))
                self.assertFalse(os.path.exists(os.path.dirname(state)))
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_abort_interrupt_tombstone_waits_for_consumer(self):
        with tempfile.TemporaryDirectory() as d:
            state = self._state(d)
            os.environ["HAO_STATE_DIR"] = state
            try:
                led.Ledger().write_running("abcd12345678", target="w2:p9")
                self.assertEqual(led.Ledger().cancel("abcd12345678"), 0)
                def status_stub(args, machine=None):
                    if args[:2] == ["agent", "get"]:
                        return 0, json.dumps({"result": {"agent": {
                            "agent_status": "idle"}}}), ""
                    return 0, "{}", ""
                with mock.patch.object(hao, "run_herdr",
                                       side_effect=status_stub), \
                        mock.patch.object(hao.time, "sleep", return_value=None):
                    rc, _out, err = run_cli(
                        ["abort", "abcd12345678", "--interrupt", "--json"],
                        {"HAO_STATE_DIR": state, "HAO_ABORT_ALLOW": "1"})
                self.assertEqual(rc, 0, err)
                self.assertTrue(led.Ledger().get("abcd12345678")["interrupted"])
                rc, _out, _err = run_cli(
                    ["wait", "w2:p9", "abcd12345678"],
                    {"HAO_STATE_DIR": state})
                self.assertEqual(rc, 10)
                self.assertFalse(os.path.exists(state))
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_file_mode_wait_keeps_record_until_result(self):
        with tempfile.TemporaryDirectory() as d:
            state = self._state(d)
            sid = "beef11223344"
            rp = os.path.join(state, sid, "result.md")
            os.makedirs(os.path.dirname(rp), exist_ok=True)
            with open(rp, "w") as f:
                f.write("body")
            os.environ["HAO_STATE_DIR"] = state
            try:
                led.Ledger().write_running(sid, target="w2:p9")
                led.Ledger().write_done(sid, result_path=rp)
                rc, out, _err = run_cli(
                    ["wait", "w2:p9", sid, "--mode", "file", "--json"],
                    {"HAO_STATE_DIR": state})
                self.assertEqual(rc, 0)
                self.assertEqual(json.loads(out)["result_path"], rp)
                self.assertTrue(os.path.exists(os.path.join(state, sid + ".json")))
                self.assertTrue(os.path.exists(rp))
                rc, out, _err = run_cli(["result", sid, "--json"],
                                        {"HAO_STATE_DIR": state})
                self.assertEqual(rc, 0)
                self.assertEqual(json.loads(out)["content"], "body")
                self.assertFalse(os.path.exists(state))
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_cancel_tombstone_remains_until_wait(self):
        with tempfile.TemporaryDirectory() as d:
            state = self._state(d)
            os.environ["HAO_STATE_DIR"] = state
            try:
                led.Ledger().write_running("abcd12345678", target="w2:p9")
                rc, _out, _err = run_cli(
                    ["cancel", "abcd12345678", "--json"],
                    {"HAO_STATE_DIR": state})
                self.assertEqual(rc, 0)
                self.assertTrue(os.path.exists(os.path.join(state,
                                                            "abcd12345678.json")))
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_tidy_collects_orphan_locks_and_results(self):
        with tempfile.TemporaryDirectory() as d:
            state = self._state(d)
            os.makedirs(state)
            open(os.path.join(state, "deadbeef0000.json.lock"), "w").close()
            os.makedirs(os.path.join(state, "deadbeef0000"))
            with mock.patch.dict(os.environ, {"HAO_STATE_DIR": state}):
                stats = led.Ledger().cleanup()
            self.assertEqual(stats["locks_removed"], 1)
            self.assertEqual(stats["dirs_removed"], 1)
            self.assertFalse(os.path.exists(state))


class TestZ6Prompt(unittest.TestCase):
    def test_prompt_pins_caller_state_dir(self):
        with tempfile.TemporaryDirectory() as d:
            state = os.path.join(d, "hao", "tasks")
            with mock.patch.dict(os.environ, {"HAO_STATE_DIR": state}):
                prompt = hao.build_prompt("task", "hao-" + "aabbccddeeff0011")
                self.assertIn(f'HAO_STATE_DIR="{state}"', prompt)
                self.assertFalse(os.path.exists(state))


if __name__ == "__main__":
    unittest.main()
