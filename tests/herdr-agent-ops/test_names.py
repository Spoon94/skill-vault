import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "herdr-agent-ops", "scripts"))
from names import NAMES, RESERVED, GRAY


class TestNames(unittest.TestCase):
    def test_count(self):
        total = [n for g in NAMES.values() for n in g["names"]]
        self.assertEqual(len(total), 1600)
        self.assertEqual(len(set(total)), 1600)

    def test_format(self):
        for g in NAMES.values():
            for n in g["names"]:
                self.assertRegex(n, r"^[a-z]{4,6}$")

    def test_no_reserved(self):
        for g in NAMES.values():
            for n in g["names"]:
                self.assertNotIn(n, RESERVED)
                self.assertNotIn(n, GRAY)

    def test_keywords_present(self):
        for g in NAMES.values():
            self.assertTrue(g["keywords_zh"])
            self.assertTrue(g["keywords_en"])


if __name__ == "__main__":
    unittest.main()
