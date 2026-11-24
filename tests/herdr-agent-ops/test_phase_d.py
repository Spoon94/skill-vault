import contextlib
import io
import json
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
from hao_test_guard import install_offline_guard  # noqa: E402
install_offline_guard(hao)
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
        self.assertIn("--summary", prompt)
        self.assertIn("结果载荷", prompt)
        self.assertIn("≤600", prompt)
        self.assertNotIn(token, prompt)


class TestD4Summary(unittest.TestCase):
    def test_done_summary_is_returned_by_wait(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                sid = "abcd12345678"
                token = "hao-" + sid + "9900"
                Ledger().write_running(sid, token=token, target="w2:p9")
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(hao.cmd_done(token, "answer body"), 0)
                result = hao.cmd_wait("w2:p9", token, 1)
                self.assertEqual(result["status"], "done")
                self.assertEqual(result["summary"], "answer body")
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_done_summary_roundtrip_via_cli(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                sid = "abcd12345678"
                token = "hao-" + sid + "9900"
                Ledger().write_running(sid, token=token, target="w2:p9")
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(hao.main(["done", token, "--summary", "cli body"]), 0)
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertEqual(hao.main(["wait", "w2:p9", token]), 0)
                result = json.loads(out.getvalue().strip().splitlines()[-1])
                self.assertEqual(result["summary"], "cli body")
            finally:
                os.environ.pop("HAO_STATE_DIR", None)


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
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                self.assertIsNone(Ledger().heartbeat("deadbeef0000"))
                self.assertIsNone(Ledger().get("deadbeef0000"))
                files = os.listdir(os.path.join(d, "hao", "tasks")) if os.path.isdir(
                    os.path.join(d, "hao", "tasks")) else []
                self.assertFalse([f for f in files if f.endswith(".json")])
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_wait_round_does_not_create_stub(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                self.assertEqual(hao._wait_round_rec(Ledger(), "deadbeef0000"), {})
                self.assertIsNone(Ledger().get("deadbeef0000"))
            finally:
                os.environ.pop("HAO_STATE_DIR", None)


if __name__ == "__main__":
    unittest.main()
