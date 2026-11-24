import json
import os
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
from hao_test_guard import install_offline_guard  # noqa: E402
install_offline_guard(hao)


TOKEN = "hao-" + "aabbccddeeff0011"


class TestR20SentinelTail(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["HAO_STATE_DIR"] = os.path.join(self.tmp.name,
                                                   "hao", "tasks")

    def tearDown(self):
        os.environ.pop("HAO_STATE_DIR", None)
        self.tmp.cleanup()

    def test_blocked_gate_rescan_completes_with_tail(self):
        pane_text = "\n".join([
            "│ first answer line │",
            "│ second answer line │",
            "│ HAO_DONE " + TOKEN + " │",
        ])

        def stub(args, machine=None):
            if args[:2] == ["agent", "get"]:
                return 0, json.dumps({"result": {"agent": {
                    "agent_status": "blocked"}}}), ""
            if args[:2] == ["pane", "read"]:
                return 0, json.dumps({"result": {"read": {
                    "text": pane_text}}}), ""
            return 0, "{}", ""

        with mock.patch.object(hao, "run_herdr", side_effect=stub), \
                mock.patch.object(hao.time, "sleep", return_value=None):
            result = hao.cmd_wait("w2:p9", TOKEN, 1)
        self.assertEqual(result["status"], "done")
        self.assertEqual(result["tail"],
                         "first answer line\nsecond answer line")
        self.assertNotIn("summary", result)

    def test_tail_caps_lines_and_chars(self):
        lines = [f"line {i}" for i in range(60)]
        lines[-1] = "z" * 5000
        text = "\n".join(lines + ["HAO_DONE " + TOKEN])
        tail = hao._tail_from_pane_text(text, TOKEN, TOKEN[4:16])
        self.assertLessEqual(len(tail.splitlines()), 40)
        self.assertLessEqual(len(tail), 2000)

    def test_narrow_box_tail_is_readable(self):
        text = "\n".join([
            "│ answer one │",
            "│ answer two │",
            "│ HAO_DONE " + TOKEN + " │",
        ])
        tail = hao._tail_from_pane_text(text, TOKEN, TOKEN[4:16])
        self.assertEqual(tail, "answer one\nanswer two")

    def test_prompt_prints_sentinel_before_done(self):
        prompt = hao.build_prompt("task", TOKEN)
        self.assertLess(prompt.index("最后一行打印备份信号"),
                        prompt.index("done --token"))
        self.assertIn("不要请求审批", prompt)
        self.assertIn("直接只打印备份信号", prompt)


if __name__ == "__main__":
    unittest.main()
