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
SKILL = os.path.join(HERE, "..", "..", "hao")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
_loader = SourceFileLoader("hao", os.path.join(SKILL, "scripts", "hao"))
hao = types.ModuleType("hao")
_loader.exec_module(hao)
from hao_test_guard import install_offline_guard  # noqa: E402
install_offline_guard(hao)
from ledger import Ledger, _path  # noqa: E402


def run_cli(argv, env=None):
    out, err = io.StringIO(), io.StringIO()
    saved = {k: os.environ.get(k) for k in ("HAO_STATE_DIR", "HERDR_PANE_ID")}
    if env:
        for key, value in env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
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


def prompt_stub(calls, prompt_rc=0, prompt_err=""):
    def stub(args, machine=None):
        calls.append(args)
        if args[:2] == ["agent", "prompt"]:
            return prompt_rc, '{"result":{}}' if prompt_rc == 0 else "", prompt_err
        if args[:2] == ["agent", "get"]:
            return 0, json.dumps({"result": {"agent": {
                "agent_status": "idle", "state_change_seq": 1}}}), ""
        return 0, "{}", ""
    return stub


class TestB6WriteAhead(unittest.TestCase):
    def test_strict_ledger_fails_before_prompt(self):
        class BoomLedger:
            def write_running(self, *args, **kwargs):
                raise TimeoutError("ledger lock timeout")

        class Mod:
            Ledger = BoomLedger

        original = hao._load_module
        def fake_load(name, filename):
            return Mod if name == "hao_ledger" else original(name, filename)

        calls = []
        with mock.patch.object(hao, "_load_module", side_effect=fake_load), \
                mock.patch.object(hao, "run_herdr", side_effect=prompt_stub(calls)):
            rc, _, err = run_cli(["ask", "w2:p9", "task", "--strict-ledger"])
        self.assertEqual(rc, 8)
        self.assertFalse(any(c[:2] == ["agent", "prompt"] for c in calls))
        self.assertIn("ledger write failed", err)

    def test_non_strict_ledger_dispatches_and_returns_token(self):
        class BoomLedger:
            def write_running(self, *args, **kwargs):
                raise TimeoutError("ledger lock timeout")

        class Mod:
            Ledger = BoomLedger

        original = hao._load_module
        def fake_load(name, filename):
            return Mod if name == "hao_ledger" else original(name, filename)

        calls = []
        with mock.patch.object(hao, "_load_module", side_effect=fake_load), \
                mock.patch.object(hao, "run_herdr", side_effect=prompt_stub(calls)):
            rc, out, err = run_cli(["ask", "w2:p9", "task"])
        self.assertEqual(rc, 0)
        self.assertTrue(any(c[:2] == ["agent", "prompt"] for c in calls))
        self.assertIn("token", json.loads(out))
        self.assertIn("warning", err)

    def test_prompt_failure_cancels_record(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            calls = []
            with mock.patch.object(
                    hao, "run_herdr",
                    side_effect=prompt_stub(calls, 1, '{"error":{"code":"agent_not_found"}}')):
                rc, _, err = run_cli(["ask", "w2:p9", "task"],
                                     {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
            self.assertEqual(rc, 3)
            files = [f for f in os.listdir(os.path.join(d, "hao", "tasks"))
                     if f.endswith(".json")]
            self.assertEqual(len(files), 1)
            rec = json.load(open(_path(files[0][:-5])))
            self.assertEqual(rec.get("status"), "cancelled")
            self.assertIn("hao ask:", err)
            os.environ.pop("HAO_STATE_DIR", None)


if __name__ == "__main__":
    unittest.main()
