#!/usr/bin/env python3
"""Tests for tools/credits.py. Run: python3 tools/test_credits.py"""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import credits  # noqa: E402


def row(**kw):
    base = {f: "" for f in credits.FIELDS}
    base.update(id="x", provider="P", program="Prog", category="hyperscaler", max_credits_usd=0,
                self_serve="no", requires_entity="yes", requires_funding="no",
                requires_partner_code="no", gpu_eligible="yes", covers_ai_apis="no",
                confidence="low", phase="P1", priority=3)
    base.update(kw)
    return base


class RealDatabase(unittest.TestCase):
    def setUp(self):
        self.rows = credits.load()

    def test_schema_is_valid(self):
        self.assertEqual(credits.validate(self.rows), [])

    def test_size_in_expected_range(self):
        self.assertGreaterEqual(len(self.rows), 80)

    def test_high_confidence_rows_are_dated(self):
        for r in self.rows:
            if r["confidence"] == "high":
                self.assertTrue(r["verified_on"], r["id"])


class Logic(unittest.TestCase):
    def test_phases_are_cumulative(self):
        rows = [row(id="a", phase="P0"), row(id="b", phase="P1"), row(id="c", phase="P2")]
        self.assertEqual([r["id"] for r in credits.available_by(rows, "P1")], ["a", "b"])

    def test_summary_keeps_best_tier_per_provider(self):
        rows = [row(id="s", provider="G", max_credits_usd=2000, phase="P1"),
                row(id="l", provider="G", max_credits_usd=350000, phase="P1"),
                row(id="a", provider="A", max_credits_usd=1000, phase="P1")]
        p1 = [s for s in credits.summary(rows) if s["phase"] == "P1"][0]
        self.assertEqual(p1["sum_of_ceilings_usd"], 353000)
        self.assertEqual(p1["best_per_provider_usd"], 351000)
        self.assertEqual(p1["providers"], 2)

    def test_compute_filter_drops_saas(self):
        rows = [row(id="c", category="gpu-cloud", max_credits_usd=10, phase="P1"),
                row(id="s", category="saas", max_credits_usd=99, phase="P1")]
        p1 = [s for s in credits.summary(rows, credits.COMPUTE) if s["phase"] == "P1"][0]
        self.assertEqual(p1["sum_of_ceilings_usd"], 10)

    def test_select_filters(self):
        rows = [row(id="g", gpu_eligible="yes", self_serve="yes", max_credits_usd=5),
                row(id="n", gpu_eligible="no", self_serve="yes", max_credits_usd=50),
                row(id="p", gpu_eligible="partial", self_serve="no", max_credits_usd=500)]
        self.assertEqual({r["id"] for r in credits.select(rows, gpu=True)}, {"g", "p"})
        self.assertEqual({r["id"] for r in credits.select(rows, self_serve=True)}, {"g", "n"})
        self.assertEqual({r["id"] for r in credits.select(rows, min_usd=50)}, {"n", "p"})

    def test_validate_catches_bad_values(self):
        bad = row(id="b", gpu_eligible="maybe", phase="P9", application_url="http://x")
        problems = " ".join(credits.validate([bad, row(id="b")]))
        for needle in ("gpu_eligible", "phase", "https://", "duplicate id"):
            self.assertIn(needle, problems)

    def test_export_json_roundtrip(self):
        rows = credits.load()
        with tempfile.TemporaryDirectory() as d:
            path = credits.export_json(rows, pathlib.Path(d) / "p.json")
            self.assertEqual(len(json.loads(path.read_text(encoding="utf-8"))), len(rows))

    def test_markdown_table(self):
        md = credits.to_markdown([row(id="m", max_credits_usd=1500)])
        self.assertIn("| 1 | P | Prog |", md)
        self.assertIn("$1,500", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
