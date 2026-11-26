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
PLAIN_TIMEOUT = "timed out after 20s: herdr agent wait w2:p9"


class WaitCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "hao", "tasks")
        self.env = mock.patch.dict(os.environ,
                                   {"HAO_STATE_DIR": self.state})
        self.env.start()
        self.led = Ledger()
        self.led.write_running(SID, token=TOKEN, target="w2:p9",
                               prompt="task")

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def _stub(self, wait_stderr, done_after=None):
        calls = {"wait": 0, "get": 0}

        def fake(args, machine=None):
            if args[:2] == ["agent", "get"]:
                calls["get"] += 1
                return 0, json.dumps({"result": {"agent": {
                    "agent_status": "working",
                    "state_change_seq": 1}}}), ""
            if args[:2] == ["agent", "wait"]:
                calls["wait"] += 1
                if done_after is not None and calls["wait"] >= done_after:
                    self.led.write_done(SID, summary="finished")
                return 1, "", wait_stderr
            if args[:2] == ["pane", "wait-output"]:
                return 1, "", '{"error":{"code":"timeout",' \
                              '"message":"no match"}}'
            if args[:2] == ["pane", "read"]:
                return 0, '{"result":{"read":{"text":""}}}', ""
            return 0, '{"result":{}}', ""
        return fake, calls

    def _wait(self, mode, wait_stderr, done_after=None):
        fake, calls = self._stub(wait_stderr, done_after)
        with mock.patch.object(hao, "run_herdr", side_effect=fake), \
                mock.patch.object(hao, "FAST_PATH_SECONDS", 0), \
                mock.patch.object(hao.time, "sleep", lambda *_: None):
            result = hao.cmd_wait("w2:p9", TOKEN, 5, mode=mode)
        return result, calls


class TestAWaitsSurviveHerdrTimeout(WaitCase):
    def test_sentinel_keeps_waiting_when_herdr_wait_times_out(self):
        result, calls = self._wait("sentinel", HERDR_TIMEOUT_JSON,
                                   done_after=3)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["status"], "done")
        self.assertGreaterEqual(calls["wait"], 3)

    def test_lifecycle_keeps_waiting_when_herdr_wait_times_out(self):
        result, calls = self._wait("lifecycle", HERDR_TIMEOUT_JSON,
                                   done_after=3)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["status"], "done")
        self.assertGreaterEqual(calls["wait"], 3)

    def test_sentinel_plain_timeout_still_exits_8(self):
        result, calls = self._wait("sentinel", PLAIN_TIMEOUT)
        self.assertEqual(result, 8)
        self.assertEqual(calls["wait"], 1)

    def test_lifecycle_plain_timeout_still_exits_8(self):
        result, calls = self._wait("lifecycle", PLAIN_TIMEOUT)
        self.assertEqual(result, 8)
        self.assertEqual(calls["wait"], 1)


if __name__ == "__main__":
    unittest.main()
