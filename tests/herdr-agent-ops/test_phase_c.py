import contextlib
import io
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


class TestC3Startup(unittest.TestCase):
    def test_non_suggest_does_not_load_names_or_argparse(self):
        self.assertNotIn("argparse", hao.__dict__)
        hao.__file__ = os.path.join(SKILL, "scripts", "hao")
        calls = []
        original = hao._load_module

        def record(name, filename):
            calls.append(name)
            return original(name, filename)

        with tempfile.TemporaryDirectory() as d:
            saved = os.environ.get("HAO_STATE_DIR")
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            err = io.StringIO()
            try:
                with mock.patch.object(hao, "_load_module", side_effect=record), \
                        contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                    try:
                        hao.main(["cancel", "deadbeef0000"])
                    except SystemExit:
                        pass
            finally:
                hao._ERROR_DETAIL = None
                hao._JSON_OUTPUT = False
                hao._JSON_HANDLED = False
                if saved is None:
                    os.environ.pop("HAO_STATE_DIR", None)
                else:
                    os.environ["HAO_STATE_DIR"] = saved
        self.assertNotIn("names", calls)


if __name__ == "__main__":
    unittest.main()
