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
SKILL = os.path.join(HERE, "..", "..", "hao")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
_loader = SourceFileLoader("hao", os.path.join(SKILL, "scripts", "hao"))
hao = types.ModuleType("hao")
_loader.exec_module(hao)
from hao_test_guard import install_offline_guard  # noqa: E402
install_offline_guard(hao)


def run_cli(argv, env=None):
    out, err = io.StringIO(), io.StringIO()
    saved = {k: os.environ.get(k) for k in
             ("HAO_STATE_DIR", "HERDR_PANE_ID")}
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
        hao._WAIT_DIAG = None
    return rc, out.getvalue(), err.getvalue()


class TestZ7NoRecordTimeout(unittest.TestCase):
    def test_sentinel_timeout_says_no_record_was_seen(self):
        with tempfile.TemporaryDirectory() as d:
            state = os.path.join(d, "hao", "tasks")
            with mock.patch.multiple(
                    hao,
                    _agent_status_gate=lambda *a, **k: (None, "idle", {}),
                    _sentinel_check=lambda *a, **k: (None, None),
                    _sentinel_scan_tail=lambda *a, **k: (None, None),
                    _confirm_sentinel=lambda *a, **k: None):
                rc, _out, err = run_cli(
                    ["wait", "w2:p9", "deadbeef0000", "--timeout", "1"],
                    {"HAO_STATE_DIR": state})
            self.assertEqual(rc, 4)
            self.assertIn("no ledger record was ever seen for this task", err)
            self.assertIn("HAO_STATE_DIR", err)
            self.assertIn("only the text sentinel was watched", err)
            self.assertNotIn("since dispatch", err)
            self.assertFalse(os.path.exists(state))

    def test_lifecycle_timeout_says_no_record_was_seen(self):
        with tempfile.TemporaryDirectory() as d:
            state = os.path.join(d, "hao", "tasks")

            def stub(args, machine=None):
                return 0, json.dumps({"result": {"agent": {
                    "agent_status": "idle", "state_change_seq": 0}}}), ""

            with mock.patch.object(hao, "run_herdr", side_effect=stub), \
                    mock.patch.multiple(
                        hao,
                        _sentinel_check=lambda *a, **k: (None, None),
                        _sentinel_scan_tail=lambda *a, **k: (None, None),
                        _confirm_sentinel=lambda *a, **k: None):
                rc, _out, err = run_cli(
                    ["wait", "w2:p9", "deadbeef0000", "--mode", "lifecycle",
                     "--timeout", "1"],
                    {"HAO_STATE_DIR": state})
            self.assertEqual(rc, 4)
            self.assertIn("no ledger record was ever seen for this task", err)
            self.assertIn("HAO_STATE_DIR", err)
            self.assertNotIn("since dispatch", err)
            self.assertFalse(os.path.exists(state))


if __name__ == "__main__":
    unittest.main()
