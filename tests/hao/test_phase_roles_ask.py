import unittest, types, os, json, tempfile
from importlib.machinery import SourceFileLoader
from hao_test_guard import install_offline_guard
_l = SourceFileLoader("hao", os.path.join(os.path.dirname(__file__), "..", "..", "hao", "scripts", "hao"))
hao = types.ModuleType("hao"); _l.exec_module(hao)
install_offline_guard(hao)

FULL = "以下完成上报是协议步骤"
TOK = "hao-" + "aabbccdd" + "eeff0011"
FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def golden(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


def prompt(tier, text_only=False, max_lines=None):
    p = hao.build_prompt("评审这个方案", TOK, text_only=text_only, tier=tier, max_lines=max_lines)
    return p.replace(hao.hao_command(), "<HAO>")


class TestTierBriefs(unittest.TestCase):
    def test_top_is_compact_and_capped(self):
        p = prompt("top")
        self.assertNotIn(FULL, p)
        self.assertIn("正文不超过 15 行", p)
        self.assertLess(len(p), len(prompt("low")))

    def test_mid_is_full_with_cap(self):
        p = prompt("mid")
        self.assertIn(FULL, p)
        self.assertIn("不超过 40 行", p)

    def test_low_and_unknown_match_the_golden_prompts(self):
        self.assertEqual(prompt("low"), golden("prompt_low.golden"))
        self.assertEqual(prompt(None), golden("prompt_low.golden"))
        self.assertEqual(prompt("low", text_only=True), golden("prompt_low_text_only.golden"))
        self.assertNotIn("不超过", prompt("low"))

    def test_max_lines_overrides_and_zero_means_unlimited(self):
        self.assertIn("不超过 5 行", prompt("top", max_lines=5))
        self.assertIn("不超过 5 行", prompt("low", max_lines=5))
        self.assertNotIn("不超过", prompt("top", max_lines=0))
        self.assertEqual(prompt("low", max_lines=0), golden("prompt_low.golden"))

    def test_compact_keeps_sentinel_before_done_command(self):
        p = prompt("top")
        self.assertLess(p.index("HAO_DONE"), p.index("done --token"))

    def test_compact_respects_text_only(self):
        p = prompt("top", text_only=True)
        self.assertNotIn("done --token", p)
        self.assertIn("HAO_DONE", p)

    def test_echo_guard_holds_for_every_template(self):
        for tier in ("top", "mid", "low", None):
            self.assertNotIn(TOK, prompt(tier))

    def test_ask_reports_role_tier_and_cap(self):
        sent = {}
        def fake(args, machine=None):
            a = " ".join(args[:2])
            if a == "pane layout":
                return 1, "", '{"error":{"code":"pane_not_found"}}'
            if a == "agent get":
                return 0, '{"result":{"agent":{"agent_status":"idle","state_change_seq":1}}}', ""
            if a == "pane get":
                return 0, '{"result":{"pane":{"pane_id":"w2:p9","label":"hao-moth-arbiter"}}}', ""
            if a == "agent prompt":
                sent["prompt"] = args[-1]
                return 0, '{"result":{}}', ""
            return 0, '{"result":{}}', ""
        hao.run_herdr = fake
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = d
            out = hao.cmd_ask("w2:p9", "定夺方案", False, "sentinel", None, 30)
            out7 = hao.cmd_ask("w2:p9", "定夺方案", False, "sentinel", None, 30, max_lines=7)
            bad = hao.cmd_ask("w2:p9", "定夺方案", False, "sentinel", None, 30, max_lines=-1)
        os.environ.pop("HAO_STATE_DIR", None)
        self.assertEqual((out["role"], out["tier"], out["max_lines"]), ("arbiter", "top", 15))
        self.assertEqual((out7["tier"], out7["max_lines"]), ("top", 7))
        self.assertNotIn(FULL, sent["prompt"])
        self.assertEqual(bad, 2)

    def test_ask_to_unroled_target_reports_nulls(self):
        def fake(args, machine=None):
            a = " ".join(args[:2])
            if a == "pane layout":
                return 1, "", '{"error":{"code":"pane_not_found"}}'
            if a == "agent get":
                return 0, '{"result":{"agent":{"agent_status":"idle","state_change_seq":1}}}', ""
            if a == "pane get":
                return 0, '{"result":{"pane":{"pane_id":"w2:p9","label":"hao-verse"}}}', ""
            return 0, '{"result":{}}', ""
        hao.run_herdr = fake
        with tempfile.TemporaryDirectory() as d:
            os.environ["HAO_STATE_DIR"] = d
            out = hao.cmd_ask("w2:p9", "做这件事", False, "sentinel", None, 30)
        os.environ.pop("HAO_STATE_DIR", None)
        self.assertEqual((out["role"], out["tier"], out["max_lines"]), (None, None, None))


if __name__ == "__main__":
    unittest.main()
