import argparse
import os
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


class TestD9DocDrift(unittest.TestCase):
    def test_every_public_option_is_documented(self):
        parser = hao.build_parser()
        subs = next(a for a in parser._actions
                    if isinstance(a, argparse._SubParsersAction))
        opts = sorted({s for sp in subs.choices.values()
                       for action in sp._actions
                       for s in action.option_strings if s.startswith("--")})
        readme = open(os.path.join(SKILL, "README.md"), encoding="utf-8").read()
        missing = [opt for opt in opts if opt not in readme]
        self.assertEqual(missing, [])
        self.assertGreaterEqual(len(opts), 30)


if __name__ == "__main__":
    unittest.main()
