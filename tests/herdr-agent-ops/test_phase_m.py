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
from ledger import Ledger  # noqa: E402


def run_cli(argv, env=None):
    out, err = io.StringIO(), io.StringIO()
    saved = {k: os.environ.get(k) for k in
             ("HAO_STATE_DIR", "HAO_ABORT_ALLOW", "HERDR_PANE_ID")}
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
        hao._LEDGER_WARNED = False
    return rc, out.getvalue(), err.getvalue()


def ok_stub(args, machine=None):
    if args[:2] == ["agent", "list"]:
        return 0, json.dumps({"result": {"agents": []}}), ""
    if args[:2] == ["pane", "list"]:
        return 0, json.dumps({"result": {"panes": []}}), ""
    if args[:2] == ["pane", "get"]:
        return 0, json.dumps({"result": {"pane": {
            "pane_id": args[2], "label": "hao-hawk", "agent": None}}}), ""
    if args[:2] == ["agent", "get"]:
        return 0, json.dumps({"result": {"agent": {
            "agent_status": "idle", "state_change_seq": 0}}}), ""
    return 0, "{}", ""


def one_json_line(test, text):
    lines = [line for line in text.splitlines() if line.strip()]
    test.assertEqual(len(lines), 1, text)
    return json.loads(lines[0])


class TestM1AbortJson(unittest.TestCase):
    def test_interrupt_emits_one_json(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                token = "hao-" + "abcd12345678" + "9900"
                Ledger().write_running("abcd12345678", target="w2:p9",
                                       token=token)
                with mock.patch.object(hao, "run_herdr", side_effect=ok_stub), \
                        mock.patch.object(hao.time, "sleep", return_value=None):
                    rc, out, err = run_cli(
                        ["abort", "abcd12345678", "--interrupt", "--json"],
                        {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks"), "HAO_ABORT_ALLOW": "1"})
                self.assertEqual(rc, 0, err)
                data = one_json_line(self, out)
                self.assertEqual(data, {"ok": True, "shortid": "abcd12345678",
                                        "cancelled": True, "interrupted": True,
                                        "agent_status_before": "idle",
                                        "agent_status_after": "idle"})
                rec = Ledger().get("abcd12345678")
                self.assertEqual(rec["status"], "cancelled")
                self.assertTrue(rec["interrupted"])
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_non_interrupt_json_has_cancelled(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                Ledger().write_running("abcd12345678", target="w2:p9",
                                       token="hao-" + "abcd12345678" + "9900")
                with mock.patch.object(hao, "run_herdr", side_effect=ok_stub):
                    rc, out, err = run_cli(
                        ["abort", "abcd12345678", "--json"],
                        {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
                self.assertEqual(rc, 0, err)
                data = one_json_line(self, out)
                self.assertEqual(data, {"ok": True, "shortid": "abcd12345678",
                                        "cancelled": True, "interrupted": False,
                                        "peer_running": False})
            finally:
                os.environ.pop("HAO_STATE_DIR", None)


class TestM2AlwaysJson(unittest.TestCase):
    def test_ask_error_without_json_flag(self):
        def stub(args, machine=None):
            if args[:2] == ["pane", "layout"]:
                return 0, '{"result":{"layout":{"panes":[]}}}', ""
            if args[:2] == ["agent", "get"]:
                return 0, '{"result":{"agent":{"agent_status":"idle"}}}', ""
            return 0, "{}", ""
        with mock.patch.object(hao, "run_herdr", side_effect=stub):
            rc, out, err = run_cli(
                ["ask", "w2:p9", "x", "--mode", "lifecycle"],
                {"HAO_STATE_DIR": tempfile.mkdtemp()})
        self.assertEqual(rc, 2)
        data = one_json_line(self, out)
        self.assertFalse(data["ok"])
        self.assertIn("requires --wait", data["error"])
        self.assertIn("hao ask:", err)

    def test_wait_error_without_json_flag(self):
        rc, out, err = run_cli(["wait", "w2:p9", "nothex"],
                               {"HAO_STATE_DIR": tempfile.mkdtemp()})
        self.assertEqual(rc, 2)
        data = one_json_line(self, out)
        self.assertFalse(data["ok"])
        self.assertIn("hao wait:", err)

    def test_argparse_error_is_json_too(self):
        for argv in (["ask"], ["wait"], ["a"], ["w"]):
            with self.subTest(argv=argv):
                rc, out, err = run_cli(argv)
                self.assertEqual(rc, 2)
                data = one_json_line(self, out)
                self.assertEqual(data, {"ok": False, "error": "usage error",
                                        "exit": 2})
                self.assertIn("error:", err)

    def test_done_error_json_stays_on_stderr(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out, err = run_cli(
                ["done", "hao-" + "aabbccddeeff" + "0011", "--json"],
                {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
        self.assertEqual(rc, 3)
        self.assertEqual(out, "")
        payloads = [json.loads(line) for line in err.splitlines()
                    if line.startswith("{")]
        self.assertEqual(len(payloads), 1)
        self.assertFalse(payloads[0]["ok"])
        self.assertIn("not found", payloads[0]["error"])


class TestM3DoneLedgerContract(unittest.TestCase):
    def test_unknown_readable_task_returns_3_without_sentinel(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out, err = run_cli(
                ["done", "hao-" + "aabbccddeeff" + "0011", "--json"],
                {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
            self.assertEqual(rc, 3)
            self.assertNotIn("HAO_DONE", out)
            self.assertIn("not found", err)
            self.assertFalse(os.path.exists(
                os.path.join(d, "hao", "tasks", "aabbccddeeff.json")))

    def test_unreadable_ledger_degrades_to_sentinel(self):
        class UnreadableLedger:
            def __init__(self, *a, **k):
                pass

            def get(self, sid):
                raise OSError("ledger unreadable")

            def write_done(self, *a, **k):
                raise OSError("ledger unavailable")

        fake = types.SimpleNamespace(Ledger=UnreadableLedger)
        with mock.patch.object(hao, "_load_module", return_value=fake):
            rc, out, err = run_cli(
                ["done", "hao-" + "aabbccddeeff" + "0011"])
        self.assertEqual(rc, 0)
        self.assertIn("HAO_DONE", out)
        self.assertIn("warning", err)

    def test_unreadable_ledger_constructor_degrades_to_sentinel(self):
        class CtorBoom:
            def __init__(self, *a, **k):
                raise OSError("ledger unavailable")

        fake = types.SimpleNamespace(Ledger=CtorBoom)
        with mock.patch.object(hao, "_load_module", return_value=fake):
            rc, out, err = run_cli(
                ["done", "hao-" + "aabbccddeeff" + "0011"])
        self.assertEqual(rc, 0)
        self.assertIn("HAO_DONE", out)
        self.assertIn("warning", err)

    def test_existing_running_record_is_marked_done(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                token = "hao-" + "abcd12345678" + "9900"
                Ledger().write_running("abcd12345678", token=token)
                rc, out, err = run_cli(["done", token],
                                       {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
                self.assertEqual(rc, 0, err)
                self.assertIn("HAO_DONE " + token, out)
                self.assertEqual(Ledger().get("abcd12345678")["status"],
                                 "done")
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_existing_done_record_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                token = "hao-" + "abcd12345678" + "9900"
                Ledger().write_running("abcd12345678", token=token)
                Ledger().write_done("abcd12345678")
                rc, out, err = run_cli(["done", token],
                                       {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
                self.assertEqual(rc, 0, err)
                self.assertIn("HAO_DONE " + token, out)
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_cancelled_task_still_refused(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                token = "hao-" + "abcd12345678" + "9900"
                Ledger().write_running("abcd12345678", token=token)
                Ledger().cancel("abcd12345678")
                rc, out, err = run_cli(["done", token],
                                       {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
                self.assertEqual(rc, 6)
                self.assertNotIn("HAO_DONE", out)
                self.assertIn("was cancelled", err)
            finally:
                os.environ.pop("HAO_STATE_DIR", None)


class TestEveryCommandJsonContract(unittest.TestCase):
    """Success paths: --json stdout is exactly one JSON line (done: sentinel
    on stdout is deliberate; its JSON is on stderr)."""

    def _run_success(self, argv, setup=None, patch_wait=False, env=None):
        edits = {"HAO_STATE_DIR": os.path.join(self.d, "hao", "tasks"), "HERDR_PANE_ID": None,
                 "HAO_ABORT_ALLOW": "1"}
        if env:
            edits.update(env)
        if setup:
            setup()
        patches = [mock.patch.object(hao, "run_herdr", side_effect=ok_stub)]
        if patch_wait:
            patches.append(mock.patch.object(
                hao, "_wait_sentinel",
                return_value={"status": "done", "summary": "ok"}))
        for p in patches:
            p.start()
        try:
            return run_cli(argv, edits)
        finally:
            for p in reversed(patches):
                p.stop()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        os.environ["HAO_STATE_DIR"] = os.path.join(self.d, "hao", "tasks")
        Ledger().write_running("abcd12345678", target="w2:p9",
                               token="hao-" + "abcd12345678" + "9900")

    def tearDown(self):
        os.environ.pop("HAO_STATE_DIR", None)
        self.tmp.cleanup()

    def test_success_shapes(self):
        tok = "hao-" + "abcd12345678" + "9900"
        cases = [
            ("name", ["name", "w2:p9", "hawk", "--json"]),
            ("clear", ["clear", "w2:p9", "--json"]),
            ("restore", ["restore", "--json"]),
            ("ask", ["ask", "w2:p9", "hello", "--json"]),
            ("wait", ["wait", "w2:p9", "abcd12345678", "--json"], True),
            ("cancel", ["cancel", "abcd12345678", "--json"]),
            ("abort", ["abort", "abcd12345678", "--json"]),
            ("stop", ["stop", "w2:p9", "--json"]),
            ("suggest", ["suggest", "review API", "--json"]),
            ("list", ["list", "--json"]),
            ("status", ["status", "w2:p9", "--json"]),
            ("say", ["say", "w2:p9", "hi", "--json"]),
            ("doctor", ["doctor", "--machine", "m1", "--json"]),
            ("clean", ["clean", "--json"]),
        ]
        for case in cases:
            name, argv = case[0], case[1]
            patch_wait = len(case) > 2 and case[2]
            with self.subTest(name=name):
                # cancel/abort consume the record; recreate for each case
                rec_path = os.path.join(self.d, "hao", "tasks",
                                        "abcd12345678.json")
                if os.path.exists(rec_path):
                    os.remove(rec_path)
                Ledger().write_running("abcd12345678", target="w2:p9",
                                       token=tok)
                rc, out, err = self._run_success(argv, patch_wait=patch_wait)
                self.assertEqual(rc, 0, (name, err))
                one_json_line(self, out)
        # result + done need their own state
        sid = "beef11223344"
        rp = os.path.join(self.d, "hao", "tasks", sid, "result.md")
        os.makedirs(os.path.dirname(rp), exist_ok=True)
        with open(rp, "w") as f:
            f.write("body")
        Ledger().write_running(sid, target="w2:p9")
        Ledger().write_done(sid, result_path=rp)
        rc, out, err = self._run_success(["result", sid, "--json"])
        self.assertEqual(rc, 0, err)
        one_json_line(self, out)
        Ledger().write_running("abcd12345678", target="w2:p9", token=tok)
        rc, out, err = self._run_success(["done", tok, "--json"])
        self.assertEqual(rc, 0, err)
        self.assertIn("HAO_DONE", out)
        self.assertEqual(len([line for line in err.splitlines()
                              if line.startswith("{")]), 1)

    def test_error_shapes(self):
        cases = [
            ("name", ["name", "w2:p9", "X", "--json"], ok_stub),
            ("clear", ["clear", "w2:p9", "--json"],
             lambda a, m=None: (0, json.dumps({"result": {"pane": {
                 "pane_id": a[2], "label": "yaml"}}}), "")
             if a[:2] == ["pane", "get"] else ok_stub(a, m)),
            ("restore", ["restore", "--json"],
             lambda a, m=None: (1, "", "{}")),
            ("ask", ["ask", "w2:p9", "x", "--mode", "lifecycle", "--json"],
             ok_stub),
            ("wait", ["wait", "w2:p9", "nothex", "--json"], ok_stub),
            ("cancel", ["cancel", "deadbeef0000", "--json"], ok_stub),
            ("abort", ["abort", "deadbeef0000", "--json"], ok_stub),
            ("suggest", ["suggest", "task", "--custom", "X", "--json"],
             ok_stub),
            ("list", ["list", "--json"], lambda a, m=None: (1, "", "{}")),
            ("status", ["status", "--json"], ok_stub),
            ("say", ["say", "hi", "--json"], ok_stub),
            ("result", ["result", "deadbeef0000", "--json"], ok_stub),
            ("doctor", ["doctor", "--machine", "m1", "--json"],
             lambda a, m=None: (1, "", "{}")),
        ]
        for name, argv, stub in cases:
            with self.subTest(name=name):
                env = {"HAO_STATE_DIR": os.path.join(self.d, "hao", "tasks"), "HERDR_PANE_ID": None}
                with mock.patch.object(hao, "run_herdr", side_effect=stub):
                    rc, out, err = run_cli(argv, env)
                self.assertNotEqual(rc, 0)
                data = one_json_line(self, out)
                self.assertFalse(data["ok"])
                self.assertIn("hao " + name + ":", err)
        # done is the one documented exception: JSON on stderr, no stdout
        with mock.patch.object(hao, "run_herdr", side_effect=ok_stub):
            rc, out, err = run_cli(
                ["done", "hao-" + "deadbeef0000" + "0011", "--json"],
                {"HAO_STATE_DIR": os.path.join(self.d, "hao", "tasks")})
        self.assertEqual(rc, 3)
        self.assertEqual(out, "")
        self.assertEqual(len([line for line in err.splitlines()
                              if line.startswith("{")]), 1)


if __name__ == "__main__":
    unittest.main()