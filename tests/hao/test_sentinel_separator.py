import json
import os
import sys
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

SID = "5e1f0a2b3c4d"
TOKEN = "hao-" + "5e1f0a2b" + "3c4d9a7b"
SPLIT = "hao-" + "5e1f0a2b" + "-" + "3c4d9a7b"


def pane_read(text):
    return 0, json.dumps({"result": {"read": {"text": text}}}), ""


class TestRejoinSplitToken(unittest.TestCase):
    def test_only_the_hyphen_joined_shape_is_rewritten(self):
        good = [
            f"HAO_DONE {SPLIT}",
            "HAO_DONE 5e1f0a2b-3c4d9a7b",
            f"⏺ HAO_DONE {SPLIT}",
            f"│ HAO_DONE {SPLIT} │",
            f"HAO_DONE {SPLIT} ┃",
            f"HAO_DONE {SPLIT} 。",
        ]
        for line in good:
            with self.subTest(line=line):
                self.assertEqual(hao._rejoin_split_token(line),
                                 line.replace("-3c4d9a7b",
                                              "3c4d9a7b", 1))
        bad = [
            f"HAO_DONE hao-5e1f0a2b 3c4d9a7b",
            f"HAO_DONE hao-5e1f0a2b_3c4d9a7b",
            f"HAO_DONE hao-5e1f0a2b–3c4d9a7b",
            f"HAO_DONE hao-5e1f0a2b—3c4d9a7b",
            f"HAO_DONE hao-5e1f0a2b..3c4d9a7b",
            f"HAO_DONE hao-5e1f0a2b--3c4d9a7b",
            "HAO_DONE " + "5e1f0a2b" + "3c4d9a7b" + "-00000000",
            f"HAO_DONE hao-5e1f0a-3c4d9a7b",
            f"HAO_DONE hao-5e1f0a2b-3c4d9a7",
        ]
        for line in bad:
            with self.subTest(line=line):
                self.assertEqual(hao._rejoin_split_token(line), line)


class TestIdentityUnchanged(unittest.TestCase):
    def _scan(self, text, token=TOKEN):
        with mock.patch.object(hao, "run_herdr",
                               return_value=pane_read(text)):
            return hao._sentinel_scan_tail("w2:p9", token, SID, None)[0]

    def test_current_split_token_is_accepted(self):
        line = f"HAO_DONE {SPLIT}"
        self.assertEqual(self._scan("answer\n" + line), line)

    def test_wrong_second_half_is_rejected(self):
        line = "HAO_DONE hao-5e1f0a2b-3c4dffff"
        self.assertIsNone(self._scan(line))

    def test_other_task_split_token_is_rejected(self):
        line = "HAO_DONE hao-11111111-22222222"
        self.assertIsNone(self._scan(line))

    def test_space_separated_halves_are_rejected(self):
        line = "HAO_DONE hao-5e1f0a2b 3c4d9a7b"
        self.assertIsNone(self._scan(line))


class TestFastPath(unittest.TestCase):
    def _check(self, matched, token=TOKEN):
        calls = []

        def fake(args, machine=None):
            calls.append(list(args))
            return 0, json.dumps({"result": {"matched_line": matched}}), ""
        with mock.patch.object(hao, "run_herdr", side_effect=fake):
            result = hao._sentinel_check("w2:p9", token, SID, None)
        return result, calls

    def test_current_split_token_is_accepted_with_raw_line(self):
        raw = "HAO_DONE " + SPLIT
        result, calls = self._check(raw)
        self.assertEqual(result, (raw, None, False))
        self.assertEqual(calls[0][4], hao.SENTINEL_RE_WIDE.pattern)

    def test_other_task_split_token_is_stale(self):
        result, _ = self._check("HAO_DONE hao-11111111-22222222")
        self.assertEqual(result, (None, None, True))


class TestEndToEnd(unittest.TestCase):
    def test_cmd_wait_accepts_split_sentinel_and_keeps_raw_evidence(self):
        raw = "HAO_DONE " + SPLIT
        read_text = "answer\n" + raw

        def fake(args, machine=None):
            if args[:2] == ["agent", "get"]:
                return 0, json.dumps({"result": {"agent": {
                    "agent_status": "done"}}}), ""
            if args[:2] == ["pane", "wait-output"]:
                return 0, json.dumps({"result": {
                    "matched_line": raw}}), ""
            if args[:2] == ["pane", "read"]:
                return pane_read(read_text)
            return 0, "{}", ""
        with mock.patch.object(hao, "run_herdr", side_effect=fake), \
                mock.patch.object(hao.time, "sleep", return_value=None):
            result = hao.cmd_wait("w2:p9", TOKEN, 5)
        self.assertEqual(result["status"], "done")
        self.assertEqual(result["matched_line"], raw)
        self.assertEqual(result["tail"], "answer")


class TestLedgerDegraded(unittest.TestCase):
    def test_16_hex_split_is_rejected_without_full_token(self):
        text = "HAO_DONE " + SPLIT
        with mock.patch.object(hao, "run_herdr",
                               return_value=pane_read(text)):
            last, err = hao._sentinel_scan_tail("w2:p9", None, SID, None)
        self.assertIsNone(last)
        self.assertIsNone(err)


class TestWidePattern(unittest.TestCase):
    def test_wide_is_a_strict_superset_for_these_samples(self):
        samples = [
            "HAO_DONE hao-5e1f0a2b3c4d",
            "HAO_DONE 5e1f0a2b3c4d",
            "HAO_DONE hao-5e1f0a2b3c4d9a7b",
            "HAO_DONE hao-" + "a" * 32,
            "⏺ HAO_DONE hao-5e1f0a2b3c4d │",
            "│ HAO_DONE 5e1f0a2b3c4d ┃",
            "打印：HAO_DONE hao-5e1f0a2b3c4d",
            "hao-5e1f0a2b3c4d",
            "HAO_DONE hao-5e1f0a2b 3c4d9a7b",
            "HAO_DONE hao-5e1f0a2b_3c4d9a7b",
        ]
        for line in samples:
            with self.subTest(line=line):
                self.assertEqual(bool(hao.SENTINEL_RE.match(line)),
                                 bool(hao.SENTINEL_RE_WIDE.match(line)))
        split = "HAO_DONE " + SPLIT
        self.assertIsNone(hao.SENTINEL_RE.match(split))
        self.assertIsNotNone(hao.SENTINEL_RE_WIDE.match(split))

    def test_wide_pattern_is_rust_regex_safe(self):
        pattern = hao.SENTINEL_RE_WIDE.pattern
        for forbidden in ("(?=", "(?<=", "(?<!", "\\1"):
            self.assertNotIn(forbidden, pattern)


if __name__ == "__main__":
    unittest.main()
