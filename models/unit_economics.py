#!/usr/bin/env python3
"""Unit economics for the startup: selling tokens vs. selling an AI agent, and the credit cliff.

Standard library only. Inputs live in models/scenarios.csv (every number has a source or is
marked as an assumption). Run:

  python3 models/unit_economics.py            # print all tables as Markdown
  python3 models/test_unit_economics.py       # tests

Model conventions
- GPU throughput is the aggregate number of *generated* (output) tokens per second per GPU.
- Input tokens are processed `prefill_speedup` times faster than output tokens, so serving
  `ratio` input tokens per output token costs extra GPU time: 1 + ratio / prefill_speedup.
- Market prices are per 1M input and per 1M output tokens.
"""
import csv
import pathlib
from dataclasses import dataclass

HERE = pathlib.Path(__file__).resolve().parent
SCENARIOS = HERE / "scenarios.csv"
HOURS_PER_MONTH = 730


def load_inputs(path=SCENARIOS):
    with open(path, newline="", encoding="utf-8") as f:
        return {r["key"]: float(r["value"]) for r in csv.DictReader(f)}


# ------------------------------------------------------------------ (a) selling tokens

@dataclass
class InferenceResult:
    out_tokens_per_gpu_hour: float      # at 100% load
    revenue_per_gpu_hour_full: float    # at 100% load
    revenue_per_gpu_hour: float         # at the given utilization
    cost_per_gpu_hour: float
    margin_pct: float                   # at the given utilization
    breakeven_utilization: float        # load needed to cover the GPU (>1 means impossible)


def effective_output_tps(decode_tps, ratio, prefill_speedup):
    """Output tokens per second once the GPU also has to process `ratio` input tokens each."""
    return decode_tps / (1 + ratio / prefill_speedup)


def inference_economics(gpu_usd_per_hour, decode_tps, utilization, price_in, price_out,
                        ratio=3.0, prefill_speedup=10.0):
    out_per_hour = effective_output_tps(decode_tps, ratio, prefill_speedup) * 3600
    revenue_full = out_per_hour / 1e6 * (price_out + ratio * price_in)
    revenue = revenue_full * utilization
    margin = (revenue - gpu_usd_per_hour) / revenue * 100 if revenue else float("-inf")
    return InferenceResult(out_per_hour, revenue_full, revenue, gpu_usd_per_hour, margin,
                           gpu_usd_per_hour / revenue_full if revenue_full else float("inf"))


# ------------------------------------------------------------------ (b) selling an agent

def conversation_cost_api(turns, in_per_turn, out_per_turn, price_in, price_out,
                          cached_share=0.0, cache_price_factor=0.1):
    """USD per conversation on a per-token API with prompt caching on part of the input."""
    tokens_in = turns * in_per_turn
    tokens_out = turns * out_per_turn
    in_cost = tokens_in / 1e6 * price_in * ((1 - cached_share) + cached_share * cache_price_factor)
    return in_cost + tokens_out / 1e6 * price_out


def conversation_cost_routed(turns, in_per_turn, out_per_turn, cheap, strong, hard_share,
                             cached_share=0.0, cache_price_factor=0.1):
    """Mix of a cheap model and a strong model; cheap/strong are (price_in, price_out)."""
    c = conversation_cost_api(turns, in_per_turn, out_per_turn, *cheap, cached_share, cache_price_factor)
    s = conversation_cost_api(turns, in_per_turn, out_per_turn, *strong, cached_share, cache_price_factor)
    return (1 - hard_share) * c + hard_share * s


def conversation_cost_selfhosted(turns, in_per_turn, out_per_turn, gpu_usd_per_hour, decode_tps,
                                 utilization, prefill_speedup=10.0):
    """USD per conversation on your own GPU: share of GPU time, inflated by idle capacity."""
    out_equiv = turns * (out_per_turn + in_per_turn / prefill_speedup)
    gpu_seconds = out_equiv / decode_tps
    return gpu_seconds / 3600 * gpu_usd_per_hour / utilization


@dataclass
class ClientResult:
    price: float
    llm: float
    messaging: float
    voice: float
    hosting: float
    support: float
    cost: float
    gross_profit: float
    margin_pct: float


def client_economics(price, conversations, cost_per_conversation, reminders=0, reminder_cost=0.0,
                     voice_minutes=0, voice_cost_per_min=0.0, hosting=0.0, support_hours=0.0,
                     hour_cost=0.0):
    llm = conversations * cost_per_conversation
    messaging = reminders * reminder_cost
    voice = voice_minutes * voice_cost_per_min
    support = support_hours * hour_cost
    cost = llm + messaging + voice + hosting + support
    gp = price - cost
    return ClientResult(price, llm, messaging, voice, hosting, support, cost, gp,
                        gp / price * 100 if price else float("-inf"))


def payback_months(cac, monthly_gross_profit):
    return float("inf") if monthly_gross_profit <= 0 else cac / monthly_gross_profit


# ------------------------------------------------------------------ (c) plan and credit cliff

@dataclass
class Month:
    month: int
    clients: float
    mrr: float
    revenue: float          # MRR + setup fees
    infra_cost: float
    credits_used: float
    cash_infra_cost: float  # infra cost not covered by credits


def revenue_plan(months, new_per_month, churn, price, setup_fee):
    """Clients start in month 2; churn applies to the clients at the start of each month."""
    clients, out = 0.0, []
    for m in range(1, months + 1):
        new = new_per_month if m >= 2 else 0
        clients = clients * (1 - churn) + new
        out.append((m, clients, clients * price, clients * price + new * setup_fee))
    return out


def credit_runway(monthly_costs, credits, valid_months):
    """Spend a credit pool on monthly costs until it is used up or expires.
    Returns (per-month credits used, first month with uncovered cost or None, expired amount)."""
    left, used, first_uncovered, expired = credits, [], None, 0.0
    for i, cost in enumerate(monthly_costs, 1):
        if i == valid_months + 1:  # the pool expires at the start of this month
            expired, left = left, 0.0
        take = min(cost, left)
        left -= take
        used.append(take)
        if take < cost and first_uncovered is None:
            first_uncovered = i
    return used, first_uncovered, expired


def plan_with_credits(x, cost_per_conversation):
    """12-month plan: clients, revenue, infra cost (base + GPU + per-client variable costs)."""
    rows = revenue_plan(int(x["plan.months"]), x["plan.new_clients_per_month"],
                        x["plan.monthly_churn"], x["client.price_per_month"], x["client.setup_fee"])
    gpu = x["infra.l4_count"] * x["gpu.l4.gcp"] * HOURS_PER_MONTH
    per_client = (x["client.conversations_per_month"] * cost_per_conversation
                  + x["client.hosting_per_month"])
    costs = [x["infra.base_per_month"] + gpu + c * per_client for _, c, _, _ in rows]
    used, first_uncovered, _ = credit_runway(costs, x["credits.p1"], int(x["credits.p1.valid_months"]))
    months = [Month(m, c, mrr, rev, cost, u, cost - u)
              for (m, c, mrr, rev), cost, u in zip(rows, costs, used)]
    return months, first_uncovered


# ------------------------------------------------------------------ report

def usd(v, digits=0):
    return f"${v:,.{digits}f}"


def report(x):
    out = []
    ratio, pf = x["ratio.in_out"], x["prefill.speedup"]

    out.append("## (a) Selling tokens: revenue and cost per GPU-hour\n")
    out.append("| Model on H100 | Prices | GPU | GPU $/h | Revenue $/h at 100% | at 30% | Margin at 30% | Break-even load |")
    out.append("|---|---|---|---|---|---|---|---|")
    cases = [("MoE 120B (gpt-oss class)", "tput.moe120b.h100", "price.gptoss120b.together", "Together/Groq level"),
             ("MoE 120B (gpt-oss class)", "tput.moe120b.h100", "price.gptoss120b.deepinfra", "cheapest market"),
             ("Dense 70B", "tput.dense70b.h100", "price.dense70b.median", "median $0.48")]
    for name, tkey, pkey, plabel in cases:
        for g in ("gcp", "aws", "neocloud", "marketplace"):
            r = inference_economics(x[f"gpu.h100.{g}"], x[tkey], 0.30, x[pkey + ".in"], x[pkey + ".out"], ratio, pf)
            be = f"{r.breakeven_utilization:.0%}" if r.breakeven_utilization <= 1 else "never"
            out.append(f"| {name} | {plabel} | {g} | {usd(r.cost_per_gpu_hour, 2)} | {usd(r.revenue_per_gpu_hour_full, 2)} "
                       f"| {usd(r.revenue_per_gpu_hour, 2)} | {r.margin_pct:.0f}% | {be} |")
    node_full = inference_economics(x["gpu.h100.gcp"], x["tput.moe120b.h100"], 1.0,
                                    x["price.gptoss120b.together.in"], x["price.gptoss120b.together.out"], ratio, pf)
    out.append(f"\nOne 8xH100 node with a gpt-oss-class model at Together-level prices: "
               f"{usd(node_full.revenue_per_gpu_hour_full * 8 * HOURS_PER_MONTH)} per month at 100% load, "
               f"{usd(node_full.revenue_per_gpu_hour_full * 8 * HOURS_PER_MONTH * 0.3)} at 30%; "
               f"the node costs {usd(x['gpu.h100.gcp'] * 8 * HOURS_PER_MONTH)} on Google Cloud and "
               f"{usd(x['gpu.h100.aws'] * 8 * HOURS_PER_MONTH)} on AWS per month.\n")

    out.append("## (b) Selling an agent: cost of one conversation\n")
    t, i, o = x["agent.turns"], x["agent.in_tokens_per_turn"], x["agent.out_tokens_per_turn"]
    cs, cf = x["agent.cached_share"], x["agent.cache_price_factor"]
    conv = {}
    out.append("| Option | $ per conversation | $ per 1,000 conversations |")
    out.append("|---|---|---|")
    for label, key in [("Gemini 2.5 Flash-Lite", "api.gemini25_flash_lite"), ("Claude Haiku 5.5", "api.claude_haiku55"),
                       ("Gemini 3.5 Flash-Lite", "api.gemini35_flash_lite"), ("Claude Sonnet 5.5", "api.claude_sonnet55")]:
        conv[label] = conversation_cost_api(t, i, o, x[key + ".in"], x[key + ".out"], cs, cf)
    conv["Routed: 90% Haiku 5.5 + 10% Sonnet 5.5"] = conversation_cost_routed(
        t, i, o, (x["api.claude_haiku55.in"], x["api.claude_haiku55.out"]),
        (x["api.claude_sonnet55.in"], x["api.claude_sonnet55.out"]), x["agent.hard_turn_share"], cs, cf)
    conv["Self-hosted 8B on one L4 (GCP), 30% load"] = conversation_cost_selfhosted(
        t, i, o, x["gpu.l4.gcp"], x["tput.dense8b.l4"], x["agent.selfhost_utilization"], pf)
    conv["Self-hosted 8B on one L4 (GCP), 80% load"] = conversation_cost_selfhosted(
        t, i, o, x["gpu.l4.gcp"], x["tput.dense8b.l4"], 0.8, pf)
    for label, c in conv.items():
        out.append(f"| {label} | {usd(c, 4)} | {usd(c * 1000, 2)} |")

    routed = conv["Routed: 90% Haiku 5.5 + 10% Sonnet 5.5"]
    out.append("\n### One client per month (routed model mix)\n")
    ce = client_economics(x["client.price_per_month"], x["client.conversations_per_month"], routed,
                          x["client.reminders_per_month"], x["client.reminder_cost"],
                          x["client.voice_minutes_per_month"], x["client.voice_cost_per_min"],
                          x["client.hosting_per_month"], x["client.support_hours_per_month"], x["client.hour_cost"])
    out.append("| Item | $ per month |")
    out.append("|---|---|")
    for k in ("price", "llm", "messaging", "voice", "hosting", "support", "cost", "gross_profit"):
        out.append(f"| {k.replace('_', ' ')} | {usd(getattr(ce, k), 2)} |")
    out.append(f"| gross margin | {ce.margin_pct:.0f}% |")
    out.append(f"| payback of CAC {usd(x['client.cac'])} | {payback_months(x['client.cac'], ce.gross_profit):.1f} months |")
    voice = client_economics(x["client.price_per_month"], x["client.conversations_per_month"], routed,
                             x["client.reminders_per_month"], x["client.reminder_cost"], 300,
                             x["client.voice_cost_per_min"], x["client.hosting_per_month"],
                             x["client.support_hours_per_month"], x["client.hour_cost"])
    out.append(f"\nWith 300 voice minutes a month at {usd(x['client.voice_cost_per_min'], 2)}/min the cost rises to "
               f"{usd(voice.cost, 2)} and the margin falls to {voice.margin_pct:.0f}% at the same price: "
               f"voice needs a higher tier.\n")

    out.append("## (c) 12-month plan and the credit cliff\n")
    months, first_uncovered = plan_with_credits(x, routed)
    out.append("| Month | Clients | MRR | Revenue | Infra cost | Paid by credits | Paid in cash |")
    out.append("|---|---|---|---|---|---|---|")
    for m in months:
        out.append(f"| {m.month} | {m.clients:.1f} | {usd(m.mrr)} | {usd(m.revenue)} | {usd(m.infra_cost)} "
                   f"| {usd(m.credits_used)} | {usd(m.cash_infra_cost)} |")
    total_rev = sum(m.revenue for m in months)
    last = months[-1]
    out.append(f"\nCredits {usd(x['credits.p1'])}, valid {int(x['credits.p1.valid_months'])} months: "
               + (f"they stop covering infrastructure in month {first_uncovered}." if first_uncovered
                  else "they cover infrastructure for the whole plan.")
               + f" Revenue over 12 months: {usd(total_rev)}. Month 12: MRR {usd(last.mrr)}, infra "
               f"{usd(last.infra_cost)} ({last.infra_cost / last.mrr:.0%} of MRR).")
    share = last.infra_cost / last.mrr if last.mrr else float("inf")
    out.append("The cliff is survivable: infrastructure is a small share of revenue.\n" if share < 0.3 else
               "Warning: infrastructure is a large share of revenue - the cliff will hurt.\n")
    return "\n".join(out)


if __name__ == "__main__":
    print(report(load_inputs()))
