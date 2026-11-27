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
from ledger import Ledger  # noqa: E402


class LifecycleSettleCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "hao", "tasks")
        self.env = mock.patch.dict(os.environ,
                                   {"HAO_STATE_DIR": self.state})
        self.env.start()
        self.sleeps = []

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def _stub(self, statuses):
        """statuses: agent_get results in order; last repeats."""
        calls = {"get": 0, "prompt": 0}
        def fake(args, machine=None):
            if args[:2] == ["agent", "get"]:
                idx = min(calls["get"], len(statuses) - 1)
                calls["get"] += 1
                st, seq = statuses[idx]
                return 0, json.dumps({"result": {"agent": {
                    "agent_status": st, "state_change_seq": seq}}}), ""
            if args[:2] == ["agent", "prompt"]:
                calls["prompt"] += 1
                return 0, '{"result":{}}', ""
            if args[:2] == ["pane", "layout"]:
                return 1, "", '{"error":{"code":"pane_not_found"}}'
            if args[:2] == ["pane", "get"]:
                return 0, '{"result":{"pane":{"pane_id":"w2:p9",' \
                          '"label":"hao-moth-developer"}}}', ""
            return 0, '{"result":{}}', ""
        return fake, calls

    def _ask(self, statuses, mode="lifecycle"):
        fake, calls = self._stub(statuses)
        with mock.patch.object(hao, "run_herdr", side_effect=fake), \
                mock.patch.object(hao, "cmd_wait",
                                  return_value={"status": "done"}), \
                mock.patch.object(hao.time, "sleep",
                                  side_effect=self.sleeps.append):
            rc = hao.cmd_ask("w2:p9", "task", True, mode, None, 30)
        return rc, calls

    def _record(self):
        recs = [f for f in os.listdir(self.state) if f.endswith(".json")]
        with open(os.path.join(self.state, recs[0])) as f:
            return json.load(f)


class TestLifecycleSettle(LifecycleSettleCase):
    def test_working_then_idle_dispatches_after_resnapshot(self):
        rc, calls = self._ask([("working", 1), ("working", 2),
                               ("working", 3), ("idle", 4)])
        self.assertIsInstance(rc, dict)
        self.assertEqual(calls["prompt"], 1)
        self.assertEqual(self._record()["submit_seq"], 4)
        self.assertGreaterEqual(len(self.sleeps), 3)

    def test_always_working_exits_6(self):
        with mock.patch.object(hao, "LIFECYCLE_SETTLE_SECONDS", 0.02):
            rc, calls = self._ask([("working", 1)])
        self.assertEqual(rc, 6)
        self.assertIn("needs an idle agent", hao._ERROR_DETAIL)
        self.assertEqual(calls["prompt"], 0)
        hao._ERROR_DETAIL = None

    def test_blocked_exits_6_without_settle_polling(self):
        rc, calls = self._ask([("blocked", 1)])
        self.assertEqual(rc, 6)
        self.assertIn("needs an idle agent", hao._ERROR_DETAIL)
        self.assertEqual(self.sleeps, [])
        self.assertEqual(calls["prompt"], 0)
        hao._ERROR_DETAIL = None

    def test_unknown_exits_6_without_settle_polling(self):
        rc, calls = self._ask([("unknown", 1)])
        self.assertEqual(rc, 6)
        self.assertIn("needs an idle agent", hao._ERROR_DETAIL)
        self.assertEqual(self.sleeps, [])
        self.assertEqual(calls["prompt"], 0)
        hao._ERROR_DETAIL = None

    def test_sentinel_mode_dispatches_to_working_peer_immediately(self):
        rc, calls = self._ask([("working", 1)], mode="sentinel")
        self.assertIsInstance(rc, dict)
        self.assertEqual(calls["prompt"], 1)
        self.assertEqual(self.sleeps, [])


if __name__ == "__main__":
    unittest.main()
