import contextlib
import io
import json
import os
import sys
import tempfile
import types
import unittest
from importlib.machinery import SourceFileLoader
from types import SimpleNamespace
from unittest import mock

HERE = os.path.dirname(__file__)
SKILL = os.path.join(HERE, "..", "..", "herdr-agent-ops")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
_loader = SourceFileLoader("hao", os.path.join(SKILL, "scripts", "hao"))
hao = types.ModuleType("hao")
_loader.exec_module(hao)
from hao_test_guard import install_offline_guard  # noqa: E402
install_offline_guard(hao)


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


class TestD8UniversalJson(unittest.TestCase):
    def test_all_subcommands_accept_json(self):
        samples = {
            "name": ["w2:p9", "hawk"], "clear": ["w2:p9"], "restore": [],
            "ask": ["w2:p9", "task"], "wait": ["w2:p9", "deadbeef0000"],
            "done": ["deadbeef0000"], "cancel": ["deadbeef0000"],
            "abort": ["deadbeef0000"], "stop": ["w2:p9"],
            "suggest": ["task"], "list": [],
            "status": [], "say": ["hi"], "result": ["deadbeef0000"],
            "doctor": [], "clean": [],
        }
        parser = hao.build_parser()
        for name, args in samples.items():
            with self.subTest(name=name):
                parsed = parser.parse_args([name, *args, "--json"])
                self.assertTrue(parsed.json)

    def test_say_json_success(self):
        with mock.patch.object(hao, "run_herdr", return_value=(0, "{}", "")):
            rc, out, _ = run_cli(["say", "w2:p9", "hi", "--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out), {"ok": True, "pane_id": "w2:p9"})

    def test_say_json_error(self):
        def stub(args, machine=None):
            if args[:2] == ["agent", "get"]:
                return 0, json.dumps({"result": {"agent": {
                    "agent_status": "working"}}}), ""
            return 0, "{}", ""
        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc, out, err = run_cli(["say", "w2:p9", "hi", "--strict", "--json"])
        self.assertEqual(rc, 6)
        self.assertFalse(json.loads(out)["ok"])
        self.assertIn("exit", json.loads(out))
        self.assertIn("hao say:", err)

    def test_doctor_machine_json(self):
        with mock.patch.object(hao, "run_herdr", return_value=(0, "{}", "")):
            rc, out, _ = run_cli(["doctor", "--machine", "m1", "--json"])
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(out)["ok"])
        self.assertEqual(json.loads(out)["checks"][0]["name"], "machine")
        with mock.patch.object(hao, "run_herdr", return_value=(1, "", "")):
            rc, out, err = run_cli(["doctor", "--machine", "m1", "--json"])
        self.assertEqual(rc, 7)
        self.assertFalse(json.loads(out)["ok"])
        self.assertIn("hao doctor:", err)

    def test_doctor_local_json(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "hao", "tasks"))
            run = SimpleNamespace(returncode=0, stdout="ok", stderr="")
            with mock.patch.object(hao.subprocess, "run", return_value=run):
                rc, out, _ = run_cli(["doctor", "--json"],
                                     {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks"),
                                      "HERDR_ENV": "1", "HERDR_PANE_ID": None})
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertTrue(data["ok"])
        self.assertTrue(all(c["ok"] for c in data["checks"]))
        self.assertEqual([c["name"] for c in data["checks"]],
                         ["python3", "herdr", "HERDR_ENV", "state dir", "ledger"])


if __name__ == "__main__":
    unittest.main()
