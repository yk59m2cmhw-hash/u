# okno — text AI front desk prototype

A customer writes to a small home-services company; the agent answers FAQs from the company's knowledge
base, collects the task, district, preferred time, name and phone, shows a summary, and hands the confirmed
lead to staff. It never quotes prices and never confirms a visit: deterministic guards enforce both on top
of any model.

Product docs (Russian): [`product/`](../product/scenario.md). Decisions: [`plan/DECISIONS.md`](../plan/DECISIONS.md).

## Run

Python 3.10+. No dependencies for offline mode; `pip install anthropic` for Claude.

```bash
python3 -m okno                      # terminal chat (provider: auto)
python3 -m okno.web --port 8080      # web demo at http://127.0.0.1:8080
python3 -m okno.web --host 0.0.0.0   # open from a phone on the same Wi-Fi
```

Providers (`--provider`, or `auto` = Claude if `ANTHROPIC_API_KEY` is set, Gemini if `GEMINI_API_KEY` is set,
otherwise offline):

| Provider | What it is | Model (default; override with `--model` or `OKNO_MODEL`) |
|---|---|---|
| `offline` | rules and templates, no model, no network — labelled as such in the UI | `rules-v1` |
| `anthropic` | Claude via the official `anthropic` SDK, structured output (`output_config.format`), prompt caching, server-side refusal fallback on models that support it | `claude-opus-5-5` |
| `gemini` | Gemini via Google's OpenAI-compatible endpoint (`Authorization: Bearer $GEMINI_API_KEY`) | `gemini-2.5-flash-lite` |

## Lead delivery

Every handed-off lead is appended to `data/leads.jsonl` (`OKNO_LEADS_FILE`). Optional:

- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` — post the card to a staff chat;
- `OKNO_WEBHOOK_URL` — POST `{reason, lead, card}` as JSON (CRM incoming webhook, automation).

See [`.env.example`](../.env.example). Never commit real keys.

## Tests and eval

```bash
python3 -m unittest discover -s okno/tests -t .             # unit tests (offline, recorded model turns)
python3 -m okno.evals.run                                    # 20 scripted dialogs, offline
ANTHROPIC_API_KEY=... python3 -m okno.evals.run --provider anthropic --model claude-haiku-5-5
```

The eval checks every reply for prices and visit promises and each dialog's final status, handoff reason,
fields, language and number of customer messages. It reports token use (measured on real providers,
estimated offline) and cost per lead for several models.

## Layout

| File | Role |
|---|---|
| `agent.py` | conversation engine: emergencies, human requests, complaints, confirmation, handoff |
| `guards.py` | price / visit-promise filter, emergency and intent detection, language |
| `providers.py` | offline rules, Claude, Gemini, replay (tests) |
| `prompts.py` | system prompt and JSON schema shared by the model providers |
| `lead.py`, `phone.py`, `kb.py` | lead fields and staff card, KZ phone normalisation, knowledge base |
| `handoff.py` | JSONL, Telegram and webhook sinks |
| `web.py`, `cli.py` | demo interfaces (standard library only) |
| `data/demo_company.json` | fictional company knowledge base |
| `evals/` | scripted dialogs and the runner |
