import contextlib
import io
import json
import os
import signal
import sys
import tempfile
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
             ("HAO_STATE_DIR", "HERDR_PANE_ID", "PATH",
              "SHIM_SLEEP", "SHIM_PIDLOG")}
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


def _alarm(seconds=8):
    class Ctx:
        def __enter__(self):
            self.old = signal.signal(signal.SIGALRM, self._boom)
            signal.alarm(seconds)
        def _boom(self, signum, frame):
            raise TimeoutError("test exceeded total timeout")
        def __exit__(self, *exc):
            signal.alarm(0)
            signal.signal(signal.SIGALRM, self.old)
    return Ctx()


class TestR13HerdrTimeout(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = os.path.join(self.tmp.name, "bin")
        os.makedirs(self.bin)
        self.shim = os.path.join(self.bin, "herdr")
        with open(self.shim, "w") as f:
            f.write('''#!/bin/sh
cmd="$1 $2"
sleep_it=0
case "$SHIM_SLEEP" in
  all) sleep_it=1 ;;
  prompt) [ "$cmd" = "agent prompt" ] && sleep_it=1 ;;
  wait-output) [ "$cmd" = "pane wait-output" ] && sleep_it=1 ;;
  agent-wait) [ "$cmd" = "agent wait" ] && sleep_it=1 ;;
  pane-read) [ "$cmd" = "pane read" ] && sleep_it=1 ;;
esac
if [ "$sleep_it" = 1 ]; then
  echo "$$" >> "$SHIM_PIDLOG"
  exec sleep 60
fi
case "$cmd" in
  "agent get") printf '%s\\n' '{"result":{"agent":{"agent_status":"idle","state_change_seq":0}}}' ;;
  "pane layout") printf '%s\\n' '{"result":{"layout":{"panes":[]}}}' ;;
  "pane list") printf '%s\\n' '{"result":{"panes":[]}}' ;;
  "agent list") printf '%s\\n' '{"result":{"agents":[]}}' ;;
  "pane read") printf '%s\\n' '{"result":{"read":{"text":""}}}' ;;
  "pane wait-output") printf '%s\\n' '{"result":{"matched_line":""}}' ;;
  "agent wait") printf '%s\\n' '{}' ;;
  "machine status") printf '%s\\n' '{}' ;;
  "agent prompt") printf '%s\\n' '{}' ;;
  "pane get") printf '%s\\n' '{"result":{"pane":{"pane_id":"w2:p9"}}}' ;;
  *) printf '%s\\n' '{}' ;;
esac
exit 0
''')
        os.chmod(self.shim, 0o755)
        self.state = os.path.join(self.tmp.name, "hao", "tasks")
        self.pidlog = os.path.join(self.tmp.name, "pids")
        self.env = {"HAO_STATE_DIR": self.state, "HERDR_PANE_ID": None,
                    "PATH": self.bin + ":" + os.environ.get("PATH", ""),
                    "SHIM_SLEEP": "all", "SHIM_PIDLOG": self.pidlog}

    def tearDown(self):
        # only kill PIDs this test started, never by name/pattern
        if os.path.exists(self.pidlog):
            with open(self.pidlog) as f:
                for line in f:
                    pid = line.strip()
                    if pid.isdigit():
                        try:
                            os.kill(int(pid), signal.SIGKILL)
                        except ProcessLookupError:
                            pass
        self.tmp.cleanup()

    def _assert_no_live_shim(self):
        if not os.path.exists(self.pidlog):
            return
        with open(self.pidlog) as f:
            for line in f:
                pid = line.strip()
                if not pid.isdigit():
                    continue
                with self.assertRaises(ProcessLookupError):
                    os.kill(int(pid), 0)

    def _run(self, argv, sleep_mode):
        if os.path.exists(self.pidlog):
            os.remove(self.pidlog)
        env = dict(self.env, SHIM_SLEEP=sleep_mode)
        with _alarm(8), mock.patch.object(hao, "_herdr_timeout",
                                          return_value=0.5):
            rc, out, err = run_cli(argv, env)
        self._assert_no_live_shim()
        return rc, out, err

    def test_ask_prompt_returns_8_with_unknown_delivery(self):
        rc, _out, err = self._run(["ask", "w2:p9", "task", "--json"], "prompt")
        self.assertEqual(rc, 8)
        self.assertIn("prompt delivery unknown", err)
        self.assertIn("pane read w2:p9", err)
        recs = [f for f in os.listdir(self.state) if f.endswith(".json")]
        self.assertEqual(len(recs), 1)
        os.environ["HAO_STATE_DIR"] = self.state
        try:
            rec = Ledger().get(recs[0][:-5])
        finally:
            os.environ.pop("HAO_STATE_DIR", None)
        self.assertEqual(rec["status"], "cancelled")

    def test_wait_fast_path_returns_8(self):
        rc, _out, err = self._run(
            ["wait", "w2:p9", "deadbeef0000", "--json"], "wait-output")
        self.assertEqual(rc, 8)
        self.assertIn("timed out", err)

    def test_wait_backstop_returns_8(self):
        with mock.patch.object(hao, "FAST_PATH_SECONDS", 0):
            rc, _out, err = self._run(
                ["wait", "w2:p9", "deadbeef0000", "--json"], "agent-wait")
        self.assertEqual(rc, 8)
        self.assertIn("timed out", err)

    def test_status_returns_8(self):
        rc, out, err = self._run(["status", "w2:p9", "--json"], "all")
        self.assertEqual(rc, 8)
        self.assertIn("status query failed", err)
        self.assertEqual(json.loads(out)["exit"], 8)

    def test_stop_returns_8(self):
        rc, out, _err = self._run(["stop", "w2:p9", "--json"], "all")
        self.assertEqual(rc, 8)
        self.assertEqual(json.loads(out)["exit"], 8)

    def test_list_returns_8(self):
        rc, out, _err = self._run(["list", "--json"], "all")
        self.assertEqual(rc, 8)
        self.assertEqual(json.loads(out)["exit"], 8)

    def test_wait_all_modes_return_8_without_rescan(self):
        for mode in ("sentinel", "lifecycle", "file"):
            with self.subTest(mode=mode):
                rc, out, err = self._run(
                    ["wait", "w2:p9", "deadbeef0000", "--mode", mode,
                     "--timeout", "20", "--json"], "all")
                self.assertEqual(rc, 8, err)
                lines = [line for line in out.splitlines() if line.strip()]
                self.assertEqual(len(lines), 1, out)
                self.assertEqual(json.loads(lines[0])["exit"], 8)
                with open(self.pidlog) as f:
                    self.assertEqual(len(f.read().split()), 1)
                self.assertFalse(os.path.exists(self.state))

    def test_timeout_error_is_short_and_omits_prompt(self):
        if os.path.exists(self.pidlog):
            os.remove(self.pidlog)
        prompt = "task line one\ntask line two\n" + ("X" * 200)
        env = {k: v for k, v in self.env.items() if v is not None}
        env["SHIM_SLEEP"] = "prompt"
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(hao, "_herdr_timeout", return_value=0.5):
            rc, _out, err = hao.run_herdr(
                ["agent", "prompt", "w2:p4E", prompt])
        self.assertEqual(rc, 8)
        self.assertLessEqual(len(err), 120, err)
        self.assertIn("herdr agent prompt w2:p4E", err)
        self.assertNotIn("task line", err)
        self.assertNotIn("X" * 20, err)
        self._assert_no_live_shim()

    def test_ask_all_hang_returns_8_without_ledger(self):
        rc, out, err = self._run(["ask", "w2:p9", "task", "--json"], "all")
        self.assertEqual(rc, 8)
        lines = [line for line in out.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, out)
        self.assertFalse(os.path.exists(self.state), err)

    def test_timeout_limits(self):
        self.assertEqual(hao._herdr_timeout(["pane", "layout", "p"]), 5)
        self.assertEqual(hao._herdr_timeout(["agent", "prompt", "p"]), 30)
        self.assertEqual(hao._herdr_timeout(["pane", "wait-output", "p",
                                             "--timeout", "1000"]), 6)
        self.assertEqual(hao._herdr_timeout(["agent", "wait", "p",
                                             "--timeout", "8000"]), 13)
        self.assertEqual(hao._herdr_timeout(["agent", "get", "p"]), 20)


class TestR17AskSingleGetAndFailFast(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "hao", "tasks")

    def tearDown(self):
        self.tmp.cleanup()

    def _ask_stub(self, gets):
        def stub(args, machine=None):
            if args[:2] == ["pane", "layout"]:
                return 0, json.dumps({"result": {"layout": {"panes": []}}}), ""
            if args[:2] == ["agent", "get"]:
                gets.append(args)
                return 0, json.dumps({"result": {"agent": {
                    "agent_status": "idle", "state_change_seq": 3}}}), ""
            if args[:2] == ["agent", "prompt"]:
                return 0, "{}", ""
            return 0, "{}", ""
        return stub

    def test_async_ask_gets_agent_once(self):
        gets = []
        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._ask_stub(gets)):
            rc, _out, err = run_cli(
                ["ask", "w2:p9", "task", "--json"],
                {"HAO_STATE_DIR": self.state})
        self.assertEqual(rc, 0, err)
        self.assertEqual(len(gets), 1, gets)

    def test_lifecycle_precheck_reuses_same_get(self):
        gets = []
        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._ask_stub(gets)), \
                mock.patch.object(hao, "cmd_wait",
                                  return_value={"status": "done"}):
            rc, _out, err = run_cli(
                ["ask", "w2:p9", "task", "--mode", "lifecycle", "--wait",
                 "--json"], {"HAO_STATE_DIR": self.state})
        self.assertEqual(rc, 0, err)
        self.assertEqual(len(gets), 1, gets)

    def test_first_herdr_failure_stops_resolve(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(hao, "run_herdr",
                                  return_value=(8, "", "herdr unavailable")):
            for cmd in (["name", "verse", "hawk"],
                        ["clear", "verse"],
                        ["stop", "verse"],
                        ["ask", "verse", "task"],
                        ["status", "verse"]):
                with self.subTest(cmd=cmd):
                    os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
                    try:
                        rc = hao.main(cmd)
                    finally:
                        os.environ.pop("HAO_STATE_DIR", None)
                    self.assertEqual(rc, 8)
                    self.assertFalse(os.path.exists(
                        os.path.join(d, "hao", "tasks")))

    def test_cancel_stops_before_ledger_write_on_herdr_failure(self):
        os.environ["HAO_STATE_DIR"] = self.state
        try:
            Ledger().write_running("abcd12345678", target="w2:p9")
            with mock.patch.object(hao, "run_herdr",
                                   return_value=(8, "", "herdr unavailable")):
                rc = hao.cmd_cancel("abcd12345678")
            self.assertEqual(rc, 8)
            self.assertEqual(Ledger().get("abcd12345678")["status"], "running")
        finally:
            os.environ.pop("HAO_STATE_DIR", None)


class TestR15SingleAgentGet(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "hao", "tasks")
        os.environ["HAO_STATE_DIR"] = self.state
        self.sid = "deadbeef0000"

    def tearDown(self):
        os.environ.pop("HAO_STATE_DIR", None)
        self.tmp.cleanup()

    def _stub(self, events):
        def stub(args, machine=None):
            if args[:2] == ["agent", "get"]:
                events.append("get")
                return 0, json.dumps({"result": {"agent": {
                    "agent_status": "idle", "state_change_seq": 0}}}), ""
            if args[:2] == ["agent", "wait"]:
                events.append("wait")
                return 0, "{}", ""
            if args[:2] == ["pane", "read"]:
                events.append("read")
                return 0, json.dumps({"result": {"read": {"text": ""}}}), ""
            return 0, "{}", ""
        return stub

    def _assert_no_double_get(self, events):
        gets = [i for i, e in enumerate(events) if e == "get"]
        self.assertFalse(any(events[i + 1] == "get" for i in gets
                             if i + 1 < len(events)), events)
        self.assertLessEqual(len(gets) - events.count("read"), 1, events)

    def test_sentinel_round_does_one_agent_get(self):
        events = []
        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._stub(events)), \
                mock.patch.object(hao, "FAST_PATH_SECONDS", 0), \
                mock.patch.object(hao.time, "sleep", return_value=None), \
                _alarm(8):
            rc = hao.cmd_wait("w2:p9", self.sid, 0.05)
        self.assertEqual(rc, 4)
        self._assert_no_double_get(events)

    def test_lifecycle_round_does_one_agent_get(self):
        events = []
        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._stub(events)), \
                mock.patch.object(hao, "_sentinel_check",
                                  return_value=(None, None)), \
                mock.patch.object(hao, "_sentinel_scan_tail",
                                  return_value=(None, None)), \
                mock.patch.object(hao.time, "sleep", return_value=None), \
                _alarm(8):
            rc = hao._wait_lifecycle("w2:p9", self.sid, "deadbeef00000000",
                                     0.05, None, False, False)
        self.assertEqual(rc, 4)
        self.assertFalse(any(events[i] == "get" and events[i + 1] == "get"
                             for i in range(len(events) - 1)), events)

    def test_file_round_does_one_agent_get(self):
        events = []
        with mock.patch.object(hao, "run_herdr",
                               side_effect=self._stub(events)), \
                mock.patch.object(hao.time, "sleep",
                                  side_effect=lambda *a: events.append("sleep")), \
                _alarm(8):
            rc = hao._wait_file("w2:p9", self.sid, "deadbeef00000000",
                                0.05, None)
        self.assertEqual(rc, 4)
        self.assertFalse(any(events[i] == "get" and events[i + 1] == "get"
                             for i in range(len(events) - 1)), events)


class TestR14StatusNotFound(unittest.TestCase):
    def test_query_failure_is_8(self):
        def stub(args, machine=None):
            return 1, "", "herdr connection failed"
        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc = hao.cmd_status("w2:pX")
        self.assertEqual(rc, 8)

    def test_genuine_not_found_is_3(self):
        def stub(args, machine=None):
            return 1, "", '{"error":{"code":"agent_not_found"}}'
        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc = hao.cmd_status("w2:pX")
        self.assertEqual(rc, 3)


if __name__ == "__main__":
    unittest.main()
