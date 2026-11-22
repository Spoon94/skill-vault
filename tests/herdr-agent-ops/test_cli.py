import os
import io
import subprocess
import sys
import tempfile
import unittest
import types
from importlib.machinery import SourceFileLoader
import contextlib
from contextlib import redirect_stdout

_loader = SourceFileLoader("hao", os.path.join(os.path.dirname(__file__), "..", "..", "herdr-agent-ops", "scripts", "hao"))
hao = types.ModuleType(_loader.name)
_loader.exec_module(hao)

normalize_id = hao.normalize_id
build_prompt = hao.build_prompt
SENTINEL_RE = hao.SENTINEL_RE
build_parser = hao.build_parser
cmd_cancel = hao.cmd_cancel
cmd_done = hao.cmd_done

SKILL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "herdr-agent-ops")


class TestParser(unittest.TestCase):
    def test_restore_defaults(self):
        p = build_parser()
        a = p.parse_args(["restore", "--dry-run"])
        self.assertIsNone(a.workspace)
        self.assertTrue(a.adopt)
        self.assertTrue(a.dry_run)

    def test_restore_no_adopt(self):
        a = build_parser().parse_args(["restore", "--no-adopt"])
        self.assertFalse(a.adopt)

    def test_say_one_arg(self):
        a = build_parser().parse_args(["say", "hello"])
        self.assertEqual(a.args, ["hello"])

    def test_say_two_args(self):
        a = build_parser().parse_args(["say", "forge", "hello world"])
        self.assertEqual(a.args, ["forge", "hello world"])

    def test_wait_flags(self):
        a = build_parser().parse_args(["wait", "w2:p9", "hao-abc", "--no-agent", "--accept-unknown"])
        self.assertTrue(a.no_agent)
        self.assertTrue(a.accept_unknown)

    def test_aliases(self):
        p = build_parser()
        a = p.parse_args(["n", "w2:p9", "hawk", "--scope", "api"])
        self.assertEqual(a.name, "hawk")
        a2 = p.parse_args(["s", "审查 PR"])
        self.assertEqual(a2.task, "审查 PR")


class TestIds(unittest.TestCase):
    def test_normalize_full_token(self):
        self.assertEqual(normalize_id("hao-abcdef1234567890"), "abcdef123456")

    def test_normalize_shortid_passthrough(self):
        self.assertEqual(normalize_id("abcdef123456"), "abcdef123456")

    def test_token_16hex(self):
        import secrets
        tok = "hao-" + secrets.token_hex(8)
        self.assertRegex(tok[4:], r"^[0-9a-f]{16}$")
        self.assertIsNotNone(SENTINEL_RE.match(f"  HAO_DONE {tok}"))

    def test_build_prompt_file_mode(self):
        p = build_prompt("do X", "hao-aabb1122334455", "/tmp/r.md")
        self.assertNotIn("hao-aabb1122334455", p.replace("\n", ""))
        self.assertIn("/tmp/r.md", p)


class TestLedgerFlow(unittest.TestCase):
    def test_done_cancel_by_shortid(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["XDG_STATE_HOME"] = d
            sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))
            try:
                from ledger import Ledger
                l = Ledger()
                sid = "abcd12345678"
                l.write_running(sid, token="hao-" + sid + "9900")
                # cancel by shortid
                self.assertEqual(cmd_cancel(sid), 0)
                # done after cancel rejected
                self.assertEqual(cmd_done("hao-" + sid + "9900", None), 6)
            finally:
                sys.path.pop(0)

    def test_cancel_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["XDG_STATE_HOME"] = d
            sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))
            try:
                self.assertEqual(cmd_cancel("zzzz99999999"), 3)
            finally:
                sys.path.pop(0)


class TestFileWait(unittest.TestCase):
    def test_wait_file(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["XDG_STATE_HOME"] = d
            sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))
            try:
                from ledger import Ledger
                l = Ledger()
                sid = "feed12345678"
                rp = os.path.join(d, "hao", "tasks", sid, "result.md")
                os.makedirs(os.path.dirname(rp), exist_ok=True)
                open(rp, "w").close()  # empty file
                l.write_running(sid, result_path=rp)
                # simulate an existing pane WITHOUT an agent (r6#2):
                # agent get -> agent_not_found, pane get -> exists
                orig = hao.run_herdr

                def stub(args, machine=None):
                    if args[:2] == ["agent", "get"]:
                        return 1, "", '{"error":{"code":"agent_not_found"}}'
                    if args[:2] == ["pane", "get"]:
                        return 0, '{"result":{"pane":{"pane_id":"w2:pX"}}}', ""
                    return orig(args, machine)

                hao.run_herdr = stub
                try:
                    # empty file -> timeout (short deadline)
                    r = hao._wait_file("w2:pX", sid, "hao-feed1234567890", 0.3, None)
                    self.assertEqual(r, 4)
                    # write content -> done after size stabilizes
                    with open(rp, "w") as f:
                        f.write("result body")
                    r2 = hao._wait_file("w2:pX", sid, "hao-feed1234567890", 6, None)
                    self.assertEqual(r2["status"], "done")
                    self.assertEqual(r2["result_path"], rp)
                finally:
                    hao.run_herdr = orig
            finally:
                sys.path.pop(0)

    def test_wait_file_missing_pane_exit3(self):
        # r6#2 + error-map fix: nonexistent pane must stop the wait with 3
        with tempfile.TemporaryDirectory() as d:
            os.environ["XDG_STATE_HOME"] = d
            sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))
            try:
                from ledger import Ledger
                Ledger().write_running("feed99998888")
                r = hao._wait_file("w2:pX", "feed99998888", "hao-feed9999888890", 3, None)
                self.assertEqual(r, 3)
            finally:
                sys.path.pop(0)


class TestTokenMatches(unittest.TestCase):
    def test_full_token(self):
        self.assertTrue(hao._token_matches(
            "hao-aabbccddeeff0011", "hao-aabbccddeeff0011", "aabbccddeeff"))

    def test_bare_shortid_matches_16hex_sentinel(self):
        # forge #9: waiter holds only the 12-hex shortid; sentinel is 16-hex
        self.assertTrue(hao._token_matches(
            "hao-aabbccddeeff0011", "aabbccddeeff", "aabbccddeeff"))
        self.assertTrue(hao._token_matches(
            "hao-aabbccddeeff0011", None, "aabbccddeeff"))

    def test_mismatch(self):
        self.assertFalse(hao._token_matches(
            "hao-aabbccddeeff0011", "hao-9999888877776666", "999988887777"))


class TestSentinelRobustness(unittest.TestCase):
    def test_regex_accepts_overlong_token(self):
        # peer mis-assembled the token (20-hex, duplicated segment) must
        # still match; the sid prefix anchors task identity
        self.assertIsNotNone(SENTINEL_RE.match("  HAO_DONE hao-aabb11223344aabb1122"))

    def test_join_wrapped_sentinel(self):
        lines = ["  HAO_DONE hao-aabb11", "  223344aabb1122"]
        joined = hao._join_wrapped_sentinels(lines)
        self.assertEqual(joined, ["  HAO_DONE hao-aabb11223344aabb1122"])
        m = SENTINEL_RE.match(joined[0])
        self.assertIsNotNone(m)
        self.assertTrue(hao._token_matches(m.group(1), None, "aabb11223344"))

    def test_join_skips_non_hex_continuation(self):
        lines = ["  HAO_DONE hao-aabb11", "  ordinary output line"]
        self.assertEqual(hao._join_wrapped_sentinels(lines), lines)

    def test_join_leaves_complete_sentinel_alone(self):
        lines = ["  HAO_DONE hao-aabb11223344", "  next message"]
        self.assertEqual(hao._join_wrapped_sentinels(lines), lines)

    def test_regex_accepts_missing_prefix(self):
        # round-8 live incident: peer dropped the hao- prefix entirely
        m = SENTINEL_RE.match("  HAO_DONE aabb1122334499ff")
        self.assertIsNotNone(m)
        self.assertTrue(hao._token_matches(m.group(1), None, "aabb11223344"))

    def test_join_never_extends_complete_sentinel(self):
        # r8#1: hex output line right after a COMPLETE 16-hex sentinel
        lines = ["  HAO_DONE hao-aabb1122334499ff", "  ccddeeff0011223344"]
        self.assertEqual(hao._join_wrapped_sentinels(lines), lines)

    def test_join_respects_total_cap(self):
        # r8#1: fragment 11-hex + continuation 23-hex > 32 -> not joined
        lines = ["  HAO_DONE hao-aabb1122334", "  4556677889900aabbccddee"]
        self.assertEqual(hao._join_wrapped_sentinels(lines), lines)

    def test_overlong_without_sid_anchor_rejected(self):
        self.assertFalse(hao._token_matches(
            "hao-ccddee00112233445566", None, "aabb11223344"))


class TestWriteDegradation(unittest.TestCase):
    def setUp(self):
        self.lm = hao._load_module("hao_ledger", "ledger.py")
        self.orig_ledger = self.lm.Ledger
        self.orig_run = hao.run_herdr

    def tearDown(self):
        self.lm.Ledger = self.orig_ledger
        hao.run_herdr = self.orig_run
        hao._LEDGER_WARNED = False
        os.environ.pop("XDG_STATE_HOME", None)

    def test_done_prints_sentinel_when_ledger_write_fails(self):
        # r8#3 (P1): ledger failure must never swallow the sentinel
        class BoomLedger(self.orig_ledger):
            def write_done(self, *a, **k):
                raise TimeoutError("ledger lock timeout")

            def get(self, sid):
                return None

        self.lm.Ledger = BoomLedger
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = hao.cmd_done("hao-aabb1122334499ff", None)
        self.assertEqual(rc, 0)
        self.assertIn("HAO_DONE", out.getvalue())
        self.assertIn("warning", err.getvalue())

    def test_ask_returns_token_when_ledger_write_fails(self):
        # r8#3 (P1): task dispatched -> the token must survive the write failure
        class BoomLedger(self.orig_ledger):
            def write_running(self, *a, **k):
                raise TimeoutError("ledger lock timeout")

        def stub(args, machine=None):
            if args[:2] == ["agent", "prompt"]:
                return 0, '{"result":{}}', ""
            if args[:2] == ["agent", "get"]:
                return 1, "", '{"error":{"code":"agent_not_found"}}'
            return self.orig_run(args, machine)

        self.lm.Ledger = BoomLedger
        hao.run_herdr = stub
        with tempfile.TemporaryDirectory() as d:
            os.environ["XDG_STATE_HOME"] = d
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                r = hao.cmd_ask("w2:pX", "task text", False, "sentinel", None, 60)
        self.assertIsInstance(r, dict)
        self.assertIn("token", r)
        self.assertIn("warning", err.getvalue())


class TestParserFlags(unittest.TestCase):
    def test_wait_token_flag(self):
        a = build_parser().parse_args(["wait", "w2:p9", "--token", "hao-abc123"])
        self.assertEqual(a.token_opt, "hao-abc123")
        self.assertIsNone(a.token)

    def test_done_token_flag(self):
        a = build_parser().parse_args(["done", "--token", "hao-abc123"])
        self.assertEqual(a.token_opt, "hao-abc123")

    def test_list_workspace_flag(self):
        a = build_parser().parse_args(["list", "--workspace", "w2"])
        self.assertEqual(a.workspace_opt, "w2")

    def test_restore_workspace_flag(self):
        a = build_parser().parse_args(["restore", "--workspace", "w2", "--dry-run"])
        self.assertEqual(a.workspace_opt, "w2")
        self.assertTrue(a.dry_run)


class TestCLI(unittest.TestCase):
    def test_help(self):
        r = subprocess.run(
            [sys.executable, os.path.join(SKILL_DIR, "scripts", "hao"), "--help"],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0)
        self.assertIn("usage", r.stdout.lower())

    def test_no_args_help_and_roster(self):
        r = subprocess.run(
            [sys.executable, os.path.join(SKILL_DIR, "scripts", "hao")],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(r.returncode, 0)
        self.assertIn("usage", r.stdout.lower())

    def test_restore_dry_run_env_workspace(self):
        env = dict(os.environ)
        env["HERDR_WORKSPACE_ID"] = os.environ.get("HERDR_WORKSPACE_ID", "w2")
        r = subprocess.run(
            [sys.executable, os.path.join(SKILL_DIR, "scripts", "hao"),
             "restore", "--dry-run"],
            capture_output=True, text=True, timeout=15, env=env)
        self.assertIn(r.returncode, (0, 6))
        self.assertNotIn("Traceback", r.stderr)

    def test_suggest_json(self):
        r = subprocess.run(
            [sys.executable, os.path.join(SKILL_DIR, "scripts", "hao"),
             "suggest", "审查 PR", "--json",
             "--live-names", "--label-roles"],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(r.returncode, 0)
        import json
        out = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertIn("group", out)
        self.assertEqual(len(out["candidates"]), 3)


if __name__ == "__main__":
    unittest.main()
