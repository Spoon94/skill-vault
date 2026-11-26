import unittest, types, os, io, json, contextlib, tempfile
from importlib.machinery import SourceFileLoader
from hao_test_guard import install_offline_guard
_l = SourceFileLoader("hao", os.path.join(os.path.dirname(__file__), "..", "..", "hao", "scripts", "hao"))
hao = types.ModuleType("hao"); _l.exec_module(hao)
install_offline_guard(hao)


def fake_herdr(label):
    calls = []
    def fake(args, machine=None):
        calls.append(list(args))
        if args[:2] == ["pane", "get"]:
            return 0, json.dumps({"result": {"pane": {"pane_id": "w2:p9", "label": label}}}), ""
        if args[:2] == ["agent", "get"]:
            return 1, "", '{"error":{"code":"agent_not_found"}}'   # shell pane: label only
        return 0, '{"result":{}}', ""
    return fake, calls


def run_json(fn, *args):
    buf = io.StringIO()
    hao._JSON_OUTPUT = True
    try:
        with contextlib.redirect_stdout(buf):
            rc = fn(*args)
    finally:
        hao._JSON_OUTPUT = False
    return rc, json.loads(buf.getvalue().strip().splitlines()[-1])


class TestNameRole(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["HAO_STATE_DIR"] = os.path.join(self.tmp.name, "hao", "tasks")

    def tearDown(self):
        os.environ.pop("HAO_STATE_DIR", None)
        self.tmp.cleanup()

    def test_sets_label_with_role_and_reports_tier(self):
        fake, calls = fake_herdr("")
        hao.run_herdr = fake
        rc, out = run_json(hao.cmd_name, "w2:p9", "moth", "frontend-developer", False, False)
        self.assertEqual(rc, 0)
        self.assertIn(["pane", "rename", "w2:p9", "hao-moth-frontend-developer"], calls)
        self.assertEqual((out["role"], out["tier"], out["kept"]), ("frontend-developer", "low", False))
        self.assertNotIn("scope", out)

    def test_unknown_role_exits_2_and_lists_roles(self):
        hao.run_herdr = lambda args, machine=None: (0, '{"result":{}}', "")
        self.assertEqual(hao.cmd_name("w2:p9", "moth", "foo", False, False), 2)
        self.assertIn("frontend-developer", hao._ERROR_DETAIL)
        hao._ERROR_DETAIL = None

    def test_rerun_without_role_keeps_existing_role(self):
        fake, calls = fake_herdr("hao-moth-reviewer")
        hao.run_herdr = fake
        rc, out = run_json(hao.cmd_name, "w2:p9", "lens", None, False, False)
        self.assertEqual(rc, 0)
        self.assertIn(["pane", "rename", "w2:p9", "hao-lens-reviewer"], calls)
        self.assertTrue(out["kept"])

    def test_legacy_scope_is_kept_verbatim_with_null_tier(self):
        fake, calls = fake_herdr("hao-verse-ops")
        hao.run_herdr = fake
        rc, out = run_json(hao.cmd_name, "w2:p9", "lens", None, False, False)
        self.assertEqual(rc, 0)
        self.assertIn(["pane", "rename", "w2:p9", "hao-lens-ops"], calls)
        self.assertEqual((out["role"], out["tier"]), ("ops", None))

    def test_status_shows_role_tier_group(self):
        def fake(args, machine=None):
            if args[:2] == ["pane", "get"]:
                return 0, '{"result":{"pane":{"pane_id":"w2:p9","label":"hao-moth-reviewer"}}}', ""
            return 1, "", '{"error":{"code":"agent_not_found"}}'
        hao.run_herdr = fake
        rc, out = run_json(hao.cmd_status, "w2:p9")
        self.assertEqual((out["role"], out["tier"], out["group"]), ("reviewer", "mid", "设计评审"))

    def test_parser_has_role_not_scope(self):
        p = hao.build_parser()
        a = p.parse_args(["name", "w2:p9", "hawk", "--role", "reviewer"])
        self.assertEqual(a.role, "reviewer")
        with self.assertRaises(SystemExit):
            p.parse_args(["name", "w2:p9", "hawk", "--scope", "api"])
        with self.assertRaises(SystemExit):
            p.parse_args(["suggest", "review", "--scope", "api"])


if __name__ == "__main__":
    unittest.main()
