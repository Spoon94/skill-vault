import unittest
import unittest
import os
from importlib.machinery import SourceFileLoader

import unittest
import os
import types
from importlib.machinery import SourceFileLoader

_loader = SourceFileLoader("hao", os.path.join(os.path.dirname(__file__), "..", "..", "herdr-agent-ops", "scripts", "hao"))
hao = types.ModuleType(_loader.name)
_loader.exec_module(hao)
from hao_test_guard import install_offline_guard  # noqa: E402
install_offline_guard(hao)

run_herdr = hao.run_herdr
resolve_target = hao.resolve_target
HAO_LABEL_RE = hao.HAO_LABEL_RE


class TestScaffold(unittest.TestCase):
    def test_resolve_pane_id(self):
        self.assertEqual(resolve_target("w2:p9"), "w2:p9")

    def test_resolve_workspace_tab_pane(self):
        self.assertEqual(resolve_target("w2:t1:p9"), "w2:p9")

    def test_label_regex(self):
        m = HAO_LABEL_RE.match("hao-hawk-api")
        self.assertEqual(m.group(1), "hawk")
        self.assertEqual(m.group(2), "api")


if __name__ == "__main__":
    unittest.main()
