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

TOKEN = "hao-" + "aabbccdd" + "eeff0011"
SID = TOKEN[4:16]
TIMEOUT_JSON = '{"error":{"code":"timeout"}}'
PLAIN_TIMEOUT = "timed out after 20s: herdr agent wait"


class Clock:
    def __init__(self):
        self.t = 1000.0

    def time(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


def _repeat(values):
    if isinstance(values, dict):
        values = [values]
    values = list(values)
    def gen():
        yield from values[:-1]
        while True:
            yield values[-1]
    return gen()


class WaitGapCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "hao", "tasks")
        self.env = mock.patch.dict(os.environ, {"HAO_STATE_DIR": self.state})
        self.env.start()
        self.led = Ledger()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()
        hao._ERROR_DETAIL = None

    def sentinel(self, timeout=5, fast=0, gate=None, check=None,
                 scan=None, confirm=None, finish=None, clock=None):
        gate = gate or ((None, "idle", {}),)
        check = check or ((None, None, False),)
        scan = scan or ((None, None),)
        confirm = confirm or (None,)
        finish = finish or {"status": "done"}
        c = clock or Clock()
        with mock.patch.object(hao, "FAST_PATH_SECONDS", fast), \
                mock.patch.object(hao.time, "time", c.time), \
                mock.patch.object(hao.time, "sleep", c.sleep), \
                mock.patch.object(hao, "_agent_status_gate",
                                  side_effect=_repeat(gate)), \
                mock.patch.object(hao, "_sentinel_check",
                                  side_effect=_repeat(check)), \
                mock.patch.object(hao, "_sentinel_scan_tail",
                                  side_effect=_repeat(scan)), \
                mock.patch.object(hao, "_confirm_sentinel",
                                  side_effect=_repeat(confirm)), \
                mock.patch.object(hao, "_finish_sentinel",
                                  side_effect=_repeat(finish)):
            return hao._wait_sentinel("w2:p9", SID, TOKEN, timeout, None,
                                      False, False)


class TestSentinelGaps(WaitGapCase):
    def test_gate_blocked_sets_hint_and_returns_5(self):
        with mock.patch.object(hao, "_set_blocked_hint") as hint:
            rc = self.sentinel(gate=((5, "blocked", {}),),
                               scan=((None, None),))
        self.assertEqual(rc, 5)
        hint.assert_called_once()

    def test_gate_3_prescan_finds_sentinel(self):
        result = self.sentinel(gate=((3, "exited", {}),),
                               scan=(("HAO_DONE line", None),),
                               finish=({"status": "done", "matched_line": "x"},))
        self.assertEqual(result["status"], "done")

    def test_gate_9_unknown_and_gate_8(self):
        self.assertEqual(self.sentinel(gate=((9, "unknown", {}),)), 9)
        self.assertEqual(self.sentinel(gate=((8, "unknown", {}),)), 8)

    def test_validated_sentinel_completes_on_later_gate(self):
        result = self.sentinel(
            fast=30,
            gate=((None, "idle", {}), (3, "exited", {})),
            check=(("HAO_DONE line", None, False),),
            confirm=(None,),
            scan=((None, None),),
            finish=({"status": "done", "via": "validated"},))
        self.assertEqual(result["via"], "validated")

    def test_working_agent_wait_plain_timeout_is_8(self):
        def fake(args, machine=None):
            return 1, "", PLAIN_TIMEOUT
        with mock.patch.object(hao, "run_herdr", side_effect=fake), \
                mock.patch.object(hao, "_agent_status_gate",
                                  return_value=(None, "working", {})):
            rc = hao._wait_sentinel("w2:p9", SID, TOKEN, 5, None, False, False)
        self.assertEqual(rc, 8)

    def test_working_agent_wait_timeout_reaches_deadline(self):
        clock = Clock()
        def fake(args, machine=None):
            clock.t += 2
            return 1, "", TIMEOUT_JSON
        with mock.patch.object(hao, "run_herdr", side_effect=fake), \
                mock.patch.object(hao, "_agent_status_gate",
                                  return_value=(None, "working", {})), \
                mock.patch.object(hao.time, "time", clock.time), \
                mock.patch.object(hao.time, "sleep", clock.sleep):
            rc = hao._wait_sentinel("w2:p9", SID, TOKEN, 5, None, False, False)
        self.assertEqual(rc, 4)

    def test_backstop_scan_hit_confirms(self):
        def fake(args, machine=None):
            return 0, "{}", ""
        result = self.sentinel(fast=0, gate=((None, "idle", {}),),
                               scan=(("HAO_DONE line", None),),
                               confirm=("HAO_DONE line",),
                               finish=({"status": "done"},))
        self.assertEqual(result["status"], "done")

    def test_backstop_scan_error(self):
        self.assertEqual(self.sentinel(fast=0, scan=((None, 8),)), 8)

    def test_backstop_scan_miss_times_out(self):
        rc = self.sentinel(fast=0, timeout=2, scan=((None, None),))
        self.assertEqual(rc, 4)


def lifecycle_wait(clock, timeout=10, gate=None, check=None, scan=None,
                   confirm=None, finish=None, run=None):
    gate = gate or ((None, "idle", {"state_change_seq": 0}),)
    check = check or ((None, None, False),)
    scan = scan or ((None, None),)
    confirm = confirm or (None,)
    finish = finish or {"status": "done"}
    with mock.patch.object(hao, "_agent_status_gate",
                           side_effect=_repeat(gate)), \
            mock.patch.object(hao, "_sentinel_check",
                              side_effect=_repeat(check)), \
            mock.patch.object(hao, "_sentinel_scan_tail",
                              side_effect=_repeat(scan)), \
            mock.patch.object(hao, "_confirm_sentinel",
                              side_effect=_repeat(confirm)), \
            mock.patch.object(hao, "_finish_sentinel",
                              side_effect=_repeat(finish)), \
            mock.patch.object(hao.time, "time", clock.time), \
            mock.patch.object(hao.time, "sleep", clock.sleep):
        if run is not None:
            with mock.patch.object(hao, "run_herdr", side_effect=run):
                return hao._wait_lifecycle("w2:p9", SID, TOKEN, timeout,
                                           None, False, False)
        return hao._wait_lifecycle("w2:p9", SID, TOKEN, timeout, None,
                                   False, False)


class TestLifecycleGaps(WaitGapCase):
    def test_unknown_exits_6(self):
        self.assertEqual(lifecycle_wait(Clock(), gate=((None, "unknown", {}),)),
                         6)

    def test_no_activity_exits_9(self):
        rc = lifecycle_wait(Clock(), timeout=20,
                            gate=((None, "idle", {"state_change_seq": 0}),),
                            check=((None, None, False),),
                            scan=((None, None),))
        self.assertEqual(rc, 9)

    def test_sentinel_check_error_and_scan_error(self):
        self.assertEqual(lifecycle_wait(Clock(),
                                        check=((None, 8, False),)), 8)
        self.assertEqual(lifecycle_wait(Clock(),
                                        scan=((None, 8),)), 8)

    def test_ml_confirm_and_scan_confirm(self):
        result = lifecycle_wait(
            Clock(), gate=((None, "working", {"state_change_seq": 1}),),
            check=(("line", None, False),), confirm=("line",),
            finish=({"status": "done", "via": "ml"},))
        self.assertEqual(result["via"], "ml")
        result = lifecycle_wait(
            Clock(), gate=((None, "working", {"state_change_seq": 1}),),
            check=((None, None, False),), scan=(("line", None),),
            confirm=("line",), finish=({"status": "done", "via": "scan"},))
        self.assertEqual(result["via"], "scan")

    def test_agent_wait_plain_timeout_is_8(self):
        rc = lifecycle_wait(
            Clock(), gate=((None, "working", {"state_change_seq": 1}),),
            run=lambda args, machine=None: (1, "", PLAIN_TIMEOUT))
        self.assertEqual(rc, 8)


class TestWaitHelpersGaps(WaitGapCase):
    def test_wait_round_rec_degrades(self):
        class Bad:
            def heartbeat(self, sid):
                raise RuntimeError("lock")
            def get(self, sid):
                raise RuntimeError("read")
        self.assertEqual(hao._wait_round_rec(Bad(), SID), {})

        class GetOnly:
            def heartbeat(self, sid):
                raise RuntimeError("lock")
            def get(self, sid):
                return {"status": "running"}
        self.assertEqual(hao._wait_round_rec(GetOnly(), SID),
                         {"status": "running"})

    def test_record_gone_and_consumed(self):
        class Bad:
            def get(self, sid):
                raise RuntimeError("read")
        self.assertFalse(hao._wait_record_gone(Bad(), SID))
        self.assertFalse(hao._wait_consumed(Bad(), SID, True))
        class Gone:
            def get(self, sid):
                return None
        self.assertTrue(hao._wait_consumed(Gone(), SID, True))
        self.assertIn("already consumed", hao._ERROR_DETAIL)

    def test_agent_status_gate_errors(self):
        with mock.patch.object(hao, "run_herdr",
                               return_value=(1, "", '{"error":{"code":"agent_not_found"}}')):
            self.assertEqual(hao._agent_status_gate("w2:p9", None, False, False)[0], 3)
        with mock.patch.object(hao, "run_herdr",
                               return_value=(1, "", '{"error":{"code":"server"}}')):
            self.assertEqual(hao._agent_status_gate("w2:p9", None, False, False)[0], 8)
        with mock.patch.object(hao, "run_herdr",
                               return_value=(0, "not json", "")):
            self.assertEqual(hao._agent_status_gate("w2:p9", None, False, False)[0], 8)
        with mock.patch.object(hao, "run_herdr",
                               return_value=(0, '{"result":{"agent":'
                                                '{"agent_status":"unknown"}}}', "")):
            gate = hao._agent_status_gate("w2:p9", None, False, False)
        self.assertEqual(gate[0], 9)

    def test_sentinel_scan_tail_errors(self):
        with mock.patch.object(hao, "run_herdr",
                               return_value=(1, "", '{"error":{"code":"server"}}')):
            self.assertEqual(hao._sentinel_scan_tail("w2:p9", TOKEN, SID,
                                                     None)[1], 8)
        with mock.patch.object(hao, "run_herdr",
                               return_value=(0, "plain text", "")):
            last, err = hao._sentinel_scan_tail("w2:p9", TOKEN, SID, None)
        self.assertIsNone(last)
        self.assertIsNone(err)

    def test_confirm_sentinel_branches(self):
        seq = iter([(1, "", ""), (0, '{"result":{"agent":{"agent_status":"idle"}}}', "")])
        with mock.patch.object(hao, "run_herdr", side_effect=[(0, '{"result":{"agent":{"agent_status":"working"}}}', "")]):
            self.assertIsNone(hao._confirm_sentinel("w2:p9", TOKEN, SID, None, False))
        with mock.patch.object(hao, "run_herdr",
                               return_value=(1, "", "boom")):
            self.assertIsNone(hao._confirm_sentinel("w2:p9", TOKEN, SID, None, False))
        with mock.patch.object(hao, "run_herdr",
                               return_value=(0, "not json", "")):
            self.assertIsNone(hao._confirm_sentinel("w2:p9", TOKEN, SID, None, False))


class TestWaitFileGaps(WaitGapCase):
    def test_timeout_and_blocked_and_exited(self):
        def stub(status):
            def fake(args, machine=None):
                if args[:2] == ["agent", "get"]:
                    return 0, json.dumps({"result": {"agent": {
                        "agent_status": status}}}), ""
                return 0, "{}", ""
            return fake
        with mock.patch.object(hao, "run_herdr", side_effect=stub("idle")), \
                mock.patch.object(hao.time, "sleep", return_value=None):
            self.assertEqual(hao._wait_file("w2:p9", SID, TOKEN, 0.01, None), 4)
        with mock.patch.object(hao, "run_herdr", side_effect=stub("blocked")):
            self.assertEqual(hao._wait_file("w2:p9", SID, TOKEN, 5, None), 5)
        with mock.patch.object(hao, "run_herdr", side_effect=stub("exited")):
            self.assertEqual(hao._wait_file("w2:p9", SID, TOKEN, 5, None), 3)

    def test_no_agent_existing_pane_keeps_waiting(self):
        def fake(args, machine=None):
            if args[:2] == ["agent", "get"]:
                return 1, "", '{"error":{"code":"agent_not_found"}}'
            if args[:2] == ["pane", "get"]:
                return 0, '{"result":{"pane":{}}}', ""
            return 0, "{}", ""
        with mock.patch.object(hao, "run_herdr", side_effect=fake), \
                mock.patch.object(hao.time, "sleep", return_value=None):
            self.assertEqual(hao._wait_file("w2:p9", SID, TOKEN, 0.01, None), 4)

    def test_record_gone_returns_3(self):
        with mock.patch.object(hao, "_wait_round_rec",
                               side_effect=_repeat([{"status": "running"}, {}])), \
                mock.patch.object(hao, "_wait_consumed",
                                  side_effect=_repeat([False, True])), \
                mock.patch.object(hao, "run_herdr",
                                  return_value=(0, '{"result":{"agent":'
                                                   '{"agent_status":"idle"}}}', "")), \
                mock.patch.object(hao.time, "sleep", return_value=None):
            rc = hao._wait_file("w2:p9", SID, TOKEN, 5, None)
        self.assertEqual(rc, 3)

    def test_done_and_cancelled_payloads(self):
        with mock.patch.object(hao, "_wait_round_rec",
                               return_value={"status": "done",
                                             "summary": "ok"}):
            r = hao._wait_file("w2:p9", SID, TOKEN, 5, None)
        self.assertEqual(r["summary"], "ok")
        with mock.patch.object(hao, "_wait_round_rec",
                               return_value={"status": "cancelled"}):
            self.assertEqual(hao._wait_file("w2:p9", SID, TOKEN, 5, None), 10)

    def test_invalid_agent_json_and_unreadable_result(self):
        def fake(args, machine=None):
            if args[:2] == ["agent", "get"]:
                return 0, '{"result":{}}', ""
            return 0, "{}", ""
        with mock.patch.object(hao, "run_herdr", side_effect=fake), \
                mock.patch.object(hao.time, "sleep", return_value=None):
            self.assertEqual(hao._wait_file("w2:p9", SID, TOKEN, 0.01, None), 4)

        rp = os.path.join(self.state, SID, "result.md")
        os.makedirs(os.path.dirname(rp), exist_ok=True)
        with open(rp, "w") as f:
            f.write("body")
        self.led.write_running(SID, result_path=rp)
        with mock.patch.object(hao, "run_herdr", side_effect=fake), \
                mock.patch.object(hao, "safe_read", return_value=None):
            r = hao._wait_file("w2:p9", SID, TOKEN, 5, None)
        self.assertIn("tail_note", r)

    def test_stable_file_write_failures_still_complete(self):
        rp = os.path.join(self.state, SID, "result.md")
        os.makedirs(os.path.dirname(rp), exist_ok=True)
        with open(rp, "w") as f:
            f.write("body")
        self.led.write_running(SID, result_path=rp)
        with mock.patch.object(hao, "run_herdr",
                               return_value=(0, '{"result":{"agent":'
                                                '{"agent_status":"done"}}}', "")), \
                mock.patch.object(hao.Ledger if hasattr(hao, "Ledger") else Ledger,
                                  "write_done", side_effect=RuntimeError("x")), \
                mock.patch.object(Ledger, "consume", side_effect=RuntimeError("y")):
            r = hao._wait_file("w2:p9", SID, TOKEN, 5, None)
        self.assertEqual(r["tail"], "body")


if __name__ == "__main__":
    unittest.main()
