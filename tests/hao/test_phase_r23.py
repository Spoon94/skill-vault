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

TOKEN = "hao-" + "aabbccddeeff0011"
SID = TOKEN[4:16]


class TestR23ValidatedSentinel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["HAO_STATE_DIR"] = os.path.join(self.tmp.name,
                                                   "hao", "tasks")

    def tearDown(self):
        os.environ.pop("HAO_STATE_DIR", None)
        self.tmp.cleanup()

    def test_validated_sentinel_survives_unreadable_blocked_screen(self):
        state = {"gets": 0}
        line = "HAO_DONE " + TOKEN

        def stub(args, machine=None):
            if args[:2] == ["agent", "get"]:
                state["gets"] += 1
                status = "idle" if state["gets"] == 1 else "blocked"
                return 0, json.dumps({"result": {"agent": {
                    "agent_status": status}}}), ""
            if args[:2] == ["pane", "wait-output"]:
                return 0, json.dumps({"result": {
                    "matched_line": line}}), ""
            if args[:2] == ["pane", "read"]:
                return 0, json.dumps({"result": {"read": {
                    "text": "dialog covers the screen"}}}), ""
            return 0, "{}", ""
        with mock.patch.object(hao, "run_herdr", side_effect=stub), \
                mock.patch.object(hao.time, "sleep", return_value=None):
            result = hao.cmd_wait("w2:p9", TOKEN, 2)
        self.assertEqual(result["status"], "done")
        self.assertEqual(result["matched_line"], line)
        self.assertIsNone(result["tail"])
        self.assertIn("tail_note", result)
        self.assertIn("dialog may cover it", result["tail_note"])
        self.assertIsNone(result["last_line"])

    def test_last_line_after_noise_and_decorations(self):
        text = "\n".join([
            "Thought for 2s",
            "│ answer line │",
            "Update available",
            "HAO_DONE " + TOKEN,
        ])

        def stub(args, machine=None):
            if args[:2] == ["pane", "read"]:
                return 0, json.dumps({"result": {"read": {
                    "text": text}}}), ""
            return 0, "{}", ""
        hao._LAST_PANE_TEXT = None
        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            tail, last_line, note = hao._completion_tail(
                "w2:p9", TOKEN, SID, None)
        self.assertEqual(tail, "answer line")
        self.assertEqual(last_line, "answer line")
        self.assertIsNone(note)

    def test_last_line_null_when_no_usable_line(self):
        text = "\n".join(["Thought for 2s", "────────", ">",
                          "HAO_DONE " + TOKEN])

        def stub(args, machine=None):
            if args[:2] == ["pane", "read"]:
                return 0, json.dumps({"result": {"read": {
                    "text": text}}}), ""
            return 0, "{}", ""
        hao._LAST_PANE_TEXT = None
        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            tail, last_line, note = hao._completion_tail(
                "w2:p9", TOKEN, SID, None)
        self.assertEqual(tail, "")
        self.assertIsNone(last_line)
        self.assertIsNone(note)

    def test_no_sentinel_still_returns_blocked_hint(self):
        def stub(args, machine=None):
            if args[:2] == ["agent", "get"]:
                return 0, json.dumps({"result": {"agent": {
                    "agent_status": "blocked"}}}), ""
            if args[:2] == ["pane", "read"]:
                return 0, json.dumps({"result": {"read": {
                    "text": "no sentinel"}}}), ""
            return 0, "{}", ""
        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc = hao.cmd_wait("w2:p9", TOKEN, 1)
        self.assertEqual(rc, 5)
        self.assertIn("--text-only", hao._ERROR_DETAIL)
        hao._ERROR_DETAIL = None


if __name__ == "__main__":
    unittest.main()
