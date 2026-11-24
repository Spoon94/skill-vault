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
SKILL = os.path.join(HERE, "..", "..", "herdr-agent-ops")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
_loader = SourceFileLoader("hao", os.path.join(SKILL, "scripts", "hao"))
hao = types.ModuleType("hao")
_loader.exec_module(hao)
from hao_test_guard import install_offline_guard  # noqa: E402
install_offline_guard(hao)

TOKEN = "hao-" + "aabbccddeeff0011"


def run_cli(argv, env=None):
    out, err = io.StringIO(), io.StringIO()
    saved = {k: os.environ.get(k) for k in ("HAO_STATE_DIR",)}
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
    return rc, out.getvalue(), err.getvalue()


class TestR21TextOnly(unittest.TestCase):
    def test_text_only_prompt_has_no_done_command(self):
        prompt = hao.build_prompt("task", TOKEN, text_only=True)
        self.assertNotIn("done --token", prompt)
        self.assertNotIn("hao done", prompt)
        self.assertIn("HAO_DONE", prompt)
        self.assertIn("不要调用任何命令", prompt)

    def test_text_only_flag_parses(self):
        a = hao.build_parser().parse_args(
            ["ask", "w2:p9", "task", "--text-only"])
        self.assertTrue(a.text_only)

    def test_tail_drops_before_last_delimiter_and_noise(self):
        text = "\n".join([
            "old prompt line",
            "--- 任务结束 ---",
            "protocol echo before last delimiter",
            "--- 任务结束 ---",
            "以下完成上报是协议步骤",
            "完成时，将令牌",
            "Thought for 3s",
            "✻ Worked for 2m",
            "Update available",
            "────────",
            ">",
            "answer line 1",
            "answer line 2",
            "HAO_DONE " + TOKEN,
        ])
        self.assertEqual(hao._tail_from_pane_text(text, TOKEN, TOKEN[4:16]),
                         "answer line 1\nanswer line 2")

    def test_tail_limits_still_apply(self):
        text = "\n".join([f"answer {i}" for i in range(60)] +
                         ["HAO_DONE " + TOKEN])
        tail = hao._tail_from_pane_text(text, TOKEN, TOKEN[4:16])
        self.assertLessEqual(len(tail.splitlines()), 40)
        self.assertLessEqual(len(tail), 2000)

    def test_blocked_without_sentinel_hints_text_only(self):
        def stub(args, machine=None):
            if args[:2] == ["agent", "get"]:
                return 0, json.dumps({"result": {"agent": {
                    "agent_status": "blocked"}}}), ""
            if args[:2] == ["pane", "read"]:
                return 0, json.dumps({"result": {"read": {
                    "text": "no sentinel here"}}}), ""
            return 0, "{}", ""
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc, out, err = run_cli(
                ["wait", "w2:p9", TOKEN, "--json"],
                {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
        self.assertEqual(rc, 5)
        self.assertIn("--text-only", err)
        self.assertEqual(json.loads(out)["exit"], 5)


if __name__ == "__main__":
    unittest.main()
