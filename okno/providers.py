"""Model providers. Each returns a ModelTurn for one customer message.

- OfflineProvider: deterministic rules and templates. No model, no network. Used for tests, for the
  cloud eval, and to show the flow without an API key. It is clearly not an LLM.
- AnthropicProvider: Claude through the official `anthropic` SDK with structured output.
- GeminiProvider: Gemini through Google's official OpenAI-compatible endpoint (stdlib HTTP).
- ReplayProvider: returns pre-recorded turns (tests of parsing and guardrails).
"""
import json
import math
import os
import re
import urllib.request
from dataclasses import dataclass, field

from . import guards
from . import kb as kbmod
from . import phone as phonemod
from .lead import ASK_ORDER, REQUIRED
from .prompts import FIELDS, TURN_SCHEMA

# Models that accept the server-side refusal fallback (see the Claude API reference).
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5", "claude-opus-5", "claude-fable-5-2"}


# Leading greetings are not part of the task description ("Здравствуйте, течёт кран" -> "Течёт кран").
_GREETING = re.compile(r"^\s*(?:здравствуйте|здрасьте|добрый\s+(?:день|вечер)|доброе\s+утро|привет|сәлеметсіз\s+бе|салем|сәлем|hello|hi)[\s,.!]*", re.I)

class ProviderError(RuntimeError):
    pass


@dataclass
class ModelTurn:
    reply: str
    updates: dict = field(default_factory=dict)
    intent: str = "collect"
    user_confirmed: bool = False
    handoff_reason: str = ""
    usage: dict = field(default_factory=dict)
    asked: str = ""            # field the reply asks for (offline provider only)

    @classmethod
    def from_json(cls, data, usage=None):
        updates = {k: v for k, v in (data.get("updates") or {}).items() if k in FIELDS and v}
        return cls(reply=str(data.get("reply", "")), updates=updates,
                   intent=data.get("intent", "collect"), user_confirmed=bool(data.get("user_confirmed")),
                   handoff_reason=data.get("handoff_reason", "") or "", usage=usage or {})


@dataclass
class TurnContext:
    kb: dict
    system: str
    history: list          # [{"role": "user"|"assistant", "content": str}]
    user_text: str
    user_content: str
    lead: object
    status: str
    asked: set
    last_question: str = ""


def estimate_tokens(text):
    """Rough token estimate for Russian text (about 3 characters per token). An estimate, not a count."""
    return math.ceil(len(text or "") / 3)


def estimated_usage(ctx, output_text):
    prompt = ctx.system + "".join(m["content"] for m in ctx.history) + ctx.user_content
    return {"input_tokens": estimate_tokens(prompt), "output_tokens": estimate_tokens(output_text),
            "cache_read": 0, "cache_write": 0, "estimated": True}


# ---------------------------------------------------------------- offline rules

_DAY = (r"сегодня|завтра|послезавтра|в понедельник|во вторник|в среду|в четверг|в пятницу|в субботу|"
        r"в воскресенье|в выходные|на выходных|в будни|сейчас|как можно скорее|побыстрее|бүгін|ертең")
_PART = r"утром|дн[её]м|вечером|после обеда|до обеда|кешке|таңертең|түсте"
_CLOCK = (r"после \d{1,2}(?::\d{2})?|до \d{1,2}(?::\d{2})?|с \d{1,2}(?::\d{2})? до \d{1,2}(?::\d{2})?|"
          r"в \d{1,2}(?::\d{2})?(?!\s*(?:комнат|раз|шт))|\d{1,2}:\d{2}")
_TIME = re.compile(rf"(?<!\w)(?:{_DAY}|{_PART}|{_CLOCK})(?!\w)", re.IGNORECASE)
_NAME_PATTERNS = [
    re.compile(r"(?i:меня зовут)\s+([A-ZА-ЯЁӘҒҚҢӨҰҮҺІ][\w-]{1,20})"),
    re.compile(r"(?i:менің атым)\s+([A-ZА-ЯЁӘҒҚҢӨҰҮҺІ][\w-]{1,20})"),
    re.compile(r"^\s*(?i:я)\s+([A-ZА-ЯЁ][а-яё-]{1,20})\s*$"),
    re.compile(r",\s*([A-ZА-ЯЁ][а-яё]{2,20})\s*$"),
]
_FIRST_WORD = re.compile(r"^\s*([A-ZА-ЯЁӘҒҚҢӨҰҮҺІ][a-zа-яёәғқңөұүһі-]{1,20})(?=[\s,.!]|$)")
_NOT_NAMES = {"да", "нет", "ок", "окей", "спасибо", "здравствуйте", "добрый", "привет", "сегодня", "завтра",
              "послезавтра", "хорошо", "ладно", "отлично", "верно", "иә", "жоқ", "рахмет", "сәлем", "салем",
              "мастер", "нужен", "нужно", "телефон", "номер", "меня", "мой", "моё", "мое", "менің"}
_ADDRESS_HINT = re.compile(r"(?:мкр\.?|микрорайон|возле|рядом с|около|ул\.|улица|жк)\s*[^,.;!?]{2,40}", re.IGNORECASE)
_VISIT_PRESSURE = re.compile(r"подтверди|сможет приехать|точно приедет|во сколько приедет|когда приедет", re.IGNORECASE)

QUESTIONS = {
    "task": "Расскажите, пожалуйста, что нужно сделать?",
    "district": "В каком районе Алматы нужно выполнить работу? Можно добавить ориентир.",
    "time_window": "Когда вам удобно, чтобы мастер приехал? Укажите день и примерное время.",
    "name": "Как к вам обращаться?",
    "phone": "Оставьте, пожалуйста, номер телефона для связи.",
}
ACK = {"district": "Район: {}.", "time_window": "Удобное время: {}."}


def extract_time(text):
    spans = [m.group(0) for m in _TIME.finditer(text or "")]
    return " ".join(spans).strip()


def extract_name(text, last_question):
    for p in _NAME_PATTERNS:
        m = p.search(text or "")
        if m and m.group(1).lower() not in _NOT_NAMES:
            return m.group(1)
    if last_question == "name":
        m = _FIRST_WORD.search(text or "")
        if m and m.group(1).lower() not in _NOT_NAMES:
            return m.group(1)
    return ""


class OfflineProvider:
    """Rules and templates for the demo without a model. Clearly labelled; not an LLM."""
    name = "offline"
    model = "rules-v1"
    sends_data_out = False

    def __init__(self, kb):
        self.kb = kb

    def next_turn(self, ctx):
        text, lead, kb = ctx.user_text, ctx.lead, self.kb
        updates, parts = {}, []
        topics = [t for t, _ in kbmod.faq_answers(text, kb)]

        p = phonemod.extract(text)
        if p:
            updates["phone"] = p
        d = kbmod.match_district(text, kb)
        if d:
            updates["district"] = d
            hint = _ADDRESS_HINT.search(text)
            if hint:
                updates["address_hint"] = hint.group(0).strip()
        if "hours" not in topics:
            t = extract_time(text)
            if t:
                updates["time_window"] = t
        n = extract_name(text, ctx.last_question)
        if n and n != d:
            updates["name"] = n
        s = kbmod.match_service(text, kb)
        if s and not lead.service:
            updates["service"] = s
        wordy = len(text.split()) >= 4
        bare_yes = guards.is_yes(text) and len(text.split()) <= 3
        if (not lead.task and (s or (wordy and not topics and not d)) and not bare_yes
                and not guards.is_sales_question(text)):
            task = re.sub(r"\+?\d[\d\s\-()]{6,}\d", "", text).strip(" ,.")
            task = _GREETING.sub("", task).strip(" ,.!") or task
            updates["task"] = task[:1].upper() + task[1:300]

        if ctx.status == "collecting" and not ctx.history:
            parts.append(f"Здравствуйте! Я виртуальный помощник компании «{kb['company']}».")
            if guards.detect_language(text) == "kk":
                parts[-1] = ("Сәлеметсіз бе! Я виртуальный помощник компании «" + kb["company"] +
                             "». Можно писать по-русски или по-казахски.")
        for _, answer in kbmod.faq_answers(text, kb)[:2]:
            parts.append(answer)
        if _VISIT_PRESSURE.search(text):
            parts.append(guards.VISIT_SAFE)
        if phonemod.looks_like_phone_attempt(text) and "phone" not in updates:
            parts.append("Похоже, в номере не хватает цифр. Напишите его в формате +7 7XX XXX XX XX.")

        merged = {f: (updates.get(f) or getattr(lead, f)) for f in FIELDS}
        for f, tmpl in ACK.items():
            if f in updates and ctx.status == "collecting":
                parts.append(tmpl.format(merged[f]))
        missing = [f for f in REQUIRED if not merged.get(f)]
        asked = ""
        if missing:
            for f in ASK_ORDER:
                if f == "name":  # optional: asked once, right before the phone
                    if not merged["name"] and "name" not in ctx.asked:
                        asked = "name"
                        break
                    continue
                if not merged.get(f):
                    asked = f
                    break
            parts.append(QUESTIONS[asked])
        reply = " ".join(parts)
        intent = "collect" if missing else "confirm"
        turn = ModelTurn(reply=reply, updates=updates, intent=intent, asked=asked)
        turn.usage = estimated_usage(ctx, json.dumps({"reply": reply, "updates": updates}, ensure_ascii=False))
        return turn


# ---------------------------------------------------------------- Claude

class AnthropicProvider:
    """Claude via the official SDK with structured output (output_config.format)."""
    name = "anthropic"
    sends_data_out = True

    def __init__(self, model=None, effort="low", client=None):
        self.model = model or os.environ.get("OKNO_MODEL") or "claude-opus-5-5"
        self.effort = effort
        self._client = client

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic  # optional dependency
            except ImportError as e:  # pragma: no cover - depends on the environment
                raise ProviderError("pip install anthropic") from e
            self._client = anthropic.Anthropic()
        return self._client

    def next_turn(self, ctx):
        client = self._get_client()
        kwargs = dict(
            model=self.model,
            max_tokens=4096,
            system=[{"type": "text", "text": ctx.system, "cache_control": {"type": "ephemeral"}}],
            messages=ctx.history + [{"role": "user", "content": ctx.user_content}],
            output_config={"format": {"type": "json_schema", "schema": TURN_SCHEMA}, "effort": self.effort},
        )
        try:
            if self.model in FALLBACK_MODELS:
                response = client.beta.messages.create(**kwargs, betas=["server-side-fallback-2026-07-01"],
                                                       fallbacks="default")
            else:
                response = client.messages.create(**kwargs)
        except Exception as e:  # SDK errors: network, auth, rate limits
            raise ProviderError(f"{type(e).__name__}: {e}") from e
        u = response.usage
        usage = {"input_tokens": u.input_tokens or 0, "output_tokens": u.output_tokens or 0,
                 "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
                 "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0, "estimated": False}
        if response.stop_reason == "refusal":
            return ModelTurn(reply="", intent="handoff", handoff_reason="model_refusal", usage=usage)
        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            return ModelTurn.from_json(json.loads(text), usage)
        except json.JSONDecodeError as e:
            raise ProviderError(f"model returned invalid JSON: {text[:200]}") from e


# ---------------------------------------------------------------- Gemini

class GeminiProvider:
    """Gemini via Google's OpenAI-compatible endpoint; key in GEMINI_API_KEY (Bearer)."""
    name = "gemini"
    sends_data_out = True
    URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

    def __init__(self, model=None, api_key=None, opener=None):
        self.model = model or os.environ.get("OKNO_MODEL") or "gemini-2.5-flash-lite"
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self._open = opener or urllib.request.urlopen

    def next_turn(self, ctx):
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": ctx.system}] + ctx.history
                        + [{"role": "user", "content": ctx.user_content}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "okno_turn", "schema": TURN_SCHEMA, "strict": True}},
        }
        req = urllib.request.Request(self.URL, data=json.dumps(body).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {self.api_key}"})
        try:
            with self._open(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            raise ProviderError(f"{type(e).__name__}: {e}") from e
        usage = {"input_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                 "output_tokens": data.get("usage", {}).get("completion_tokens", 0),
                 "cache_read": 0, "cache_write": 0, "estimated": False}
        content = data["choices"][0]["message"].get("content") or ""
        try:
            return ModelTurn.from_json(json.loads(content), usage)
        except json.JSONDecodeError as e:
            raise ProviderError(f"model returned invalid JSON: {content[:200]}") from e


# ---------------------------------------------------------------- replay (tests)

class ReplayProvider:
    name = "replay"
    model = "recorded"
    sends_data_out = True

    def __init__(self, turns):
        self.turns = list(turns)

    def next_turn(self, ctx):
        if not self.turns:
            raise ProviderError("no more recorded turns")
        item = self.turns.pop(0)
        if isinstance(item, Exception):
            raise item
        return ModelTurn.from_json(item, {"input_tokens": 0, "output_tokens": 0, "estimated": True})


def make_provider(name, kb, model=None):
    """name: offline | anthropic | gemini | auto (anthropic if ANTHROPIC_API_KEY, gemini if GEMINI_API_KEY)."""
    if name == "auto":
        name = ("anthropic" if os.environ.get("ANTHROPIC_API_KEY")
                else "gemini" if os.environ.get("GEMINI_API_KEY") else "offline")
    if name == "offline":
        return OfflineProvider(kb)
    if name == "anthropic":
        return AnthropicProvider(model)
    if name == "gemini":
        return GeminiProvider(model)
    raise ValueError(f"unknown provider {name!r}")
