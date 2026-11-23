import argparse
import ast
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


def run_cli(argv, env=None):
    out, err = io.StringIO(), io.StringIO()
    saved = {k: os.environ.get(k) for k in
             ("XDG_STATE_HOME", "HERDR_PANE_ID", "HAO_ABORT_ALLOW")}
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


class TestD6Guard(unittest.TestCase):
    def test_nonzero_returns_have_reason(self):
        tree = ast.parse(open(os.path.join(SKILL, "scripts", "hao")).read())
        bad = []

        def is_fail(v):
            return isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == "fail"

        def is_set_error(stmt):
            return (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
                    and isinstance(stmt.value.func, ast.Name)
                    and stmt.value.func.id == "_set_error")

        def walk(stmts, fn):
            for i, stmt in enumerate(stmts):
                if (isinstance(stmt, ast.Return)
                        and isinstance(stmt.value, ast.Constant)
                        and isinstance(stmt.value.value, int)
                        and not isinstance(stmt.value.value, bool)
                        and stmt.value.value != 0):
                    prev = stmts[i - 1] if i else None
                    if not is_fail(stmt.value) and not (prev and is_set_error(prev)):
                        bad.append((fn, stmt.lineno, stmt.value.value))
                for _, val in ast.iter_fields(stmt):
                    if isinstance(val, list) and val and all(isinstance(x, ast.stmt) for x in val):
                        walk(val, fn)

        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("cmd_"):
                walk(node.body, node.name)
        self.assertEqual(bad, [])


class TestD6Reasons(unittest.TestCase):
    def test_name_already_taken(self):
        def stub(args, machine=None):
            if args[:2] == ["agent", "list"]:
                return 0, json.dumps({"result": {"agents": [
                    {"name": "forge", "pane_id": "w2:p1"}]}}), ""
            if args[:2] == ["pane", "list"]:
                return 0, json.dumps({"result": {"panes": []}}), ""
            return 0, "{}", ""

        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc, _, err = run_cli(["name", "w2:p9", "forge"])
        self.assertEqual(rc, 6)
        self.assertIn("already taken by agent on w2:p1", err)

    def test_name_label_reserved(self):
        def stub(args, machine=None):
            if args[:2] == ["agent", "list"]:
                return 0, json.dumps({"result": {"agents": []}}), ""
            if args[:2] == ["pane", "list"]:
                return 0, json.dumps({"result": {"panes": [
                    {"pane_id": "w2:p1", "label": "hao-forge"}]}}), ""
            return 0, "{}", ""

        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc, _, err = run_cli(["name", "w2:p9", "forge"])
        self.assertEqual(rc, 6)
        self.assertIn("already reserved by label", err)

    def test_name_non_hao_label_needs_force(self):
        def stub(args, machine=None):
            if args[:2] == ["agent", "list"]:
                return 0, json.dumps({"result": {"agents": []}}), ""
            if args[:2] == ["pane", "list"]:
                return 0, json.dumps({"result": {"panes": []}}), ""
            if args[:2] == ["pane", "get"]:
                return 0, json.dumps({"result": {"pane": {
                    "pane_id": args[2], "label": "yaml"}}}), ""
            return 0, "{}", ""

        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc, _, err = run_cli(["name", "w2:p9", "forge"])
        self.assertEqual(rc, 6)
        self.assertIn("non-hao label", err)
        self.assertIn("--force", err)

    def test_ask_lifecycle_requires_wait(self):
        rc, _, err = run_cli(["ask", "w2:p9", "x", "--mode", "lifecycle"])
        self.assertEqual(rc, 2)
        self.assertIn("lifecycle mode requires --wait", err)

    def test_ask_lifecycle_needs_idle(self):
        def stub(args, machine=None):
            if args[:2] == ["agent", "get"]:
                return 0, json.dumps({"result": {"agent": {
                    "agent_status": "working"}}}), ""
            return 0, "{}", ""

        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc, _, err = run_cli(["ask", "w2:p9", "x", "--mode", "lifecycle",
                                  "--wait"])
        self.assertEqual(rc, 6)
        self.assertIn("lifecycle mode needs an idle agent", err)

    def test_done_cancelled_reason(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["XDG_STATE_HOME"] = d
            try:
                token = "hao-" + "abcd12345678" + "9900"
                Ledger().write_running("abcd12345678", token=token)
                Ledger().cancel("abcd12345678")
                rc, _, err = run_cli(["done", token], {"XDG_STATE_HOME": d})
                self.assertEqual(rc, 6)
                self.assertIn("was cancelled", err)
            finally:
                os.environ.pop("XDG_STATE_HOME", None)

    def test_done_final_working_reason(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["XDG_STATE_HOME"] = d
            try:
                token = "hao-" + "abcd12345678" + "9900"
                Ledger().write_running("abcd12345678", token=token,
                                       target="w2:p9")
                def stub(args, machine=None):
                    if args[:2] == ["agent", "get"]:
                        return 0, json.dumps({"result": {"agent": {
                            "agent_status": "working"}}}), ""
                    return 0, "{}", ""
                with mock.patch.object(hao, "run_herdr", side_effect=stub):
                    rc, _, err = run_cli(["done", token, "--final"],
                                         {"XDG_STATE_HOME": d})
                self.assertEqual(rc, 5)
                self.assertIn("--final requires idle or done", err)
            finally:
                os.environ.pop("XDG_STATE_HOME", None)

    def test_abort_not_found_and_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["XDG_STATE_HOME"] = d
            try:
                rc, _, err = run_cli(["abort", "deadbeef0000"],
                                     {"XDG_STATE_HOME": d})
                self.assertEqual(rc, 3)
                self.assertIn("not found", err)
                token = "hao-" + "abcd12345678" + "9900"
                Ledger().write_running("abcd12345678", token=token,
                                       target="w2:p9")
                def stub(args, machine=None):
                    if args[:2] == ["agent", "get"]:
                        return 0, json.dumps({"result": {"agent": {
                            "agent_status": "blocked"}}}), ""
                    return 0, "{}", ""
                with mock.patch.object(hao, "run_herdr", side_effect=stub):
                    rc, _, err = run_cli(["abort", "abcd12345678", "--interrupt"],
                                         {"XDG_STATE_HOME": d})
                self.assertEqual(rc, 5)
                self.assertIn("TTY or 0600 approval", err)
            finally:
                os.environ.pop("XDG_STATE_HOME", None)

    def test_say_reasons(self):
        rc, _, err = run_cli(["say", "hi"], {"HERDR_PANE_ID": None})
        self.assertEqual(rc, 3)
        self.assertIn("target required", err)
        def stub(args, machine=None):
            if args[:2] == ["agent", "get"]:
                return 0, json.dumps({"result": {"agent": {
                    "agent_status": "working"}}}), ""
            return 0, "{}", ""
        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc, _, err = run_cli(["say", "w2:p9", "hi", "--strict"])
        self.assertEqual(rc, 6)
        self.assertIn("--strict refuses", err)

    def test_doctor_machine_reason(self):
        with mock.patch.object(hao, "run_herdr", return_value=(1, "", "")):
            rc, _, err = run_cli(["doctor", "--machine", "nope"])
        self.assertEqual(rc, 7)
        self.assertIn("machine nope unavailable", err)

    def test_status_no_agent_status_is_null(self):
        def stub(args, machine=None):
            if args[:2] == ["agent", "get"]:
                return 1, "", '{"error":{"code":"agent_not_found"}}'
            if args[:2] == ["pane", "get"]:
                return 0, json.dumps({"result": {"pane": {
                    "pane_id": args[2], "label": "hao-forge-ops",
                    "agent": None}}}), ""
            return 0, "{}", ""
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc, out, _ = run_cli(["status", "w2:p9", "--json"],
                                 {"XDG_STATE_HOME": d})
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertIsNone(data["agent"])
        self.assertIsNone(data["agent_status"])


if __name__ == "__main__":
    unittest.main()
