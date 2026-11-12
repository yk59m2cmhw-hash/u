#!/usr/bin/env python3
"""Tests for models/okno_costs.py. Run: python3 models/test_okno_costs.py"""
import csv
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import okno_costs as oc  # noqa: E402


class OknoCosts(unittest.TestCase):
    def setUp(self):
        self.x = oc.load_inputs()

    def test_conversation_cost(self):
        x = dict(self.x)
        c = oc.conversation_cost_usd(x, "claude-haiku-5-5", input_tokens=1_000_000, output_tokens=1_000_000)
        self.assertAlmostEqual(c, 0.10 + 0.50)

    def test_cac_hours(self):
        x = dict(self.x)
        expected = (50 * 0.25 + 15 * 0.75 + 5 * 1.5 + 3 * 6) / 1.5
        self.assertAlmostEqual(oc.cac_hours(x), expected)

    def test_whatsapp_costs_more_than_telegram(self):
        tg = oc.Scenario("t", "claude-haiku-5-5", "telegram", 3)
        wa = oc.Scenario("w", "claude-haiku-5-5", "whatsapp_direct", 3)
        bsp = oc.Scenario("b", "claude-haiku-5-5", "whatsapp_bsp", 3)
        m = lambda s: oc.monthly_costs_kzt(self.x, s)["messaging"]
        self.assertEqual(m(tg), 0)
        self.assertGreater(m(wa), 0)
        self.assertAlmostEqual(m(bsp) - m(wa), self.x["wa.bsp_fee_usd_month"] * self.x["fx.kzt_per_usd"])

    def test_break_even_covers_fee_and_tax(self):
        s = oc.SCENARIOS[0]
        p = oc.break_even_price(self.x, s)
        self.assertAlmostEqual(oc.margin_at(self.x, s, p), 0, places=6)
        self.assertGreater(oc.margin_at(self.x, s, p * 2), 0)

    def test_scale_is_cheaper_than_pilots(self):
        self.assertLess(oc.break_even_price(self.x, oc.SCENARIOS[4]), oc.break_even_price(self.x, oc.SCENARIOS[0]))

    def test_infra_shared_by_clients(self):
        a = oc.monthly_costs_kzt(self.x, oc.Scenario("a", "claude-haiku-5-5", "telegram", 3))["infrastructure"]
        b = oc.monthly_costs_kzt(self.x, oc.Scenario("b", "claude-haiku-5-5", "telegram", 30))["infrastructure"]
        self.assertAlmostEqual(a / b, 10)

    def test_inputs_have_sources_or_are_assumptions(self):
        with open(oc.INPUTS, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                self.assertIn(r["kind"], ("source", "assumption"), r["key"])
                if r["kind"] == "source":
                    self.assertTrue(r["source"].startswith("https://") and r["date"], r["key"])

    def test_report_renders(self):
        text = oc.report(self.x)
        self.assertIn("Безубыточная цена", text)
        self.assertIn("Экономия, если одобрят кредиты", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
