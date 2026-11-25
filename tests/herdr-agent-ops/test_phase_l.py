import contextlib
import io
import json
import os
import sys
import tempfile
import time
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
from ledger import Ledger, _path  # noqa: E402


def run_cli(argv, env=None):
    out, err = io.StringIO(), io.StringIO()
    saved = {k: os.environ.get(k) for k in ("HAO_STATE_DIR", "HERDR_ENV")}
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


def make_record(sid, status="done", age=0, result=False):
    Ledger().write_running(sid, target="w2:p9")
    if status == "done":
        Ledger().write_done(sid)
    elif status == "cancelled":
        Ledger().cancel(sid)
    rec = json.load(open(_path(sid)))
    rec["status"] = status
    rec["updated"] = time.time() - age
    with open(_path(sid), "w") as f:
        json.dump(rec, f)
    if result:
        d = os.path.join(os.path.dirname(_path(sid)), sid)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "result.md"), "w") as f:
            f.write("x")


class TestL1Clean(unittest.TestCase):
    def test_default_ttl_keeps_fresh_running_and_removes_orphan(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                make_record("aaaa11112222", "done", 0)
                make_record("bbbb11112222", "done", 90000)
                make_record("cccc11112222", "running", 0)
                make_record("dddd11112222", "running", 90000)
                stats = Ledger().cleanup(ttl_s=86400)
                self.assertEqual(stats["removed"], 2)
                self.assertEqual(stats["kept_running"], 1)
                self.assertIsNotNone(Ledger().get("aaaa11112222"))
                self.assertIsNone(Ledger().get("bbbb11112222"))
                self.assertIsNotNone(Ledger().get("cccc11112222"))
                self.assertIsNone(Ledger().get("dddd11112222"))
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_all_removes_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                make_record("aaaa11112222", "done", 0)
                make_record("bbbb11112222", "cancelled", 0)
                stats = Ledger().cleanup(ttl_s=0, all_=True)
                self.assertEqual(stats["removed"], 2)
                self.assertIsNone(Ledger().get("aaaa11112222"))
                self.assertIsNone(Ledger().get("bbbb11112222"))
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_all_keeps_running(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                make_record("cccc11112222", "running", 0)
                make_record("dddd11112222", "running", 90000)
                stats = Ledger().cleanup(ttl_s=0, all_=True)
                self.assertEqual(stats["kept_running"], 2)
                self.assertIsNotNone(Ledger().get("cccc11112222"))
                self.assertIsNotNone(Ledger().get("dddd11112222"))
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_dry_run_does_not_delete(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                make_record("bbbb11112222", "done", 90000, result=True)
                with open(_path("bbbb11112222") + ".lock", "w"):
                    pass
                stats = Ledger().cleanup(ttl_s=86400, dry_run=True)
                self.assertEqual(stats["removed"], 1)
                self.assertEqual(stats["locks_removed"], 1)
                self.assertEqual(stats["dirs_removed"], 1)
                self.assertIsNotNone(Ledger().get("bbbb11112222"))
                self.assertTrue(os.path.exists(_path("bbbb11112222") + ".lock"))
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_clean_collects_orphan_locks_and_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                make_record("bbbb11112222", "done", 90000, result=True)
                with open(_path("bbbb11112222") + ".lock", "w"):
                    pass
                orphan_lock = os.path.join(os.path.dirname(_path("bbbb11112222")),
                                           "cccc11112222.json.lock")
                with open(orphan_lock, "w"):
                    pass
                os.makedirs(os.path.join(os.path.dirname(_path("bbbb11112222")),
                                         "eeee11112222"), exist_ok=True)
                stats = Ledger().cleanup(ttl_s=86400)
                self.assertEqual(stats["removed"], 1)
                self.assertGreaterEqual(stats["locks_removed"], 2)
                self.assertGreaterEqual(stats["dirs_removed"], 2)
                base = os.path.dirname(_path("bbbb11112222"))
                self.assertFalse(os.path.exists(os.path.join(base, "bbbb11112222.json.lock")))
                self.assertFalse(os.path.exists(os.path.join(base, "cccc11112222.json.lock")))
                self.assertFalse(os.path.exists(os.path.join(base, "eeee11112222")))
                self.assertFalse(os.path.exists(base))
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_clean_cli_json(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                make_record("bbbb11112222", "done", 90000)
                rc, out, _ = run_cli(["clean", "--json"],
                                     {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
                self.assertEqual(rc, 0)
                data = json.loads(out)
                self.assertTrue(data["ok"])
                self.assertEqual(data["removed"], 1)
            finally:
                os.environ.pop("HAO_STATE_DIR", None)

    def test_clean_cli_all(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                make_record("aaaa11112222", "done", 0)
                rc, out, _ = run_cli(["clean", "--all", "--json"],
                                     {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks")})
                self.assertEqual(rc, 0)
                self.assertEqual(json.loads(out)["removed"], 1)
                self.assertIsNone(Ledger().get("aaaa11112222"))
            finally:
                os.environ.pop("HAO_STATE_DIR", None)


class TestL2Doctor(unittest.TestCase):
    def test_doctor_runs_cleanup_and_reports_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "hao", "tasks"))
            os.environ["HAO_STATE_DIR"] = os.path.join(d, "hao", "tasks")
            try:
                make_record("bbbb11112222", "done", 90000)
                run = SimpleNamespace(returncode=0, stdout="ok", stderr="")
                with mock.patch.object(hao.subprocess, "run", return_value=run):
                    rc, out, _ = run_cli(["doctor", "--json"],
                                         {"HAO_STATE_DIR": os.path.join(d, "hao", "tasks"), "HERDR_ENV": "1"})
                data = json.loads(out)
                self.assertEqual(rc, 0)
                ledger = next(c for c in data["checks"] if c["name"] == "ledger")
                self.assertEqual(ledger["removed"], 1)
                self.assertIsNone(Ledger().get("bbbb11112222"))
            finally:
                os.environ.pop("HAO_STATE_DIR", None)


if __name__ == "__main__":
    unittest.main()
