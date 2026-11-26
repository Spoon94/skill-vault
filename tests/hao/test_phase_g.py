import json
import os
import sys
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


class TestG1HaoCommand(unittest.TestCase):
    def test_prompt_uses_executable_command(self):
        token = "hao-" + "aabbccddeeff0011"
        prompt = hao.build_prompt("task", token)
        cmd = hao.hao_command()
        self.assertIn(f"{cmd} done --token <完整令牌>", prompt)
        self.assertIn("若无法执行该命令", prompt)
        self.assertNotIn(token, prompt)

    def test_command_has_script_path(self):
        cmd = hao.hao_command()
        self.assertIn(sys.executable or "python3", cmd)
        self.assertIn("scripts/hao", cmd)


class TestG3Decorations(unittest.TestCase):
    def test_pi_style_sentinels(self):
        tok = "hao-" + "aabbccddeeff0011"
        cases = [
            f"  HAO_DONE {tok} ┃",
            f"  HAO_DONE {tok} │",
            f"│ HAO_DONE {tok} │",
            f"● HAO_DONE {tok}",
            f"HAO_DONE {tok} ┃ ✓",
            f"└ HAO_DONE {tok} ┘",
        ]
        for line in cases:
            self.assertIsNotNone(hao.SENTINEL_RE.match(line), line)

    def test_prefix_line_accepts_box_chars(self):
        self.assertIsNotNone(hao._PREFIX_LINE_RE.match("┃ HAO_DONE hao-0011 ┃"))


class TestG4WaitGuidance(unittest.TestCase):
    def test_unknown_agent_hint(self):
        def stub(args, machine=None):
            return 0, json.dumps({"result": {"agent": {
                "agent_status": "unknown"}}}), ""
        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc = hao._agent_gate("w2:p9", None, False, False)
        self.assertEqual(rc, 9)
        self.assertIn("--accept-unknown", hao._ERROR_DETAIL)
        hao._ERROR_DETAIL = None

    def test_no_agent_hint(self):
        with mock.patch.object(hao, "run_herdr",
                               return_value=(1, "", '{"error":{"code":"agent_not_found"}}')):
            rc = hao._agent_gate("w2:p9", None, False, False)
        self.assertEqual(rc, 3)
        self.assertIn("--no-agent", hao._ERROR_DETAIL)
        hao._ERROR_DETAIL = None


if __name__ == "__main__":
    unittest.main()
