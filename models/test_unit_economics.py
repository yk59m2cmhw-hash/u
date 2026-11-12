#!/usr/bin/env python3
"""Tests for models/unit_economics.py. Run: python3 models/test_unit_economics.py"""
import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import unit_economics as ue  # noqa: E402


class Inference(unittest.TestCase):
    def test_effective_throughput_accounts_for_prefill(self):
        # 3 input tokens per output, prefill 10x faster -> 1.3x the time per output token
        self.assertAlmostEqual(ue.effective_output_tps(1300, 3, 10), 1000)

    def test_revenue_and_breakeven(self):
        # 1000 out tok/s effective -> 3.6M out + 10.8M in per hour
        r = ue.inference_economics(gpu_usd_per_hour=2.0, decode_tps=1300, utilization=0.5,
                                   price_in=0.10, price_out=0.40, ratio=3, prefill_speedup=10)
        self.assertAlmostEqual(r.out_tokens_per_gpu_hour, 3_600_000)
        self.assertAlmostEqual(r.revenue_per_gpu_hour_full, 3.6 * 0.40 + 10.8 * 0.10)  # 2.52
        self.assertAlmostEqual(r.revenue_per_gpu_hour, 1.26)
        self.assertAlmostEqual(r.breakeven_utilization, 2.0 / 2.52)
        self.assertLess(r.margin_pct, 0)

    def test_hyperscaler_h100_never_breaks_even_at_cheapest_prices(self):
        x = ue.load_inputs()
        r = ue.inference_economics(x["gpu.h100.gcp"], x["tput.moe120b.h100"], 1.0,
                                   x["price.gptoss120b.deepinfra.in"], x["price.gptoss120b.deepinfra.out"])
        self.assertGreater(r.breakeven_utilization, 1)


class Agent(unittest.TestCase):
    def test_conversation_cost_without_cache(self):
        c = ue.conversation_cost_api(turns=10, in_per_turn=1000, out_per_turn=100,
                                     price_in=1.0, price_out=5.0)
        self.assertAlmostEqual(c, 10_000 / 1e6 * 1.0 + 1_000 / 1e6 * 5.0)  # 0.015

    def test_cache_reduces_input_cost(self):
        full = ue.conversation_cost_api(10, 1000, 0, 1.0, 5.0)
        cached = ue.conversation_cost_api(10, 1000, 0, 1.0, 5.0, cached_share=0.5, cache_price_factor=0.1)
        self.assertAlmostEqual(cached, full * 0.55)

    def test_routing_is_weighted_average(self):
        cheap = ue.conversation_cost_api(8, 3000, 150, 0.1, 0.5)
        strong = ue.conversation_cost_api(8, 3000, 150, 2.0, 10.0)
        mixed = ue.conversation_cost_routed(8, 3000, 150, (0.1, 0.5), (2.0, 10.0), 0.1)
        self.assertAlmostEqual(mixed, 0.9 * cheap + 0.1 * strong)

    def test_selfhosted_cost_scales_with_idle_capacity(self):
        busy = ue.conversation_cost_selfhosted(8, 3000, 150, 0.85, 800, 0.8)
        idle = ue.conversation_cost_selfhosted(8, 3000, 150, 0.85, 800, 0.2)
        self.assertAlmostEqual(idle / busy, 4.0)

    def test_client_economics_and_payback(self):
        r = ue.client_economics(price=250, conversations=600, cost_per_conversation=0.01,
                                reminders=400, reminder_cost=0.02, hosting=10,
                                support_hours=2, hour_cost=15)
        self.assertAlmostEqual(r.cost, 6 + 8 + 10 + 30)
        self.assertAlmostEqual(r.gross_profit, 196)
        self.assertAlmostEqual(ue.payback_months(392, r.gross_profit), 2.0)
        self.assertTrue(math.isinf(ue.payback_months(100, -5)))


class Plan(unittest.TestCase):
    def test_revenue_plan_with_churn(self):
        rows = ue.revenue_plan(3, new_per_month=10, churn=0.1, price=100, setup_fee=50)
        self.assertEqual(rows[0][1], 0)
        self.assertAlmostEqual(rows[1][1], 10)
        self.assertAlmostEqual(rows[2][1], 19)
        self.assertAlmostEqual(rows[2][3], 19 * 100 + 10 * 50)

    def test_credit_runway_runs_out(self):
        used, first, expired = ue.credit_runway([100, 100, 100], credits=250, valid_months=12)
        self.assertEqual(used, [100, 100, 50])
        self.assertEqual(first, 3)
        self.assertEqual(expired, 0)

    def test_credit_runway_expires(self):
        used, first, expired = ue.credit_runway([10, 10, 10, 10], credits=100, valid_months=2)
        self.assertEqual(used, [10, 10, 0, 0])
        self.assertEqual(first, 3)
        self.assertEqual(expired, 80)

    def test_report_renders(self):
        text = ue.report(ue.load_inputs())
        for heading in ("(a) Selling tokens", "(b) Selling an agent", "(c) 12-month plan"):
            self.assertIn(heading, text)

    def test_every_input_has_source_or_is_assumption(self):
        import csv
        with open(ue.SCENARIOS, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                self.assertIn(r["kind"], ("source", "assumption"), r["key"])
                if r["kind"] == "source":
                    self.assertTrue(r["source"].startswith("https://"), r["key"])
                    self.assertTrue(r["date"], r["key"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
