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
from ledger import Ledger  # noqa: E402


class TestD7Wake(unittest.TestCase):
    def test_wake_template_is_self_describing_without_summary(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["XDG_STATE_HOME"] = d
            try:
                sid = "abcd12345678"
                token = "hao-" + sid + "9900"
                target = "w2:p9"
                caller = "w2:p1"
                Ledger().write_running(sid, token=token, target=target,
                                       wake=caller)
                calls = []

                def stub(args, machine=None):
                    calls.append(args)
                    return 0, "{}", ""

                out = io.StringIO()
                with mock.patch.object(hao, "run_herdr", side_effect=stub), \
                        contextlib.redirect_stdout(out):
                    rc = hao.main(["done", token, "--summary", "private answer"])
                self.assertEqual(rc, 0)
                prompt = next(c[3] for c in calls if c[:2] == ["agent", "prompt"])
                expected = (f"[HAO_WAKE] {sid} done — run: {hao.hao_command()} wait {target} "
                            f"--token {sid}")
                self.assertEqual(prompt, expected)
                self.assertNotIn("private answer", prompt)
            finally:
                os.environ.pop("XDG_STATE_HOME", None)


if __name__ == "__main__":
    unittest.main()
