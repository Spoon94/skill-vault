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

SID = "abcd12345678"
TOKEN = "hao-" + SID + "0000"


class TestReplyPayload(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "hao", "tasks")
        self.env = mock.patch.dict(os.environ,
                                   {"HAO_STATE_DIR": self.state})
        self.env.start()
        self.led = Ledger()
        self.rp = os.path.join(self.state, SID, "result.md")

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def _write_result(self, body):
        os.makedirs(os.path.dirname(self.rp), exist_ok=True)
        with open(self.rp, "w") as f:
            f.write(body)

    def _wait(self, payload):
        with mock.patch.object(hao, "_wait_sentinel",
                               return_value=payload):
            return hao.cmd_wait("w2:p9", SID, 1)

    def test_summary_wins_and_result_file_is_removed(self):
        self._write_result("file answer")
        self.led.write_done(SID, summary="ledger answer",
                            result_path=self.rp)
        result = self._wait({"status": "done", "summary": "ledger answer",
                             "result_path": self.rp})
        self.assertEqual(result["summary"], "ledger answer")
        self.assertNotIn("tail", result)
        self.assertFalse(os.path.exists(self.rp))
        self.assertFalse(os.path.exists(os.path.join(self.state,
                                                     SID + ".json")))

    def test_result_file_fills_tail_when_no_summary(self):
        self._write_result("file answer")
        self.led.write_done(SID, result_path=self.rp)
        result = self._wait({"status": "done", "result_path": self.rp})
        self.assertEqual(result["tail"], "file answer")
        self.assertTrue(result["result_consumed"])
        self.assertEqual(result["result_path"], self.rp)
        self.assertFalse(os.path.exists(self.rp))
        self.assertFalse(os.path.exists(os.path.join(self.state,
                                                     SID + ".json")))

    def test_tail_is_kept_when_there_is_no_file(self):
        self.led.write_running(SID, token=TOKEN, target="w2:p9")
        result = self._wait({"status": "done", "tail": "screen answer"})
        self.assertEqual(result["tail"], "screen answer")
        self.assertFalse(os.path.exists(os.path.join(self.state,
                                                     SID + ".json")))
        self.assertFalse(os.path.exists(self.state))

    def test_unreadable_result_file_sets_tail_note_and_keeps_it(self):
        self._write_result("file answer")
        result = {"status": "done", "result_path": self.rp}
        with mock.patch.object(hao, "safe_read", return_value=None):
            consume = hao._reply_payload(result, SID)
        self.assertFalse(consume)
        self.assertEqual(
            result["tail_note"],
            "result file unreadable; left in place for hao result")
        self.assertNotIn("result_consumed", result)
        self.assertTrue(os.path.exists(self.rp))

    def test_finish_done_keeps_tail_for_done_without_summary(self):
        self.led.write_done(SID)
        out = hao._finish_done(self.led, SID, "HAO_DONE line",
                               tail="screen answer")
        self.assertEqual(out["tail"], "screen answer")

    def test_finish_sentinel_skips_tail_when_summary_exists(self):
        self.led.write_done(SID, summary="ledger answer")
        with mock.patch.object(
                hao, "_completion_tail",
                return_value=("screen answer", "screen answer", None)) as ct:
            out = hao._finish_sentinel(self.led, SID, "HAO_DONE line",
                                       "w2:p9", TOKEN, None)
        ct.assert_not_called()
        self.assertEqual(out["status"], "done")
        self.assertNotIn("tail", out)


if __name__ == "__main__":
    unittest.main()
