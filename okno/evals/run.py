"""Run the scripted dialogs and score them.

  python3 -m okno.evals.run                                   # offline rules (no model)
  ANTHROPIC_API_KEY=... python3 -m okno.evals.run --provider anthropic --model claude-haiku-5-5
  GEMINI_API_KEY=... python3 -m okno.evals.run --provider gemini

Checks for every dialog: no price and no visit promise in any reply; the expected final status, handoff
reason, fields, language and number of customer messages. Token use is measured on real providers and
estimated (characters / 3) offline.
"""
import argparse
import json
import pathlib

from .. import guards
from .. import kb as kbmod
from ..agent import Conversation
from ..providers import make_provider

HERE = pathlib.Path(__file__).resolve().parent
DIALOGS = HERE / "dialogs.json"

# USD per 1M input / output tokens (Claude: Claude API reference cached 2026-11-03; Gemini: see models/okno_inputs.csv)
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
}


def run_dialog(dialog, provider, kb):
    conv = Conversation(kb, provider)
    replies, out = [], None
    for text in dialog["turns"]:
        out = conv.handle(text)
        replies.append(out["reply"])
    exp, fails = dialog["expect"], []
    for i, r in enumerate(replies):
        if guards.has_price(r) and "Задача:" not in r:  # the summary quotes the customer verbatim
            fails.append(f"price in reply {i + 1}")
        if guards.has_visit_promise(r):
            fails.append(f"visit promise in reply {i + 1}")
    if out["status"] != exp["status"]:
        fails.append(f"status {out['status']} != {exp['status']}")
    if exp.get("reason") and out["handoff_reason"] != exp["reason"]:
        fails.append(f"reason {out['handoff_reason']!r} != {exp['reason']!r}")
    for k, v in exp.get("fields", {}).items():
        if out["lead"].get(k) != v:
            fails.append(f"{k}={out['lead'].get(k)!r} != {v!r}")
    if exp.get("language") and out["lead"]["language"] != exp["language"]:
        fails.append(f"language {out['lead']['language']} != {exp['language']}")
    if exp.get("urgent") and out["lead"]["urgent"] != exp["urgent"]:
        fails.append(f"urgent {out['lead']['urgent']!r} != {exp['urgent']!r}")
    if exp.get("first_reply_contains") and exp["first_reply_contains"] not in replies[0]:
        fails.append(f"first reply lacks {exp['first_reply_contains']!r}")
    if exp.get("notes_nonempty") and not out["lead"]["notes"]:
        fails.append("notes empty")
    if conv.user_turns > exp.get("max_user_turns", 99):
        fails.append(f"turns {conv.user_turns} > {exp['max_user_turns']}")
    return {"id": dialog["id"], "title": dialog["title"], "passed": not fails, "fails": fails,
            "turns": conv.user_turns, "usage": conv.usage, "lead_ready": out["handoff_reason"] == "lead_ready"}


def cost(usage, model):
    pin, pout = PRICES[model]
    billed_in = usage["input_tokens"] + usage.get("cache_write", 0) * 1.25 + usage.get("cache_read", 0) * 0.1
    return billed_in / 1e6 * pin + usage["output_tokens"] / 1e6 * pout


def report(results, provider):
    passed = sum(r["passed"] for r in results)
    ready = [r for r in results if r["lead_ready"]]
    avg_in = sum(r["usage"]["input_tokens"] for r in ready) / max(len(ready), 1)
    avg_out = sum(r["usage"]["output_tokens"] for r in ready) / max(len(ready), 1)
    avg_calls = sum(r["usage"]["model_calls"] for r in ready) / max(len(ready), 1)
    estimated = any(r["usage"].get("estimated") for r in results)
    lines = [f"# Прогон тестовых диалогов Okno",
             "",
             f"Провайдер: `{provider.name}`, модель: `{provider.model}`. "
             f"Прошли **{passed} из {len(results)}** ({passed / len(results):.0%}).",
             "",
             "| # | Диалог | Результат | Сообщений клиента | Замечания |",
             "|---|---|---|---|---|"]
    for i, r in enumerate(results, 1):
        lines.append(f"| {i} | {r['title']} | {'прошёл' if r['passed'] else 'НЕ прошёл'} | {r['turns']} | "
                     f"{'; '.join(r['fails']) or '—'} |")
    lines += ["",
              f"## Токены на одну заявку (среднее по {len(ready)} диалогам, где заявка передана)",
              "",
              f"Вход ≈ {avg_in:,.0f}, выход ≈ {avg_out:,.0f} токенов, вызовов модели ≈ {avg_calls:.1f}."
              + (" **Это оценка офлайн-режима** (символы / 3 для того же промпта, без кэширования): реальные "
                 "числа даст прогон на модели." if estimated else ""),
              "",
              "| Модель | $ за заявку | $ за 100 заявок |",
              "|---|---|---|"]
    u = {"input_tokens": avg_in, "output_tokens": avg_out, "cache_read": 0, "cache_write": 0}
    for m in PRICES:
        c = cost(u, m)
        lines.append(f"| {m} | ${c:.4f} | ${c * 100:.2f} |")
    return "\n".join(lines) + "\n", passed, len(results), (avg_in, avg_out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Okno scripted-dialog eval")
    ap.add_argument("--provider", default="offline")
    ap.add_argument("--model", default=None)
    ap.add_argument("--out", default=None, help="write the Markdown report here")
    args = ap.parse_args(argv)
    kb = kbmod.load()
    dialogs = json.loads(DIALOGS.read_text(encoding="utf-8"))
    results = []
    for d in dialogs:
        provider = make_provider(args.provider, kb, args.model)
        results.append(run_dialog(d, provider, kb))
    text, passed, total, _ = report(results, make_provider(args.provider, kb, args.model))
    if args.out:
        pathlib.Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0 if passed / total >= 0.9 else 1


if __name__ == "__main__":
    raise SystemExit(main())
