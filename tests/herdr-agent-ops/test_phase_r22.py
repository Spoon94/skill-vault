import os
import re
import sys
import types
import unittest
from importlib.machinery import SourceFileLoader

HERE = os.path.dirname(__file__)
SKILL = os.path.join(HERE, "..", "..", "herdr-agent-ops")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
_loader = SourceFileLoader("hao", os.path.join(SKILL, "scripts", "hao"))
hao = types.ModuleType("hao")
_loader.exec_module(hao)
from hao_test_guard import install_offline_guard  # noqa: E402
install_offline_guard(hao)
from ledger import Ledger  # noqa: E402

TOKEN = "hao-" + "aabbccddeeff0011"
SID = TOKEN[4:16]


def echo_prompt(prompt, width=18):
    out = []
    for line in prompt.splitlines():
        for i in range(0, len(line), width):
            out.append("│ " + line[i:i + width] + " │")
    return out


def clean(text):
    return re.sub(r"\s+", "", text)


class TestR22PromptBoundary(unittest.TestCase):
    def _assert_answer(self, text_only, answer):
        prompt = hao.build_prompt("task body", TOKEN, text_only=text_only)
        lines = echo_prompt(prompt)
        lines += ["│ " + line + " │" for line in answer]
        lines.append("│ HAO_DONE " + TOKEN + " │")
        text = "\n".join(lines)
        tail = hao._tail_from_pane_text(text, TOKEN, SID, prompt=prompt)
        self.assertEqual(tail, "\n".join(answer))
        protocol = "以下完成上报是协议步骤"
        self.assertIn(protocol, prompt)
        self.assertNotIn(clean(protocol), clean(tail))

    def test_default_prompt_wrapped_and_decorated(self):
        self._assert_answer(False, ["answer line one", "answer line two"])

    def test_text_only_prompt_wrapped_and_decorated(self):
        self._assert_answer(True, ["answer line one", "answer line two"])

    def test_prompt_scrolled_out_falls_back(self):
        text = "\n".join([
            "old task echo",
            "--- 任务结束 ---",
            "以下完成上报是协议步骤",
            "Thought for 2s",
            "---",
            ">",
            "answer one",
            "answer two",
            "HAO_DONE " + TOKEN,
        ])
        prompt = hao.build_prompt("task body", TOKEN)
        tail = hao._tail_from_pane_text(text, TOKEN, SID, prompt=prompt)
        self.assertEqual(tail, "answer one\nanswer two")

    def test_prompt_boundary_still_respects_limits(self):
        prompt = hao.build_prompt("task body", TOKEN)
        answer = [f"line {i}" for i in range(60)]
        text = "\n".join(echo_prompt(prompt) + answer +
                         ["HAO_DONE " + TOKEN])
        tail = hao._tail_from_pane_text(text, TOKEN, SID, prompt=prompt)
        self.assertLessEqual(len(tail.splitlines()), 40)
        self.assertLessEqual(len(tail), 2000)

    def test_wait_reads_prompt_from_ledger(self):
        import tempfile
        from unittest import mock

        prompt = hao.build_prompt("task body", TOKEN)
        lines = echo_prompt(prompt) + ["│ answer from peer │",
                                       "│ HAO_DONE " + TOKEN + " │"]
        text = "\n".join(lines)

        def stub(args, machine=None):
            if args[:2] == ["agent", "get"]:
                return 0, '{"result":{"agent":{"agent_status":"blocked"}}}', ""
            if args[:2] == ["pane", "read"]:
                from json import dumps
                return 0, dumps({"result": {"read": {"text": text}}}), ""
            return 0, "{}", ""
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                Ledger().write_running(SID, target="w2:p9", prompt=prompt)
                with mock.patch.object(hao, "run_herdr", side_effect=stub):
                    result = hao.cmd_wait("w2:p9", TOKEN, 1)
            finally:
                os.environ.pop("HAO_STATE_DIR", None)
        self.assertEqual(result["tail"], "answer from peer")

    def test_protocol_echo_absent_even_with_ansi(self):
        prompt = hao.build_prompt("task body", TOKEN)
        decorated = [("\x1b[2m│ " + line + " │\x1b[0m")
                     for line in echo_prompt(prompt)]
        text = "\n".join(decorated + ["│ answer │",
                                      "│ HAO_DONE " + TOKEN + " │"])
        tail = hao._tail_from_pane_text(text, TOKEN, SID, prompt=prompt)
        self.assertEqual(tail, "answer")
        self.assertNotIn(clean("完成时，将令牌"), clean(tail))


if __name__ == "__main__":
    unittest.main()
