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
from unittest import mock

_loader = SourceFileLoader("hao", os.path.join(os.path.dirname(__file__), "..", "..", "herdr-agent-ops", "scripts", "hao"))
hao = types.ModuleType(_loader.name)
_loader.exec_module(hao)
from hao_test_guard import install_offline_guard  # noqa: E402
install_offline_guard(hao)

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
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
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
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))
            try:
                self.assertEqual(cmd_cancel("deadbeef0000"), 3)
            finally:
                sys.path.pop(0)


class TestFileWait(unittest.TestCase):
    def test_wait_file(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
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
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))
            try:
                from ledger import Ledger
                Ledger().write_running("feed99998888")
                def stub(args, machine=None):
                    if args[:2] == ["agent", "get"]:
                        return 1, "", '{"error":{"code":"agent_not_found"}}'
                    if args[:2] == ["pane", "get"]:
                        return 1, "", '{"error":{"code":"pane_not_found"}}'
                    return 0, "{}", ""
                with mock.patch.object(hao, "run_herdr", side_effect=stub):
                    r = hao._wait_file("w2:pX", "feed99998888",
                                       "hao-feed9999888890", 3, None)
                self.assertEqual(r, 3)
            finally:
                sys.path.pop(0)


class TestTokenMatches(unittest.TestCase):
    def test_full_token(self):
        full = "aabbccdd" + "eeff0011"
        self.assertTrue(hao._token_matches("hao-" + full, "hao-" + full, full[:12]))

    def test_twelve_hex_shortid_sentinel_accepted(self):
        # forge r14 exception: a peer emitting just the shortid is acceptable
        sid = "aabbccdd" + "eeff"
        self.assertTrue(hao._token_matches("hao-" + sid, None, sid))

    def test_bare_shortid_wait_rejects_16hex_sentinel(self):
        # r14#2: raw 13-16 hex requires full-token knowledge; a bare-shortid
        # wait misses the canonical sentinel (prefer miss over false done;
        # real waits upgrade the token from the ledger each round)
        full = "aabbccdd" + "eeff0011"
        self.assertFalse(hao._token_matches("hao-" + full, full[:12], full[:12]))
        self.assertFalse(hao._token_matches("hao-" + full, None, full[:12]))

    def test_sixteen_hex_requires_full_token(self):
        full = "aabbccdd" + "eeff0011"
        self.assertTrue(hao._token_matches("hao-" + full, full, full[:12]))
        # sid + 4 bogus hex must NOT pass even with the full token known
        faked = full[:12] + "ffff"
        self.assertFalse(hao._token_matches("hao-" + faked, full, full[:12]))

    def test_mismatch(self):
        full = "aabbccdd" + "eeff0011"
        other = "99998888" + "77776666"
        self.assertFalse(hao._token_matches("hao-" + full, other, other[:12]))


class TestSentinelRobustness(unittest.TestCase):
    def test_regex_accepts_overlong_token(self):
        corrupt = "aabb11223344" + "aabb1122"  # 20-hex mis-assembly
        self.assertIsNotNone(SENTINEL_RE.match("  HAO_DONE hao-" + corrupt))

    def test_regex_accepts_missing_prefix(self):
        # round-8 live incident: peer dropped the hao- prefix entirely
        full = "aabb1122" + "334499ff"
        m = SENTINEL_RE.match("  HAO_DONE " + full)
        self.assertIsNotNone(m)
        self.assertTrue(hao._token_matches(m.group(1), full, full[:12]))

    def test_join_wrapped_sentinel(self):
        # round-7 shape: 8-hex fragment + 12-hex continuation rebuilding a
        # segment-duplicated token; full token from ledger authenticates it
        full = "00112233" + "445566ff"
        corrupt = full[:12] + full[8:12] + full[12:]
        lines = ["  HAO_DONE hao-" + corrupt[:8], "  " + corrupt[8:]]
        joined = hao._join_wrapped_sentinels(lines)
        self.assertEqual([l for l, _ in joined], ["  HAO_DONE hao-" + corrupt])
        self.assertTrue(joined[0][1])
        m = SENTINEL_RE.match(joined[0][0])
        self.assertIsNotNone(m)
        self.assertTrue(hao._token_matches(m.group(1), full, full[:12],
                                           joined=True))

    def test_join_skips_non_hex_continuation(self):
        lines = ["  HAO_DONE hao-aabb11", "  ordinary output line"]
        self.assertEqual(hao._join_wrapped_sentinels(lines),
                         [(lines[0], False), (lines[1], False)])

    def test_join_leaves_complete_sentinel_alone(self):
        full = "aabb1122" + "334499ff"
        lines = ["  HAO_DONE hao-" + full, "  next message"]
        self.assertEqual([l for l, _ in hao._join_wrapped_sentinels(lines)], lines)

    def test_join_never_extends_complete_sentinel(self):
        # r8#1: hex output line right after a COMPLETE 16-hex sentinel
        full = "aabb1122" + "334499ff"
        lines = ["  HAO_DONE hao-" + full, "  " + "ccddeeff" + "0011223344"]
        self.assertEqual([l for l, _ in hao._join_wrapped_sentinels(lines)], lines)

    def test_join_respects_total_cap(self):
        # r8#1: fragment 11-hex + continuation 23-hex > 32 -> not joined
        lines = ["  HAO_DONE hao-aabb1122334", "  " + "4556677889" + "900aabbccddee"]
        self.assertEqual([l for l, _ in hao._join_wrapped_sentinels(lines)], lines)

    def test_join_keyword_token_split(self):
        # round-10 live shape: ~17-col pane split HAO_DONE | hao-<token>
        full = "00112233" + "445566ff"
        lines = ["  HAO_DONE", "  hao-" + full]
        joined = hao._join_wrapped_sentinels(lines)
        self.assertEqual([l for l, _ in joined], ["  HAO_DONE hao-" + full])
        self.assertTrue(joined[0][1])
        m = SENTINEL_RE.match(joined[0][0])
        self.assertIsNotNone(m)
        self.assertTrue(hao._token_matches(m.group(1), full, full[:12],
                                           joined=True))

    def test_join_keyword_bare_hex_token(self):
        # keyword line + prefix-less full token line (16 hex >= 16)
        full = "00112233" + "445566ff"
        lines = ["  HAO_DONE", "  " + full]
        joined = hao._join_wrapped_sentinels(lines)
        self.assertTrue(joined[0][1])
        m = SENTINEL_RE.match(joined[0][0])
        self.assertIsNotNone(m)
        self.assertTrue(hao._token_matches(m.group(1), full, full[:12],
                                           joined=True))

    def test_join_chains_across_three_lines(self):
        # "HAO_DONE hao-" | "0011" | rest -> chained joins, total <=32
        full = "00112233" + "445566ff"
        lines = ["  HAO_DONE hao-", "  " + full[:4], "  " + full[4:]]
        joined = hao._join_wrapped_sentinels(lines)
        self.assertEqual([l for l, _ in joined], ["  HAO_DONE hao-" + full])
        m = SENTINEL_RE.match(joined[0][0])
        self.assertIsNotNone(m)
        self.assertTrue(hao._token_matches(m.group(1), full, full[:12],
                                           joined=True))

    def test_bare_keyword_followed_by_non_hex_not_joined(self):
        lines = ["  打印：HAO_DONE", "  加一个空格再拼接"]
        self.assertEqual([l for l, _ in hao._join_wrapped_sentinels(lines)], lines)

    def test_prompt_echo_keyword_never_joins(self):
        # r11#1: non-standalone keyword lines (prompt echoes like 打印：HAO_DONE)
        # must not absorb a following shortid-looking line
        sid = "abcd1234" + "ef56"
        lines = ["  打印：HAO_DONE", "  " + sid]
        self.assertEqual([l for l, _ in hao._join_wrapped_sentinels(lines)], lines)

    def test_keyword_plus_bare_shortid_line_not_joined(self):
        # r11#1/r12#1: keyword-only lines demand a >=16-hex continuation
        sid = "abcd1234" + "ef56"
        lines = ["  HAO_DONE", "  " + sid]
        self.assertEqual([l for l, _ in hao._join_wrapped_sentinels(lines)], lines)

    def test_keyword_requires_complete_token_continuation(self):
        # r12#1: a 15-hex continuation would ride the shortid anchor -> reject
        almost = "0011223344556" + "67"  # 15 hex
        lines = ["  HAO_DONE", "  " + almost]
        self.assertEqual([l for l, _ in hao._join_wrapped_sentinels(lines)], lines)

    def test_fragment_with_border_decoration_joins(self):
        # r12#2: decorations AFTER the token fragment must not block joining
        full = "00112233" + "445566ff"
        lines = ["  HAO_DONE hao-" + full[:4] + " │", "  " + full[4:]]
        joined = hao._join_wrapped_sentinels(lines)
        self.assertEqual([l for l, _ in joined],
                         ["  HAO_DONE hao-" + full + " │"])
        m = SENTINEL_RE.match(joined[0][0])
        self.assertIsNotNone(m)
        self.assertTrue(hao._token_matches(m.group(1), full, full[:12],
                                           joined=True))

    def test_joined_requires_exact_full_token(self):
        # r13#1: a reassembled line authenticates ONLY via the exact full
        # token (or over-long head8/tail8) — never via the shortid anchor
        full = "00112233" + "445566ff"
        faked = full[:12] + "ffff"  # sid + 4 bogus hex = 16-hex
        self.assertFalse(hao._token_matches("hao-" + faked, full, full[:12],
                                            joined=True))
        self.assertTrue(hao._token_matches("hao-" + full, full, full[:12],
                                           joined=True))
        corrupt = full[:12] + full[8:12] + full[12:]  # segment duplication
        self.assertTrue(hao._token_matches("hao-" + corrupt, full, full[:12],
                                           joined=True))
        # full token unknown (degraded ledger): joined never authenticates
        self.assertFalse(hao._token_matches("hao-" + full, None, full[:12],
                                            joined=True))

    def test_fragment_branch_strips_head_decoration(self):
        # r13#2: "HAO_DONE。 hao-0011" must reassemble into a matchable line
        full = "00112233" + "445566ff"
        lines = ["  HAO_DONE。 hao-" + full[:4], "  " + full[4:]]
        joined = hao._join_wrapped_sentinels(lines)
        self.assertEqual([l for l, _ in joined], ["  HAO_DONE hao-" + full])
        m = SENTINEL_RE.match(joined[0][0])
        self.assertIsNotNone(m)
        self.assertTrue(hao._token_matches(m.group(1), full, full[:12],
                                           joined=True))

    def test_fragment_branch_strips_bold_decoration(self):
        # r13#2: **HAO_DONE** hao-0011 shape
        full = "00112233" + "445566ff"
        lines = ["**HAO_DONE** hao-" + full[:4], full[4:]]
        joined = hao._join_wrapped_sentinels(lines)
        m = SENTINEL_RE.match(joined[0][0])
        self.assertIsNotNone(m)
        self.assertTrue(hao._token_matches(m.group(1), full, full[:12],
                                           joined=True))

    def test_keyword_with_trailing_decoration_joins(self):
        # r11#1 漏报修复: trailing 。/│ decorations must not block the join
        full = "00112233" + "445566ff"
        lines = ["  HAO_DONE。", "  hao-" + full]
        joined = hao._join_wrapped_sentinels(lines)
        self.assertEqual([l for l, _ in joined], ["  HAO_DONE hao-" + full])
        m = SENTINEL_RE.match(joined[0][0])
        self.assertIsNotNone(m)
        self.assertTrue(hao._token_matches(m.group(1), full, full[:12],
                                           joined=True))

    def test_overlong_matches_full_token_head_tail(self):
        # r9#1: round-7 style segment duplication, full token known from ledger
        full = "00112233" + "445566ff"
        corrupt = full[:12] + full[8:12] + full[12:]
        self.assertTrue(hao._token_matches("hao-" + corrupt, full, full[:12]))

    def test_overlong_rejected_without_full_token(self):
        # degraded bare-shortid wait: over-long never matches (prefer miss)
        full = "00112233" + "445566ff"
        corrupt = full[:12] + full[8:12] + full[12:]
        self.assertFalse(hao._token_matches("hao-" + corrupt, full[:12], full[:12]))

    def test_overlong_false_positive_rejected(self):
        # forge r9 repro: truncated sentinel fragment + unrelated hex line
        # faking the shortid prefix -> head/tail rule rejects it
        full = "00112233" + "445566ff"
        faked = full[:12] + "dead" + "beef"
        self.assertFalse(hao._token_matches("hao-" + faked, full, full[:12]))

    def test_overlong_without_sid_anchor_rejected(self):
        other = "ccddee00" + "112233445566"  # 20-hex unrelated
        self.assertFalse(hao._token_matches("hao-" + other, None, "aabb11223344"))


class TestFileConventionPath(unittest.TestCase):
    def test_wait_file_falls_back_to_convention_path(self):
        # r9#2: ledger lost result_path; state_dir/<sid>/result.md still completes
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))
            try:
                from ledger import Ledger
                sid = "beef11223344"
                rp = os.path.join(d, "hao", "tasks", sid, "result.md")
                os.makedirs(os.path.dirname(rp), exist_ok=True)
                with open(rp, "w") as f:
                    f.write("body")
                Ledger().write_running(sid)  # no result_path field
                orig = hao.run_herdr

                def stub(args, machine=None):
                    if args[:2] == ["agent", "get"]:
                        return 1, "", '{"error":{"code":"agent_not_found"}}'
                    if args[:2] == ["pane", "get"]:
                        return 0, '{"result":{"pane":{"pane_id":"w2:pX"}}}', ""
                    return orig(args, machine)

                hao.run_herdr = stub
                try:
                    r = hao._wait_file("w2:pX", sid, "hao-beef1122334499", 6, None)
                finally:
                    hao.run_herdr = orig
                self.assertEqual(r["status"], "done")
                self.assertEqual(r["result_path"], rp)
            finally:
                sys.path.pop(0)


class TestWriteDegradation(unittest.TestCase):
    def setUp(self):
        self.lm = hao._load_module("hao_ledger", "ledger.py")
        self.orig_ledger = self.lm.Ledger
        self.orig_run = hao.run_herdr

    def tearDown(self):
        self.lm.Ledger = self.orig_ledger
        hao.run_herdr = self.orig_run
        hao._LEDGER_WARNED = False
        os.environ.pop("HAO_STATE_DIR", None)

    def test_done_prints_sentinel_when_ledger_write_fails(self):
        # r8#3 (P1): ledger failure must never swallow the sentinel
        class BoomLedger(self.orig_ledger):
            def write_done(self, *a, **k):
                raise TimeoutError("ledger lock timeout")

            def get(self, sid):
                return {"status": "running"}

        self.lm.Ledger = BoomLedger
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = hao.cmd_done("hao-" + "00112233" + "445566ff", None)
        self.assertEqual(rc, 0)
        self.assertIn("HAO_DONE", out.getvalue())
        self.assertIn("warning", err.getvalue())

    def test_ask_file_mode_returns_result_path(self):
        def stub(args, machine=None):
            if args[:2] == ["agent", "prompt"]:
                return 0, '{"result":{}}', ""
            if args[:2] == ["agent", "get"]:
                return 1, "", '{"error":{"code":"agent_not_found"}}'
            return self.orig_run(args, machine)

        hao.run_herdr = stub
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            r = hao.cmd_ask("w2:pX", "task", False, "file", None, 60)
        self.assertIn("result_path", r)
        self.assertTrue(r["result_path"].endswith("result.md"))

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
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
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
        with tempfile.TemporaryDirectory() as d:
            shim = os.path.join(d, "herdr")
            with open(shim, "w") as f:
                f.write("#!/bin/sh\nexit 1\n")
            os.chmod(shim, 0o755)
            env = dict(os.environ, PATH=d + ":" + os.environ.get("PATH", ""))
            r = subprocess.run(
                [sys.executable, os.path.join(SKILL_DIR, "scripts", "hao")],
                capture_output=True, text=True, timeout=15, env=env)
        self.assertEqual(r.returncode, 0)
        self.assertIn("usage", r.stdout.lower())

    def test_restore_dry_run_env_workspace(self):
        def stub(args, machine=None):
            if args[:2] == ["agent", "list"]:
                return 0, '{"result":{"agents":[]}}', ""
            if args[:2] == ["pane", "list"]:
                return 0, '{"result":{"panes":[]}}', ""
            return 0, "{}", ""
        env = {"HERDR_WORKSPACE_ID":
               os.environ.get("HERDR_WORKSPACE_ID", "w2")}
        saved = {k: os.environ.get(k) for k in env}
        try:
            os.environ.update(env)
            with mock.patch.object(hao, "run_herdr", side_effect=stub):
                rc = hao.main(["restore", "--dry-run"])
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        self.assertIn(rc, (0, 6))

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
