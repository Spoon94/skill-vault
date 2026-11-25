import argparse
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
from hao_test_guard import install_offline_guard  # noqa: E402
install_offline_guard(hao)
from ledger import Ledger, _path  # noqa: E402


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


def name_stub(label="hao-forge-ops", renames=None):
    renames = renames if renames is not None else []

    def stub(args, machine=None):
        if args[:2] == ["agent", "list"]:
            return 0, json.dumps({"result": {"agents": []}}), ""
        if args[:2] == ["pane", "list"]:
            return 0, json.dumps({"result": {"panes": []}}), ""
        if args[:2] == ["pane", "get"]:
            return 0, json.dumps({"result": {"pane": {"pane_id": args[2],
                                                       "label": label}}}), ""
        if args[:2] == ["agent", "get"]:
            return 0, json.dumps({"result": {"agent": {"name": "forge"}}}), ""
        if args[:2] == ["pane", "rename"]:
            renames.append(args[3])
            return 0, "", ""
        if args[:2] == ["agent", "rename"]:
            return 0, "", ""
        return 0, "{}", ""
    return stub


class TestPhaseBHelp(unittest.TestCase):
    def test_help_completeness_and_metavars(self):
        p = hao.build_parser()
        self.assertIn("Examples:", p.epilog)
        self.assertIn("Exit codes:", p.epilog)
        subs = [a for a in p._actions if isinstance(a, argparse._SubParsersAction)]
        self.assertEqual(len(subs), 1)
        for sa in subs:
            for name, sp in sa.choices.items():
                self.assertTrue(sp.description, name)
                for action in sp._actions:
                    if action.dest in ("func", "help"):
                        continue
                    self.assertIsNotNone(action.help, f"{name} {action.dest}")
        wait = sa.choices["wait"]
        token_opt = next(a for a in wait._actions if "--token" in a.option_strings)
        self.assertEqual(token_opt.metavar, "TOKEN")

    def test_help_line_limits(self):
        p = hao.build_parser()
        self.assertLessEqual(len(p.format_help().splitlines()), 40)
        for name in ("wait", "ask"):
            sp = next(sp for sa in p._actions
                      if isinstance(sa, argparse._SubParsersAction)
                      for k, sp in sa.choices.items() if k == name)
            self.assertLessEqual(len(sp.format_help().splitlines()), 40)


class TestPhaseBName(unittest.TestCase):
    def test_name_keeps_existing_scope(self):
        renames = []
        with mock.patch.object(hao, "run_herdr", side_effect=name_stub(renames=renames)):
            rc, out, err = run_cli(["name", "w2:p9", "forge"])
        self.assertEqual(rc, 0)
        self.assertIn("hao-forge-ops", renames)
        self.assertEqual(err, "")

    def test_name_scope_empty_clears(self):
        renames = []
        with mock.patch.object(hao, "run_herdr", side_effect=name_stub(renames=renames)):
            rc, _, _ = run_cli(["name", "w2:p9", "forge", "--scope", ""])
        self.assertEqual(rc, 0)
        self.assertIn("hao-forge", renames)

    def test_name_dry_run_marks_kept(self):
        with mock.patch.object(hao, "run_herdr", side_effect=name_stub()):
            rc, out, _ = run_cli(["name", "w2:p9", "forge", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("scope=ops (kept)", out)

    def test_name_json(self):
        renames = []
        with mock.patch.object(hao, "run_herdr", side_effect=name_stub(renames=renames)):
            rc, out, err = run_cli(["name", "w2:p9", "forge", "--json"])
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertTrue(data["ok"])
        self.assertEqual(data["label"], "hao-forge-ops")
        self.assertEqual(err, "")


class TestPhaseBJson(unittest.TestCase):
    def test_clear_json(self):
        with mock.patch.object(hao, "run_herdr", side_effect=name_stub()):
            rc, out, _ = run_cli(["clear", "w2:p9", "--json"])
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(out)["ok"])

    def test_cancel_json(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                Ledger().write_running("abcd12345678")
                rc, out, err = run_cli(["cancel", "abcd12345678", "--json"],
                                       {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
                self.assertEqual(rc, 0)
                self.assertTrue(json.loads(out)["ok"])
                self.assertEqual(err, "")
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_json_error_stdout_and_stderr(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out, err = run_cli(["cancel", "deadbeef0000", "--json"],
                                   {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
        self.assertEqual(rc, 3)
        data = json.loads(out)
        self.assertFalse(data["ok"])
        self.assertEqual(data["exit"], 3)
        self.assertIn("hao cancel:", err)

    def test_restore_json_summary(self):
        panes = [{"pane_id": "w2:p9", "label": "hao-forge-ops", "agent": "claude"}]

        def stub(args, machine=None):
            if args[:2] == ["agent", "list"]:
                return 0, json.dumps({"result": {"agents": []}}), ""
            if args[:2] == ["pane", "list"]:
                return 0, json.dumps({"result": {"panes": panes}}), ""
            return 0, "{}", ""

        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc, out, _ = run_cli(["restore", "--dry-run", "--json"])
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertTrue(data["ok"])
        self.assertEqual(data["restored"], 1)

    def test_abort_json(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            Ledger().write_running("abcd12345678", target="w2:p9")
            def stub(args, machine=None):
                if args[:2] == ["agent", "get"]:
                    return 0, json.dumps({"result": {"agent": {
                        "agent_status": "idle"}}}), ""
                return 0, "{}", ""
            with mock.patch.object(hao, "run_herdr", side_effect=stub):
                rc, out, _ = run_cli(
                    ["abort", "abcd12345678", "--json"],
                    {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(out)["ok"])

    def test_status_json(self):
        def stub(args, machine=None):
            if args[:2] == ["agent", "get"]:
                return 0, json.dumps({"result": {"agent": {
                    "agent": "claude", "agent_status": "idle", "name": "forge"}}}), ""
            if args[:2] == ["pane", "get"]:
                return 0, json.dumps({"result": {"pane": {
                    "pane_id": args[2], "label": "hao-forge-ops"}}}), ""
            return 0, "{}", ""

        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc, out, _ = run_cli(["status", "w2:p9", "--json"],
                                 {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(out)["ok"])

    def test_result_json_and_consumed(self):
        with tempfile.TemporaryDirectory() as d:
            sid = "deadbeef0000"
            rp = os.path.join(d, "hao", "tasks", sid, "result.md")
            os.makedirs(os.path.dirname(rp))
            with open(rp, "w") as f:
                f.write("body")
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                Ledger().write_done(sid, result_path=rp)
                state = os.environ["HAO_STATE_DIR"]
                rc, out, _ = run_cli(["result", sid, "--json"],
                                     {"HAO_STATE_DIR": state})
                self.assertEqual(rc, 0)
                self.assertEqual(json.loads(out)["content"], "body")
                self.assertFalse(os.path.exists(_path(sid)))
                self.assertFalse(os.path.exists(state))
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_done_json(self):
        with tempfile.TemporaryDirectory() as d:
            token = "hao-" + "abcd12345678" + "9900"
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                Ledger().write_running("abcd12345678", token=token)
                rc, out, err = run_cli(["done", token, "--json"],
                                       {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
            finally:
                os.environ.pop("HAO_STATE_DIR", None)
        self.assertEqual(rc, 0)
        self.assertIn("HAO_DONE", out)
        self.assertTrue(json.loads(err.splitlines()[-1])["ok"])


class TestPhaseBRestore(unittest.TestCase):
    def test_zero_panes_message(self):
        def stub(args, machine=None):
            if args[:2] == ["agent", "list"]:
                return 0, json.dumps({"result": {"agents": []}}), ""
            if args[:2] == ["pane", "list"]:
                if "--workspace" in args:
                    return 1, "", '{"error":{"code":"workspace_not_found"}}'
                return 0, json.dumps({"result": {"panes": []}}), ""
            return 0, "{}", ""

        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc, out, _ = run_cli(["restore", "--workspace", "wZZZ", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("no hao- panes in workspace wZZZ", out)

    def test_summary_text(self):
        panes = [{"pane_id": "w2:p9", "label": "hao-forge-ops", "agent": "claude"}]

        def stub(args, machine=None):
            if args[:2] == ["agent", "list"]:
                return 0, json.dumps({"result": {"agents": []}}), ""
            if args[:2] == ["pane", "list"]:
                return 0, json.dumps({"result": {"panes": panes}}), ""
            return 0, "{}", ""

        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc, out, _ = run_cli(["restore", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("would restore 1, skipped 0", out)


class TestPhaseBCustom(unittest.TestCase):
    def test_custom_valid(self):
        rc, out, _ = run_cli(["suggest", "审查", "--custom", "hawk"])
        self.assertEqual(rc, 0)
        self.assertIn("hawk", out)

    def test_custom_invalid(self):
        rc, _, err = run_cli(["suggest", "审查", "--custom", "Hawk"])
        self.assertEqual(rc, 2)
        self.assertIn("custom", err)

    def test_custom_reserved_rejected(self):
        rc, _, err = run_cli(["suggest", "审查", "--custom", "wait"])
        self.assertEqual(rc, 2)
        self.assertIn("custom", err)

    def test_custom_json(self):
        rc, out, _ = run_cli(["suggest", "审查", "--custom", "hawk", "--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["candidates"], ["hawk"])


class TestPhaseBStrictLedger(unittest.TestCase):
    def test_strict_ledger_fails(self):
        class BoomLedger:
            def write_running(self, *args, **kwargs):
                raise TimeoutError("ledger lock timeout")

        class Mod:
            Ledger = BoomLedger

        def fake_load(name, filename):
            return Mod if name == "hao_ledger" else original(name, filename)

        original = hao._load_module

        def stub(args, machine=None):
            if args[:2] == ["agent", "prompt"]:
                return 0, '{"result":{}}', ""
            return 0, json.dumps({"result": {"agent": {"agent_status": "idle"}}}), ""

        with mock.patch.object(hao, "_load_module", side_effect=fake_load), \
                mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc, _, err = run_cli(["ask", "w2:p9", "task", "--strict-ledger"])
        self.assertEqual(rc, 8)
        self.assertIn("ledger write failed", err)


class TestPhaseBResultPath(unittest.TestCase):
    def test_allow_any_path(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "outside.txt")
            with open(path, "w") as f:
                f.write("outside")
            rc, out, err = run_cli(["result", "deadbeef0000", "--file", path,
                                    "--allow-any-path"], {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
        self.assertEqual(rc, 0)
        self.assertEqual(out, "outside\n")
        self.assertIn("warning", err)

    def test_deny_any_path(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "outside.txt")
            with open(path, "w") as f:
                f.write("outside")
            rc, _, err = run_cli(["result", "deadbeef0000", "--file", path],
                                 {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
        self.assertEqual(rc, 2)
        self.assertIn("hao result:", err)


class TestPhaseBCallerConsumed(unittest.TestCase):
    def test_caller_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            def stub(args, machine=None):
                if args[:2] == ["agent", "prompt"]:
                    return 0, '{"result":{}}', ""
                if args[:2] == ["agent", "get"]:
                    return 0, json.dumps({"result": {"agent": {
                        "agent_status": "idle", "state_change_seq": 1}}}), ""
                return 0, "{}", ""

            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            with mock.patch.object(hao, "run_herdr", side_effect=stub):
                rc, out, _ = run_cli(["ask", "w2:p9", "task"],
                                     {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks"), "HERDR_PANE_ID": "w2:p1"})
            self.assertEqual(rc, 0)
            sid = json.loads(out)["shortid"]
            rec = json.load(open(_path(sid)))
            self.assertEqual(rec.get("caller"), "w2:p1")

    def test_wait_consumed(self):
        with tempfile.TemporaryDirectory() as d:
            sid = "abcd12345678"
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            Ledger().write_running(sid, target="w2:p9")
            with mock.patch.object(hao, "_wait_sentinel",
                                   return_value={"status": "done"}):
                rc, _, _ = run_cli(["wait", "w2:p9", sid],
                                   {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
            self.assertEqual(rc, 0)
            self.assertFalse(os.path.exists(_path(sid)))


if __name__ == "__main__":
    unittest.main()
