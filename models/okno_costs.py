#!/usr/bin/env python3
"""Okno: full cost per client per month WITHOUT cloud credits (decision D-007).

Standard library only. Inputs: models/okno_inputs.csv (every number has a source or is an assumption).

  python3 models/okno_costs.py          # Markdown tables
  python3 models/test_okno_costs.py     # tests

Cost lines per client per month: model tokens, messaging (WhatsApp fees or free Telegram), share of fixed
infrastructure, onboarding and acquisition amortised over the client lifetime, support, payment fee and tax.
Credits appear only as a separate "savings if approved" line.
"""
import csv
import pathlib
from dataclasses import dataclass

HERE = pathlib.Path(__file__).resolve().parent
INPUTS = HERE / "okno_inputs.csv"
MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "gemini-2.5-flash-lite")
PRICE_POINTS_KZT = (9900, 19900, 29900, 39900)


def load_inputs(path=INPUTS):
    with open(path, newline="", encoding="utf-8") as f:
        return {r["key"]: float(r["value"]) for r in csv.DictReader(f)}


def conversation_cost_usd(x, model, input_tokens=None, output_tokens=None):
    i = x["conv.input_tokens"] if input_tokens is None else input_tokens
    o = x["conv.output_tokens"] if output_tokens is None else output_tokens
    return i / 1e6 * x[f"model.{model}.in"] + o / 1e6 * x[f"model.{model}.out"]


def cac_hours(x):
    """Founder hours spent on the funnel per paying client."""
    total = (x["funnel.contacts"] * x["hours.per_contact"] + x["funnel.conversations"] * x["hours.per_conversation"]
             + x["funnel.demos"] * x["hours.per_demo"] + x["funnel.pilots"] * x["hours.per_pilot"])
    return total / x["funnel.paid"]


@dataclass
class Scenario:
    name: str
    model: str
    channel: str          # telegram | whatsapp_direct | whatsapp_bsp
    clients: int          # clients sharing the fixed infrastructure
    support_hours: float = None
    cac_factor: float = 1.0   # 0.5 = acquisition twice as efficient


def monthly_costs_kzt(x, s):
    """Cost lines per client per month in KZT, before payment fee and tax."""
    fx = x["fx.kzt_per_usd"]
    convs = x["conv.per_client_month"]
    llm = convs * conversation_cost_usd(x, s.model) * fx
    messaging = 0.0
    if s.channel.startswith("whatsapp"):
        messaging = convs * x["conv.bot_messages"] * x["wa.service_msg_usd"] * fx
        if s.channel == "whatsapp_bsp":
            messaging += x["wa.bsp_fee_usd_month"] * fx
    infra = (x["infra.server_usd_month"] + x["infra.other_usd_month"]) * fx / s.clients
    hour = x["time.hour_kzt"]
    onboarding = x["onboarding.hours"] * hour / x["lifetime.months"]
    support = (x["support.hours_month"] if s.support_hours is None else s.support_hours) * hour
    acquisition = cac_hours(x) * s.cac_factor * hour / x["lifetime.months"]
    return {"model": llm, "messaging": messaging, "infrastructure": infra, "onboarding": onboarding,
            "support": support, "acquisition": acquisition}


def break_even_price(x, s):
    """Price at which revenue covers all lines including payment fee and tax (both % of price)."""
    cost = sum(monthly_costs_kzt(x, s).values())
    return cost / (1 - (x["pay.fee_pct"] + x["tax.pct"]) / 100)


def margin_at(x, s, price_kzt):
    cost = sum(monthly_costs_kzt(x, s).values()) + price_kzt * (x["pay.fee_pct"] + x["tax.pct"]) / 100
    return (price_kzt - cost) / price_kzt * 100


def credit_savings_months(x, s, credits_usd):
    """Client-months whose model + infrastructure costs a credit pool would cover."""
    c = monthly_costs_kzt(x, s)
    covered = (c["model"] + c["infrastructure"]) / x["fx.kzt_per_usd"]
    return float("inf") if covered == 0 else credits_usd / covered


SCENARIOS = [
    Scenario("Пилоты: 3 клиента, Telegram, Haiku 5.5", "claude-haiku-5-5", "telegram", 3),
    Scenario("Пилоты: 3 клиента, Telegram, Opus 5.5", "claude-opus-5-5", "telegram", 3),
    Scenario("Пилоты: 3 клиента, WhatsApp напрямую, Haiku 5.5", "claude-haiku-5-5", "whatsapp_direct", 3),
    Scenario("Пилоты: 3 клиента, WhatsApp через посредника, Haiku 5.5", "claude-haiku-5-5", "whatsapp_bsp", 3),
    Scenario("30 клиентов, Telegram, Haiku 5.5, поддержка 0.75 ч, привлечение ×0.5",
             "claude-haiku-5-5", "telegram", 30, support_hours=0.75, cac_factor=0.5),
    Scenario("30 клиентов, WhatsApp напрямую, Haiku 5.5, поддержка 0.75 ч, привлечение ×0.5",
             "claude-haiku-5-5", "whatsapp_direct", 30, support_hours=0.75, cac_factor=0.5),
]

LABELS = {"model": "Модель (токены)", "messaging": "Сообщения", "infrastructure": "Инфраструктура (доля)",
          "onboarding": "Внедрение (амортизация)", "support": "Поддержка", "acquisition": "Привлечение (амортизация)"}


def kzt(v):
    return f"{v:,.0f} ₸".replace(",", " ")


def report(x):
    fx = x["fx.kzt_per_usd"]
    out = ["### Стоимость одного разговора по моделям", "",
           "| Модель | $ за разговор | ₸ за разговор | ₸ в месяц на клиента (150 разговоров) |", "|---|---|---|---|"]
    for m in MODELS:
        c = conversation_cost_usd(x, m)
        out.append(f"| {m} | ${c:.4f} | {c * fx:.1f} ₸ | {kzt(c * fx * x['conv.per_client_month'])} |")
    wa = x["conv.bot_messages"] * x["wa.service_msg_usd"]
    out += ["", f"WhatsApp: {x['conv.bot_messages']:.0f} ответов агента × ${x['wa.service_msg_usd']} = ${wa:.3f} "
                f"({wa * fx:.0f} ₸) за разговор; Telegram — бесплатно.", "",
            f"Привлечение: {cac_hours(x):.1f} ч основателей на одного платящего клиента "
            f"({kzt(cac_hours(x) * x['time.hour_kzt'])}).", ""]

    out += ["### Полная себестоимость на клиента в месяц (без кредитов)", ""]
    head = "| Статья | " + " | ".join(f"S{i + 1}" for i in range(len(SCENARIOS))) + " |"
    out += [head, "|---|" + "---|" * len(SCENARIOS)]
    costs = [monthly_costs_kzt(x, s) for s in SCENARIOS]
    for key, label in LABELS.items():
        out.append(f"| {label} | " + " | ".join(kzt(c[key]) for c in costs) + " |")
    out.append("| **Итого до комиссий и налога** | " + " | ".join(f"**{kzt(sum(c.values()))}**" for c in costs) + " |")
    out.append("| **Безубыточная цена** (с комиссией и налогом) | " +
               " | ".join(f"**{kzt(break_even_price(x, s))}** (${break_even_price(x, s) / fx:.0f})" for s in SCENARIOS) + " |")
    out += ["", "Сценарии:", ""] + [f"- **S{i + 1}** — {s.name}" for i, s in enumerate(SCENARIOS)]

    out += ["", "### Маржа при разных ценах", "",
            "| Цена в месяц | " + " | ".join(f"S{i + 1}" for i in range(len(SCENARIOS))) + " |",
            "|---|" + "---|" * len(SCENARIOS)]
    for p in PRICE_POINTS_KZT:
        out.append(f"| {kzt(p)} (${p / fx:.0f}) | " + " | ".join(f"{margin_at(x, s, p):.0f}%" for s in SCENARIOS) + " |")

    out += ["", "### Чувствительность (S1, пилоты, Telegram, Haiku 5.5)", "",
            "| Если изменить | Безубыточная цена |", "|---|---|"]
    base = SCENARIOS[0]
    for label, key, val in [("стоимость часа основателя 2 000 ₸", "time.hour_kzt", 2000),
                            ("стоимость часа основателя 8 000 ₸", "time.hour_kzt", 8000),
                            ("поддержка 3 ч в месяц", "support.hours_month", 3.0),
                            ("в пилоте платят 1 из 3 (не 1.5)", "funnel.paid", 1.0),
                            ("срок жизни клиента 6 месяцев", "lifetime.months", 6),
                            ("300 разговоров в месяц", "conv.per_client_month", 300)]:
        y = dict(x)
        y[key] = val
        out.append(f"| {label} | {kzt(break_even_price(y, base))} |")

    out += ["", "### Экономия, если одобрят кредиты (отдельной строкой, D-007)", "",
            "Кредиты покрывают только модель и инфраструктуру — не время основателей и не сообщения WhatsApp.", "",
            "| Кредиты | Сценарий | Сколько клиент-месяцев покроют |", "|---|---|---|"]
    for credits, label in [(1000, "AWS Activate Founders $1,000 (Claude через Bedrock — проверить)"),
                           (2000, "Google for Startups Start $2,000 (Gemini через Vertex AI)"),
                           (5000, "Microsoft for Startups $5,000")]:
        for s in (SCENARIOS[0], SCENARIOS[4]):
            out.append(f"| {label} | {s.name} | {credit_savings_months(x, s, credits):,.0f} |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    print(report(load_inputs()))
