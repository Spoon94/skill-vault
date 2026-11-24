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
        env = dict(self.env, SHIM_SLEEP=sleep_mode)
        with _alarm(8), mock.patch.object(hao, "_herdr_timeout",
                                          return_value=0.2):
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

    def test_timeout_limits(self):
        self.assertEqual(hao._herdr_timeout(["agent", "prompt", "p"]), 30)
        self.assertEqual(hao._herdr_timeout(["pane", "wait-output", "p",
                                             "--timeout", "1000"]), 6)
        self.assertEqual(hao._herdr_timeout(["agent", "wait", "p",
                                             "--timeout", "8000"]), 13)
        self.assertEqual(hao._herdr_timeout(["agent", "get", "p"]), 20)


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
