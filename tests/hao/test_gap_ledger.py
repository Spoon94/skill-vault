import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(__file__)
SKILL = os.path.join(HERE, "..", "..", "hao")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
import ledger as led  # noqa: E402
from hao_test_guard import install_offline_guard  # noqa: E402
from importlib.machinery import SourceFileLoader  # noqa: E402

_loader = SourceFileLoader("hao", os.path.join(SKILL, "scripts", "hao"))
import types  # noqa: E402
hao = types.ModuleType("hao")
_loader.exec_module(hao)
install_offline_guard(hao)


class LedgerGapCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "hao", "tasks")
        self.env = mock.patch.dict(os.environ, {"HAO_STATE_DIR": self.state})
        self.env.start()
        self.l = led.Ledger()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()


class TestLedgerGaps(LedgerGapCase):
    def test_done_is_never_downgraded(self):
        self.l.write_done("abcd12345678", summary="ok")
        self.l.write_running("abcd12345678", target="w2:p9")
        rec = self.l.get("abcd12345678")
        self.assertEqual(rec["status"], "done")
        self.assertNotIn("target", rec)

    def test_rw_missing_base_and_record(self):
        self.assertIsNone(self.l.write_done("abcd12345678", create=False))
        os.makedirs(self.state)
        self.assertIsNone(self.l.write_done("abcd12345678", create=False))

    def test_chmod_failure_is_tolerated(self):
        real = os.chmod
        def chmod(path, mode):
            if str(path).endswith(".lock"):
                raise OSError("no")
            return real(path, mode)
        with mock.patch.object(led.os, "chmod", side_effect=chmod):
            rec = self.l.write_running("abcd12345678", target="w2:p9")
        self.assertEqual(rec["status"], "running")

    def test_lock_timeout_raises(self):
        clock = [1000.0]
        def now():
            clock[0] += 0.1
            return clock[0]
        with mock.patch.object(led.fcntl, "flock", side_effect=OSError("busy")), \
                mock.patch.object(led.time, "time", side_effect=now), \
                mock.patch.object(led.time, "sleep", return_value=None):
            with self.assertRaises(TimeoutError):
                self.l.write_running("abcd12345678", target="w2:p9")

    def test_cancel_done_and_missing(self):
        self.assertEqual(self.l.cancel("abcd12345678"), 3)
        self.l.write_done("abcd12345678", summary="ok")
        self.assertEqual(self.l.cancel("abcd12345678"), 6)

    def test_mark_interrupted(self):
        self.l.write_running("abcd12345678", target="w2:p9")
        self.l.cancel("abcd12345678")
        self.l.mark_interrupted("abcd12345678")
        self.assertTrue(self.l.get("abcd12345678")["interrupted"])

    def test_consume_keep_and_no_lock(self):
        self.l.write_running("abcd12345678", target="w2:p9")
        self.assertFalse(self.l.consume("abcd12345678", keep_result=True))
        self.assertTrue(os.path.exists(led._path("abcd12345678")))
        os.remove(led._path("abcd12345678") + ".lock")
        self.assertTrue(self.l.consume("abcd12345678"))
        self.assertFalse(os.path.exists(led._path("abcd12345678")))

    def test_consume_lock_timeout_still_removes(self):
        self.l.write_running("abcd12345678", target="w2:p9")
        clock = [1000.0]
        def now():
            clock[0] += 10
            return clock[0]
        with mock.patch.object(led.fcntl, "flock", side_effect=OSError("busy")), \
                mock.patch.object(led.time, "time", side_effect=now), \
                mock.patch.object(led.time, "sleep", return_value=None):
            self.l.consume("abcd12345678")
        self.assertFalse(os.path.exists(led._path("abcd12345678")))

    def test_tidy_removes_orphans_and_empty_tree(self):
        os.makedirs(self.state)
        open(os.path.join(self.state, "abc.json.lock"), "w").close()
        os.makedirs(os.path.join(self.state, "abc"))
        open(os.path.join(self.state, ".cleanup.lock"), "w").close()
        self.l.tidy()
        self.assertFalse(os.path.exists(self.state))
        self.assertFalse(os.path.exists(os.path.dirname(self.state)))

    def test_cleanup_dry_run_and_categories(self):
        self.l.write_running("abcd12345678", target="w2:p9")
        self.l.write_done("deadbeef0000")
        self.l.cancel("cafebabe0000")
        stats = self.l.cleanup(ttl_s=0, dry_run=True, all_=True,
                               is_running=lambda rec: True)
        self.assertGreaterEqual(stats["removed"], 1)
        stats = self.l.cleanup(ttl_s=0, all_=True,
                               is_running=lambda rec: True)
        self.assertGreaterEqual(stats["removed"], 1)

    def test_cleanup_unreadable_peer_keeps_running(self):
        self.l.write_running("abcd12345678", target="w2:p9")
        def boom(rec):
            raise RuntimeError("unreadable")
        stats = self.l.cleanup(ttl_s=0, all_=True, is_running=boom)
        self.assertEqual(stats["kept_running"], 1)

    def test_cleanup_missing_base_and_bad_json(self):
        self.assertEqual(self.l.cleanup()["removed"], 0)
        os.makedirs(self.state)
        with open(os.path.join(self.state, "bad.json"), "w") as f:
            f.write("not json")
        self.assertEqual(self.l.cleanup(ttl_s=0)["removed"], 0)

    def test_tidy_cancelled_categories(self):
        self.l.write_running("abcd12345678", target="w2:p9")
        self.l.cancel("abcd12345678")
        self.assertEqual(self.l.tidy_cancelled(lambda r: True, max_age=99999), 0)
        self.assertEqual(self.l.tidy_cancelled(lambda r: False, max_age=99999), 1)


if __name__ == "__main__":
    unittest.main()
