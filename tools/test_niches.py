#!/usr/bin/env python3
"""Tests for tools/niches.py. Run: python3 tools/test_niches.py"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import niches  # noqa: E402


class Niches(unittest.TestCase):
    def test_all_fives_score_100(self):
        row = {k: 5 for k in niches.CRITERIA}
        self.assertEqual(niches.score(row), 100)

    def test_real_file_loads_and_ranks(self):
        ranked = niches.rank(niches.load())
        self.assertGreaterEqual(len(ranked), 12)
        scores = [s for s, _ in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_access_override_moves_a_niche(self):
        rows = niches.load()
        base = dict((r["id"], s) for s, r in niches.rank(rows))
        boosted = dict((r["id"], s) for s, r in niches.rank(rows, {"home_services": {"access": 5}}))
        self.assertAlmostEqual(boosted["home_services"] - base["home_services"], 20 * 3 / 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
