import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "herdr-agent-ops", "scripts"))
import os
import tempfile
from ledger import Ledger


class TestLockTimeout(unittest.TestCase):
    def test_rw_times_out_on_held_lock(self):
        # r7#3: flock must not block indefinitely; waiter degrades instead
        import fcntl
        import time
        from ledger import _path
        with tempfile.TemporaryDirectory() as d:
            os.environ["XDG_STATE_HOME"] = d
            try:
                l = Ledger()
                l.write_running("aabb11223344")
                with open(_path("aabb11223344") + ".lock", "w") as lf:
                    fcntl.flock(lf, fcntl.LOCK_EX)
                    t0 = time.time()
                    with self.assertRaises(TimeoutError):
                        l._rw("aabb11223344", lambda rec: None, lock_timeout=0.3)
                    self.assertLess(time.time() - t0, 3)
                    # lock-free get still works while the lock is held
                    self.assertEqual(l.get("aabb11223344")["status"], "running")
            finally:
                os.environ.pop("XDG_STATE_HOME", None)


class TestLedger(unittest.TestCase):
    def test_done_tombstone(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["XDG_STATE_HOME"] = d
            l = Ledger()
            l.write_done("abc123", result_path="/tmp/r.md", summary="ok")
            rec = l.get("abc123")
            self.assertEqual(rec["status"], "done")
            self.assertEqual(rec["result_path"], "/tmp/r.md")

    def test_heartbeat_only_updates_updated(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["XDG_STATE_HOME"] = d
            l = Ledger()
            l.write_done("abc123", summary="s")
            before = l.get("abc123")["status"]
            l.heartbeat("abc123")
            self.assertEqual(l.get("abc123")["status"], before)

    def test_cancel_running_vs_done(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["XDG_STATE_HOME"] = d
            l = Ledger()
            l.write_running("run1")
            self.assertEqual(l.cancel("run1"), 0)
            l.write_done("done1")
            self.assertEqual(l.cancel("done1"), 6)

    def test_cleanup_terminal_only(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["XDG_STATE_HOME"] = d
            l = Ledger()
            l.write_done("done1")
            # age done1's record to make it stale
            import json, time
            from ledger import _path
            rec = json.load(open(_path("done1")))
            rec["updated"] = time.time() - 5000
            with open(_path("done1"), "w") as f:
                json.dump(rec, f)
            l.write_running("run1")
            l.heartbeat("run1")  # fresh heartbeat -> active running
            l.cleanup(ttl_s=1000)
            self.assertIsNone(l.get("done1"))     # terminal+stale cleaned
            self.assertIsNotNone(l.get("run1"))   # active running kept


if __name__ == "__main__":
    unittest.main()
