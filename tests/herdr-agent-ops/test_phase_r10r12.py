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


def run_cli(argv, env=None):
    out, err = io.StringIO(), io.StringIO()
    saved = {k: os.environ.get(k) for k in
             ("HAO_STATE_DIR", "HERDR_PANE_ID", "HAO_ABORT_ALLOW")}
    if env:
        for key, value in env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
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
        hao._LEDGER_WARNED = False
    return rc, out.getvalue(), err.getvalue()


def one_json(test, text):
    lines = [line for line in text.splitlines() if line.strip()]
    test.assertEqual(len(lines), 1, text)
    return json.loads(lines[0])


class TestR10MachinePreflight(unittest.TestCase):
    COMMANDS = {
        "name": ["name", "w2:p9", "hawk"],
        "clear": ["clear", "w2:p9"],
        "restore": ["restore"],
        "suggest": ["suggest", "task"],
        "ask": ["ask", "w2:p9", "task"],
        "wait": ["wait", "w2:p9", "deadbeef0000"],
        "list": ["list"],
        "stop": ["stop", "w2:p9"],
        "doctor": ["doctor"],
    }

    def _run_all(self, stub, expected):
        with tempfile.TemporaryDirectory() as d:
            state = os.path.join(d, "hao", "tasks")
            env = {"HAO_STATE_DIR": state, "HERDR_PANE_ID": None}
            for name, argv in self.COMMANDS.items():
                with self.subTest(cmd=name):
                    with mock.patch.object(hao, "run_herdr", side_effect=stub):
                        rc, out, err = run_cli(
                            argv + ["--machine", "nope", "--json"], env)
                    self.assertEqual(rc, expected[name], err)
                    self.assertTrue(out.strip(), (name, err))
                    one_json(self, out)
                    self.assertNotIn("Traceback", err)
                    self.assertFalse(os.path.exists(state), name)
                    if name != "doctor":
                        self.assertIn("nope", err)

    def test_unknown_machine_is_exit_7_everywhere(self):
        def stub(args, machine=None):
            if args[:2] == ["machine", "status"]:
                return 1, "", "error: unknown machine 'nope'"
            raise AssertionError(f"unexpected herdr call: {args}")
        expected = {name: 7 for name in self.COMMANDS}
        self._run_all(stub, expected)

    def test_unreachable_herdr_is_exit_8_except_doctor(self):
        def stub(args, machine=None):
            if args[:2] == ["machine", "status"]:
                return 8, "", "herdr unavailable: boom"
            raise AssertionError(f"unexpected herdr call: {args}")
        expected = {name: 8 for name in self.COMMANDS if name != "doctor"}
        expected["doctor"] = 7
        self._run_all(stub, expected)

    def test_plain_text_unknown_machine_maps_to_7(self):
        self.assertEqual(hao.herdr_error_rc("error: unknown machine 'x'"), 7)
        self.assertIsNone(hao._herdr_err_code("not json"))

    def test_suggest_non_json_does_not_crash(self):
        with mock.patch.object(hao, "run_herdr",
                               return_value=(0, "not json", "")):
            rc = hao.cmd_suggest("task", None, True, None, None, None, None)
        self.assertEqual(rc, 8)

    def test_list_non_json_does_not_crash(self):
        with mock.patch.object(hao, "run_herdr",
                               return_value=(0, "not json", "")):
            rc = hao.cmd_list(json_out=True)
        self.assertEqual(rc, 8)

    def test_resolve_non_json_is_silent(self):
        with mock.patch.object(hao, "run_herdr",
                               return_value=(0, "not json", "")):
            self.assertEqual(hao.resolve_target("verse"), "verse")


class TestR11UnresponsiveWarning(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "hao", "tasks")
        os.environ["HAO_STATE_DIR"] = self.state

    def tearDown(self):
        os.environ.pop("HAO_STATE_DIR", None)
        self.tmp.cleanup()

    def _stub(self, status):
        def stub(args, machine=None):
            if args[:2] == ["agent", "get"]:
                return 0, json.dumps({"result": {"agent": {
                    "agent_status": status}}}), ""
            return 0, "{}", ""
        return stub

    def test_idle_warns_once_and_continues(self):
        with mock.patch.object(hao, "RESPONSE_WARN_S", 0), \
                mock.patch.object(hao, "FAST_PATH_SECONDS", 0), \
                mock.patch.object(hao, "run_herdr",
                                  side_effect=self._stub("idle")), \
                mock.patch.object(hao, "_sentinel_scan_tail",
                                  return_value=(None, None)), \
                mock.patch.object(hao.time, "sleep", return_value=None), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            rc = hao.cmd_wait("w2:p9", "deadbeef0000", 0.05)
        self.assertEqual(rc, 4)
        text = err.getvalue()
        self.assertEqual(text.count("after 15s"), 1, text)
        self.assertIn("pane read", text)
        self.assertIn("prompt", text)

    def test_working_does_not_warn(self):
        with mock.patch.object(hao, "RESPONSE_WARN_S", 0), \
                mock.patch.object(hao, "FAST_PATH_SECONDS", 0), \
                mock.patch.object(hao, "run_herdr",
                                  side_effect=self._stub("working")), \
                mock.patch.object(hao, "_sentinel_scan_tail",
                                  return_value=(None, None)), \
                mock.patch.object(hao.time, "sleep", return_value=None), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            rc = hao.cmd_wait("w2:p9", "deadbeef0000", 0.05)
        self.assertEqual(rc, 4)
        self.assertNotIn("after 15s", err.getvalue())

    def test_unknown_does_not_warn(self):
        with mock.patch.object(hao, "RESPONSE_WARN_S", 0), \
                mock.patch.object(hao, "FAST_PATH_SECONDS", 0), \
                mock.patch.object(hao, "run_herdr",
                                  side_effect=self._stub("unknown")), \
                mock.patch.object(hao, "_sentinel_scan_tail",
                                  return_value=(None, None)), \
                mock.patch.object(hao.time, "sleep", return_value=None), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            rc = hao.cmd_wait("w2:p9", "deadbeef0000", 0.05)
        self.assertEqual(rc, 9)
        self.assertNotIn("after 15s", err.getvalue())


class TestR12PromptApproval(unittest.TestCase):
    def test_prompt_prefers_backup_without_requesting_approval(self):
        prompt = hao.build_prompt("task", "hao-" + "aabbccddeeff0011")
        self.assertIn("需要向用户申请审批", prompt)
        self.assertIn("不要请求审批", prompt)
        self.assertIn("只打印备份信号", prompt)
        self.assertNotIn("hao-aabbccddeeff0011", prompt)


if __name__ == "__main__":
    unittest.main()
