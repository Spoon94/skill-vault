import unittest
import os
import types
from importlib.machinery import SourceFileLoader

_loader = SourceFileLoader("hao", os.path.join(os.path.dirname(__file__), "..", "..", "herdr-agent-ops", "scripts", "hao"))
hao = types.ModuleType(_loader.name)
_loader.exec_module(hao)

build_prompt = hao.build_prompt
SENTINEL_RE = hao.SENTINEL_RE


class TestWait(unittest.TestCase):
    def test_no_full_token_in_prompt(self):
        p = build_prompt("do X", "hao-abc123def456")
        self.assertNotIn("hao-abc123def456", p.replace("\n", ""))

    def test_regex_indent(self):
        self.assertIsNotNone(SENTINEL_RE.match("  HAO_DONE hao-abc123def456"))
        self.assertIsNotNone(SENTINEL_RE.match("⏺ HAO_DONE hao-abc123def456"))
        self.assertIsNotNone(SENTINEL_RE.match("> HAO_DONE hao-abc123def456"))
        self.assertIsNotNone(SENTINEL_RE.match("`HAO_DONE hao-abc123def456`"))

    def test_regex_not_token_only(self):
        self.assertIsNone(SENTINEL_RE.match("thinking about hao-abc123def456"))
        self.assertIsNone(SENTINEL_RE.match("HAO_DONE other-token"))

    def test_regex_bold_colon(self):
        self.assertIsNotNone(SENTINEL_RE.match("**HAO_DONE hao-abc123def456**"))
        self.assertIsNotNone(SENTINEL_RE.match("HAO_DONE: hao-abc123def456"))


if __name__ == "__main__":
    unittest.main()
