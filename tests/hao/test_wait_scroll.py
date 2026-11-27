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

TOKEN = "hao-" + "aabbccdd" + "eeff0011"
SID = TOKEN[4:16]
HERDR_TIMEOUT_JSON = ('{"error":{"code":"timeout",'
                      '"message":"timed out waiting for agent status"}}')
NO_MATCH = '{"error":{"code":"timeout","message":"no match"}}'


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def time(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


class WaitScrollCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "hao", "tasks")
        self.env = mock.patch.dict(os.environ,
                                   {"HAO_STATE_DIR": self.state})
        self.env.start()
        self.clock = FakeClock()
        self.led = Ledger()
        self.led.write_running(SID, token=TOKEN, target="w2:p9",
                               prompt="task")

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def _stub(self, status, wait_output=None, read_text="",
              advance=2.0):
        calls = {"get": 0, "agent_wait": 0, "wait_output": 0,
                 "read": 0, "wait_output_times": [], "sleeps": []}
        clock = self.clock

        def fake(args, machine=None):
            if args[:2] == ["agent", "get"]:
                calls["get"] += 1
                return 0, json.dumps({"result": {"agent": {
                    "agent_status": status,
                    "state_change_seq": 1}}}), ""
            if args[:2] == ["agent", "wait"]:
                calls["agent_wait"] += 1
                clock.t += advance
                return 1, "", HERDR_TIMEOUT_JSON
            if args[:2] == ["pane", "wait-output"]:
                calls["wait_output"] += 1
                calls["wait_output_times"].append(clock.t)
                if wait_output is None:
                    return 1, "", NO_MATCH
                return 0, json.dumps({"result": {
                    "matched_line": wait_output}}), ""
            if args[:2] == ["pane", "read"]:
                calls["read"] += 1
                return 0, json.dumps({"result": {"read": {
                    "text": read_text}}}), ""
            return 0, '{"result":{}}', ""
        return fake, calls

    def _run_wait(self, status, timeout, fast_seconds=30,
                  wait_output=None, read_text="", mode="sentinel",
                  advance=2.0):
        fake, calls = self._stub(status, wait_output=wait_output,
                                 read_text=read_text, advance=advance)
        calls["start"] = self.clock.t
        orig_sleep = self.clock.sleep

        def sleep(seconds):
            calls["sleeps"].append(seconds)
            orig_sleep(seconds)
        with mock.patch.object(hao, "run_herdr", side_effect=fake), \
                mock.patch.object(hao, "FAST_PATH_SECONDS", fast_seconds), \
                mock.patch.object(hao.time, "time", self.clock.time), \
                mock.patch.object(hao.time, "sleep", sleep):
            result = hao.cmd_wait("w2:p9", TOKEN, timeout, mode=mode)
        return result, calls


class TestWorkingFastPath(WaitScrollCase):
    def test_working_does_not_read_pane_before_the_scan_interval(self):
        result, calls = self._run_wait("working", timeout=8)
        self.assertEqual(result, 4)
        self.assertEqual(calls["wait_output"], 0)
        self.assertEqual(calls["read"], 0)
        self.assertGreaterEqual(calls["agent_wait"], 3)

    def test_working_scans_once_per_interval(self):
        result, calls = self._run_wait("working", timeout=12)
        self.assertEqual(result, 4)
        self.assertEqual(calls["wait_output"], 1)
        self.assertGreaterEqual(
            calls["wait_output_times"][0] - calls["start"], 10)


class TestNonWorkingFastPath(WaitScrollCase):
    def test_idle_still_scans_and_completes_immediately(self):
        result, calls = self._run_wait(
            "idle", timeout=10,
            wait_output=f"HAO_DONE {TOKEN}",
            read_text=f"HAO_DONE {TOKEN}")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["status"], "done")
        self.assertEqual(calls["wait_output"], 1)
        self.assertEqual(calls["agent_wait"], 0)


class TestSettledBackstop(WaitScrollCase):
    def test_settled_backstop_sleeps_two_seconds(self):
        result, calls = self._run_wait("idle", timeout=1,
                                       fast_seconds=0, advance=0)
        self.assertEqual(result, 4)
        self.assertIn(2, calls["sleeps"])
        self.assertNotIn(0.5, calls["sleeps"])


if __name__ == "__main__":
    unittest.main()
