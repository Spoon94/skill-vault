import unittest, types, os
from importlib.machinery import SourceFileLoader
from hao_test_guard import install_offline_guard
_l = SourceFileLoader("hao", os.path.join(os.path.dirname(__file__), "..", "..", "hao", "scripts", "hao"))
hao = types.ModuleType("hao"); _l.exec_module(hao)
install_offline_guard(hao)
_n = SourceFileLoader("hao_names", os.path.join(os.path.dirname(__file__), "..", "..", "hao", "scripts", "names.py"))
names = types.ModuleType("hao_names"); _n.exec_module(names)


class TestRoles(unittest.TestCase):
    def test_catalog_has_27_roles_in_three_tiers(self):
        self.assertEqual(len(names.ROLES), 27)
        self.assertEqual({r["tier"] for r in names.ROLES.values()}, {"top", "mid", "low"})

    def test_every_role_is_well_formed_and_not_a_lexicon_name(self):
        lex = {n for g in names.NAMES.values() for n in g["names"]}
        groups = {"决策", "协调", "设计评审", "实施", "支撑"}
        for role, meta in names.ROLES.items():
            self.assertRegex(role, r"^[a-z][a-z-]{6,19}$")
            self.assertNotIn(role, lex)
            self.assertIn(meta["group"], groups)
            self.assertTrue(meta["duty"])

    def test_tier_of_known_and_unknown(self):
        self.assertEqual(names.tier_of("arbiter"), "top")
        self.assertEqual(names.tier_of("reviewer"), "mid")
        self.assertEqual(names.tier_of("explorer"), "low")
        self.assertIsNone(names.tier_of("ops"))      # legacy scope
        self.assertIsNone(names.tier_of(None))

    def test_label_role(self):
        self.assertEqual(hao.label_role("hao-moth-frontend-developer"), "frontend-developer")
        self.assertEqual(hao.label_role("hao-verse-ops"), "ops")        # legacy still parses
        self.assertIsNone(hao.label_role("hao-verse"))
        self.assertIsNone(hao.label_role(""))

    def test_make_label_round_trip(self):
        label = hao.make_label("moth", "frontend-developer")
        self.assertEqual(label, "hao-moth-frontend-developer")
        self.assertEqual(hao.label_role(label), "frontend-developer")
        self.assertEqual(hao.make_label("moth"), "hao-moth")
