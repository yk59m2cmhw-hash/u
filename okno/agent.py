"""Conversation engine: one customer dialog from first message to handoff.

Deterministic code owns the rules (emergencies, prices, visit promises, required fields, the summary the
customer confirms); the model only writes replies and extracts fields.
"""
from . import guards
from . import kb as kbmod
from . import phone as phonemod
from .lead import LABELS, Lead
from .prompts import build_system, build_user_content
from .providers import ProviderError, TurnContext

HANDOFF_REPLIES = {
    "lead_ready": "Спасибо! Заявка передана сотруднику. {callback}",
    "urgent": "Заявка передана сотруднику как срочная.",
    "human_request": "Передаю ваш вопрос сотруднику — он свяжется с вами.",
    "complaint": "Мне жаль, что так вышло. Передаю ваше обращение сотруднику — он свяжется с вами.",
    "out_of_scope": "Этот вопрос лучше уточнит сотрудник — передаю ему ваше сообщение.",
    "too_long": "Похоже, мне не удаётся собрать заявку. Передаю диалог сотруднику — он свяжется с вами.",
    "model_refusal": "Передаю ваш вопрос сотруднику — он свяжется с вами.",
}
MODEL_HANDOFF_REASONS = {"out_of_scope", "urgent", "human_request", "complaint", "model_refusal"}


class Conversation:
    def __init__(self, kb, provider, channel="web", known_phone=None, max_user_turns=12, sinks=None):
        self.kb = kb
        self.provider = provider
        self.system = build_system(kb)
        self.lead = Lead(channel=channel)
        if known_phone:
            self.lead.phone = phonemod.normalize(known_phone) or known_phone
        self.status = "collecting"   # collecting | confirming | needs_phone | handed_off | closed
        self.history = []
        self.asked = set()
        self.last_question = ""
        self.pending_reason = ""
        self.handoff_reason = ""
        self.user_turns = 0
        self.max_user_turns = max_user_turns
        self.sinks = sinks or []
        self.flags = []
        self.usage = {"input_tokens": 0, "output_tokens": 0, "cache_read": 0, "cache_write": 0,
                      "model_calls": 0, "estimated": False}
        self.delivery = []

    # ------------------------------------------------------------- public

    def handle(self, text):
        text = (text or "").strip()
        if self.status in ("handed_off", "closed"):
            return self._result("Ваше обращение уже передано сотруднику. Если нужно что-то ещё — напишите, "
                                "и я соберу новую заявку." if self.status == "handed_off"
                                else "Хорошо! Если понадобится помощь — пишите.", record=False)
        self.user_turns += 1
        self.lead.language = guards.detect_language(text, self.lead.language)

        kind = guards.detect_urgent(text)
        if kind and self.status != "needs_phone":
            self.lead.urgent = kind
            self.lead.task = self.lead.task or text[:300]
            self._light_extract(text)
            return self._handoff("urgent", user_text=text, prefix=guards.SAFETY[kind])

        if self.status == "needs_phone":
            p = phonemod.extract(text)
            if p:
                self.lead.phone = p
                return self._handoff(self.pending_reason, user_text=text)
            return self._reply(text, "Напишите, пожалуйста, номер телефона в формате +7 7XX XXX XX XX — "
                                     "без него сотрудник не сможет с вами связаться.")

        if guards.wants_human(text):
            self._light_extract(text)
            return self._handoff("human_request", user_text=text)
        if guards.is_complaint(text):
            self.lead.task = self.lead.task or text[:300]
            self._light_extract(text)
            return self._handoff("complaint", user_text=text)
        if guards.mentions_other_city(text, self.kb.get("city", "")):
            self.lead.task = self.lead.task or text[:300]
            self._light_extract(text)
            return self._handoff("out_of_scope", user_text=text,
                                 prefix=f"Сейчас мы работаем только по городу {self.kb.get('city', '')}.")
        if guards.is_cancel(text):
            self.status = "closed"
            return self._reply(text, "Хорошо, заявку не отправляю. Если понадобится мастер — пишите в любое время.")
        if guards.is_decline(text) and not self.lead.task:
            self.status = "closed"
            return self._reply(text, "Хорошо! Если понадобится мастер — пишите в любое время.")

        if self.status == "confirming" and guards.is_yes(text) and self.lead.is_complete():
            return self._handoff("lead_ready", user_text=text)

        turn = self._model_turn(text)
        if turn is None:
            return self._handoff("model_refusal", user_text=text)

        if turn.intent == "handoff" and turn.handoff_reason in MODEL_HANDOFF_REASONS:
            self.lead.merge(turn.updates, self.kb)
            reply, flags = guards.sanitize_reply(turn.reply) if turn.reply else ("", [])
            self.flags += flags
            return self._handoff(turn.handoff_reason, user_text=text, prefix=reply)

        rejected = self.lead.merge(turn.updates, self.kb)
        reply, flags = guards.sanitize_reply(turn.reply)
        self.flags += flags
        if turn.asked:
            self.asked.add(turn.asked)
            self.last_question = turn.asked
        if "phone" in rejected and "в формате +7" not in reply:
            reply += " Проверьте, пожалуйста, номер: нужен формат +7 7XX XXX XX XX."

        if self.lead.is_complete():
            if self.status == "confirming" and turn.user_confirmed:
                return self._handoff("lead_ready", user_text=text)
            if self.status == "collecting" and not self.lead.name and "name" not in self.asked:
                # The name is optional, but ask once before the summary (it was skipped if the phone came first).
                self.asked.add("name")
                self.last_question = "name"
                lead_in = reply if reply and "?" not in reply else ""
                return self._reply(text, (lead_in + " " if lead_in else "") + "Как к вам обращаться?")
            self.status = "confirming"
            self.last_question = "confirm"
            intro = reply if reply and "?" not in reply else ""
            # The summary quotes the customer verbatim, so it skips the price filter (intro is already clean).
            return self._reply(text, (intro + "\n\n" if intro else "") + self.summary(), sanitize=False)

        if self.user_turns >= self.max_user_turns:
            return self._handoff("too_long", user_text=text)
        if not turn.asked:
            nxt = next((f for f in ("task", "district", "time_window", "phone") if not getattr(self.lead, f)), "")
            if nxt:
                self.asked.add(nxt)
                self.last_question = nxt
        return self._reply(text, reply)

    def summary(self):
        rows = []
        for key in ("task", "district", "address_hint", "time_window", "name", "phone"):
            val = getattr(self.lead, key)
            if val:
                note = kbmod.district_note(val, self.kb) if key == "district" else ""
                rows.append(f"— {LABELS[key]}: {val}" + (f" ({note})" if note else ""))
        return ("Проверьте, пожалуйста, заявку:\n" + "\n".join(rows) +
                "\nВсё верно? Если что-то не так — напишите, что исправить.")

    # ------------------------------------------------------------- internals

    def _model_turn(self, text):
        external = getattr(self.provider, "sends_data_out", False)
        history, model_text = list(self.history), text
        if external:
            # Personal-data minimisation (D-022): the phone is captured by code; the model never sees it.
            p = phonemod.extract(text)
            if p:
                self.lead.phone = p
            model_text = phonemod.redact(text)
            history = [{"role": m["role"], "content": phonemod.redact(m["content"])} for m in history]
        ctx = TurnContext(kb=self.kb, system=self.system, history=history, user_text=model_text,
                          user_content=build_user_content(model_text, self.lead, self.status, mask_phone=external),
                          lead=self.lead, status=self.status, asked=set(self.asked),
                          last_question=self.last_question)
        try:
            turn = self.provider.next_turn(ctx)
        except ProviderError as e:
            self.flags.append(f"provider_error: {e}")
            return None
        for k in ("input_tokens", "output_tokens", "cache_read", "cache_write"):
            self.usage[k] += int(turn.usage.get(k, 0) or 0)
        self.usage["model_calls"] += 1
        self.usage["estimated"] = self.usage["estimated"] or bool(turn.usage.get("estimated"))
        return turn

    def _light_extract(self, text):
        """Deterministic phone and district capture for handoff paths that skip the model."""
        p = phonemod.extract(text)
        if p and not self.lead.phone:
            self.lead.phone = p
        d = kbmod.match_district(text, self.kb)
        if d and not self.lead.district:
            self.lead.merge({"district": d}, self.kb)

    def _handoff(self, reason, user_text, prefix=""):
        reason = reason or "out_of_scope"
        if not self.lead.phone:
            self.status = "needs_phone"
            self.pending_reason = reason
            ask = ("Срочно передам сотруднику — напишите, пожалуйста, ваш номер телефона."
                   if reason == "urgent" else "Чтобы сотрудник мог связаться с вами, напишите, пожалуйста, номер телефона.")
            return self._reply(user_text, " ".join(x for x in (prefix, ask) if x))
        self.status = "handed_off"
        self.handoff_reason = reason
        card = self.lead.card(self.kb["company"], reason)
        for sink in self.sinks:
            try:
                self.delivery.append(sink.deliver(card, self.lead.to_dict(), reason))
            except Exception as e:  # a failing sink must not break the dialog
                self.delivery.append({"sink": type(sink).__name__, "ok": False, "error": str(e)})
        base = HANDOFF_REPLIES.get(reason, HANDOFF_REPLIES["out_of_scope"]).format(
            callback=self.kb.get("callback_promise", ""))
        if reason == "urgent" and self.kb.get("emergency_note"):
            base += " " + self.kb["emergency_note"]
        return self._reply(user_text, " ".join(x for x in (prefix, base) if x).strip())

    def _reply(self, user_text, reply, sanitize=True):
        if not self.history and self.kb.get("privacy_notice"):  # shown once, in the first reply
            reply = f"{reply}\n\n{self.kb['privacy_notice']}"
        if sanitize:  # final safety net for every model-written path
            reply, flags = guards.sanitize_reply(reply)
            self.flags += flags
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": reply})
        return self._result(reply)

    def _result(self, reply, record=True):
        return {"reply": reply, "status": self.status, "lead": self.lead.to_dict(),
                "missing": self.lead.missing(), "handoff_reason": self.handoff_reason,
                "card": self.lead.card(self.kb["company"], self.handoff_reason) if self.status == "handed_off" else "",
                "usage": dict(self.usage)}
