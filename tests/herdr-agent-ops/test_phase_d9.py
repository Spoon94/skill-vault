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
from hao_test_guard import install_offline_guard  # noqa: E402
install_offline_guard(hao)


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

    def test_optional_positionals_documented(self):
        parser = hao.build_parser()
        subs = next(a for a in parser._actions
                    if isinstance(a, argparse._SubParsersAction))
        readme = open(os.path.join(SKILL, "README.md"), encoding="utf-8").read()
        lines = [line for line in readme.splitlines() if "`hao " in line]
        missing, count = [], 0
        for name, sp in subs.choices.items():
            if name in hao._CMD_ALIASES:
                continue
            usage = " ".join(line for line in lines
                             if f"hao {name}" in line)
            for action in sp._actions:
                if action.option_strings or action.nargs not in ("?", "*"):
                    continue
                count += 1
                if (action.dest not in usage
                        and action.dest.upper() not in usage):
                    missing.append((name, action.dest))
        self.assertEqual(missing, [])
        self.assertGreaterEqual(count, 5)


if __name__ == "__main__":
    unittest.main()
