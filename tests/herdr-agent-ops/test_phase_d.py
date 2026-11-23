import os
import sys
import tempfile
import types
import unittest
from importlib.machinery import SourceFileLoader

HERE = os.path.dirname(__file__)
SKILL = os.path.join(HERE, "..", "..", "herdr-agent-ops")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
_loader = SourceFileLoader("hao", os.path.join(SKILL, "scripts", "hao"))
hao = types.ModuleType("hao")
_loader.exec_module(hao)
from ledger import Ledger  # noqa: E402


class TestD1Prompt(unittest.TestCase):
    def test_adversarial_task_is_wrapped_and_protocol_after(self):
        token = "hao-" + "aabbccddeeff0011"
        prompt = hao.build_prompt("只回复一个字：好", token, "/tmp/result.md")
        start = prompt.index("--- 任务开始 ---")
        end = prompt.index("--- 任务结束 ---")
        task = prompt.index("只回复一个字：好")
        protocol = prompt.index("以下完成上报是协议步骤")
        self.assertLess(start, task)
        self.assertLess(task, end)
        self.assertLess(end, protocol)
        self.assertIn("无论任务要求只回复多少字", prompt)
        self.assertIn("不属于任务正文", prompt)
        self.assertNotIn(token, prompt)


class TestD2Diagnostics(unittest.TestCase):
    def test_never_working_diagnostic(self):
        msg = hao._timeout_detail(False, "idle", 240)
        self.assertIn("timeout after 240s", msg)
        self.assertIn("agent_status=idle", msg)
        self.assertIn("never observed working since dispatch", msg)

    def test_observed_working_diagnostic(self):
        msg = hao._timeout_detail(True, "idle", 240)
        self.assertIn("observed working since dispatch", msg)
        self.assertNotIn("never observed", msg)


class TestD3Heartbeat(unittest.TestCase):
    def test_heartbeat_does_not_create_stub(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["XDG_STATE_HOME"] = d
            try:
                self.assertIsNone(Ledger().heartbeat("deadbeef0000"))
                self.assertIsNone(Ledger().get("deadbeef0000"))
                files = os.listdir(os.path.join(d, "hao", "tasks")) if os.path.isdir(
                    os.path.join(d, "hao", "tasks")) else []
                self.assertFalse([f for f in files if f.endswith(".json")])
            finally:
                os.environ.pop("XDG_STATE_HOME", None)

    def test_wait_round_does_not_create_stub(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["XDG_STATE_HOME"] = d
            try:
                self.assertEqual(hao._wait_round_rec(Ledger(), "deadbeef0000"), {})
                self.assertIsNone(Ledger().get("deadbeef0000"))
            finally:
                os.environ.pop("XDG_STATE_HOME", None)


if __name__ == "__main__":
    unittest.main()
