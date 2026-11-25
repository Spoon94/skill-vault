import glob
import os
import re
import unittest

HERE = os.path.dirname(__file__)
LOADER_RE = re.compile(r"SourceFileLoader\(\s*[\"']hao[\"']")
GUARD_RE = re.compile(r"install_offline_guard\(\s*hao\s*\)")


class TestR19OfflineGuardAdoption(unittest.TestCase):
    def test_every_hao_loading_test_installs_the_guard(self):
        offenders = []
        loaders = 0
        for path in sorted(glob.glob(os.path.join(HERE, "test_*.py"))):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            if not LOADER_RE.search(text):
                continue
            loaders += 1
            if not GUARD_RE.search(text):
                offenders.append(os.path.basename(path))
        self.assertGreaterEqual(loaders, 10)
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
