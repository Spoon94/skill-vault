import unittest
import os
import types
from importlib.machinery import SourceFileLoader

_loader = SourceFileLoader("hao", os.path.join(os.path.dirname(__file__), "..", "scripts", "hao"))
hao = types.ModuleType(_loader.name)
_loader.exec_module(hao)

cmd_suggest = hao.cmd_suggest


class TestSuggest(unittest.TestCase):
    def test_cn_task(self):
        r = cmd_suggest("审查 PR 7", scope=None, json_out=True)
        self.assertEqual(r["group"], "验证审阅")
        self.assertEqual(len(r["candidates"]), 3)

    def test_reserved_excluded(self):
        r = cmd_suggest("wait output", scope=None, json_out=True)
        self.assertNotIn("wait", r["candidates"])

    def test_occupied_skipped(self):
        r = cmd_suggest("审查 PR 7", scope=None, json_out=True, live_names=["hawk"])
        self.assertNotIn("hawk", r["candidates"])

    def test_en_task(self):
        r = cmd_suggest("build a new adapter", scope=None, json_out=True)
        self.assertIn(r["group"], ["实现构建", "后端服务", "架构接口"])


if __name__ == "__main__":
    unittest.main()
