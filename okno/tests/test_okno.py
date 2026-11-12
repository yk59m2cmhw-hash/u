"""Unit tests for the Okno prototype. Run: python3 -m unittest discover -s okno/tests -t ."""
import io
import json
import pathlib
import tempfile
import threading
import unittest
import urllib.request

from okno import guards, phone
from okno import kb as kbmod
from okno.agent import Conversation
from okno.evals import run as evalrun
from okno.handoff import JsonlSink, TelegramSink, WebhookSink
from okno.lead import Lead
from okno.prompts import TURN_SCHEMA, build_system, build_user_content
from okno.providers import GeminiProvider, OfflineProvider, ProviderError, ReplayProvider, extract_time
from okno.web import make_server

KB = kbmod.load()


def offline():
    return OfflineProvider(KB)


def turn(reply, intent="collect", confirmed=False, reason="", **updates):
    fields = {f: "" for f in ("service", "task", "district", "address_hint", "time_window", "name", "phone")}
    fields.update(updates)
    return {"reply": reply, "updates": fields, "intent": intent, "user_confirmed": confirmed, "handoff_reason": reason}


class Phones(unittest.TestCase):
    def test_formats(self):
        for raw in ["+7 701 123 45 67", "8 (701) 123-45-67", "87011234567", "7011234567", "+77011234567"]:
            self.assertEqual(phone.normalize(raw), "+77011234567", raw)

    def test_invalid(self):
        for raw in ["123", "", None, "8701123"]:
            self.assertIsNone(phone.normalize(raw), raw)

    def test_extract_and_attempt(self):
        self.assertEqual(phone.extract("Данияр, 8 778 999 00 11"), "+77789990011")
        self.assertTrue(phone.looks_like_phone_attempt("123"))
        self.assertFalse(phone.looks_like_phone_attempt("+7 701 123 45 67"))
        self.assertTrue(phone.is_kz("+77011234567"))


class Guards(unittest.TestCase):
    def test_price_detected(self):
        for t in ["Замена стоит 5000 тг.", "Обычно от 10 тыс.", "Около 15 тысяч", "Цена 7 000 ₸", "это будет стоить 3000"]:
            self.assertTrue(guards.has_price(t), t)

    def test_no_false_price(self):
        for t in ["Сотрудник перезвонит через 15 минут.", "Мастера работают с 9:00 до 20:00.",
                  "Ваш телефон +77011234567.", "Стоимость назовёт сотрудник после уточнения деталей.", "Звоните 112."]:
            self.assertFalse(guards.has_price(t), t)

    def test_visit_promise(self):
        self.assertTrue(guards.has_visit_promise("Мастер приедет завтра в 18:00."))
        self.assertTrue(guards.has_visit_promise("Выезд подтверждён."))
        self.assertTrue(guards.has_visit_promise("Записал вас на завтра."))
        self.assertFalse(guards.has_visit_promise("Сотрудник свяжется с вами, чтобы подтвердить время."))

    def test_sanitize(self):
        clean, flags = guards.sanitize_reply("Это стоит 5000 тг. Мастер приедет завтра. В каком районе?")
        self.assertIn("price_removed", flags)
        self.assertIn("visit_promise_removed", flags)
        self.assertNotIn("5000", clean)
        self.assertIn("В каком районе?", clean)
        self.assertEqual(guards.sanitize_reply("")[0], "")

    def test_urgent_language_yes(self):
        self.assertEqual(guards.detect_urgent("Пахнет газом!"), "gas")
        self.assertEqual(guards.detect_urgent("Прорвало трубу"), "water")
        self.assertEqual(guards.detect_urgent("искрит розетка"), "electric")
        self.assertIsNone(guards.detect_urgent("течёт смеситель"))
        self.assertEqual(guards.detect_language("Сәлеметсіз бе"), "kk")
        self.assertEqual(guards.detect_language("Здравствуйте"), "ru")
        self.assertTrue(guards.is_yes("Да, всё верно"))
        self.assertTrue(guards.is_yes("иә"))
        self.assertFalse(guards.is_yes("Нет, район другой"))


class KnowledgeBase(unittest.TestCase):
    def test_district_and_service(self):
        self.assertEqual(kbmod.match_district("возле Орбиты", KB), "Бостандыкский")
        self.assertEqual(kbmod.match_district("Самал-2", KB), "Медеуский")
        self.assertEqual(kbmod.match_service("поменять проводку в ванной", KB), "Электрика")
        self.assertEqual(kbmod.match_service("ремонт ванной под ключ", KB), "Ремонт квартир")

    def test_price_faq_has_no_numbers(self):
        answer = dict(kbmod.faq_answers("Сколько стоит?", KB))["price"]
        self.assertFalse(guards.has_price(answer))

    def test_time_extraction(self):
        self.assertEqual(extract_time("Завтра после 18:00"), "Завтра после 18:00")
        self.assertEqual(extract_time("в пятницу с 10 до 13"), "в пятницу с 10 до 13")
        self.assertEqual(extract_time("ертең кешке"), "ертең кешке")
        self.assertEqual(extract_time("течёт кран"), "")


class Prompts(unittest.TestCase):
    def test_system_and_schema(self):
        s = build_system(KB)
        self.assertIn("Никогда не называй стоимость", s)
        self.assertIn(KB["company"], s)
        self.assertEqual(set(TURN_SCHEMA["required"]), {"reply", "updates", "intent", "user_confirmed", "handoff_reason"})
        json.dumps(TURN_SCHEMA)
        content = build_user_content("привет", Lead(), "collecting")
        self.assertIn("Не хватает: task, district, time_window, phone", content)


class Dialogs(unittest.TestCase):
    def test_full_offline_dialog_hands_off(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "leads.jsonl"
            conv = Conversation(KB, offline(), sinks=[JsonlSink(path)])
            for m in ["Течёт смеситель на кухне", "Бостандыкский", "завтра после 18:00", "Айгерим", "+7 701 123 45 67"]:
                out = conv.handle(m)
            self.assertEqual(out["status"], "confirming")
            self.assertIn("Всё верно?", out["reply"])
            out = conv.handle("да")
            self.assertEqual(out["status"], "handed_off")
            self.assertIn("Телефон: +77011234567", out["card"])
            record = json.loads(path.read_text(encoding="utf-8").strip())
            self.assertEqual(record["lead"]["district"], "Бостандыкский")

    def test_urgent_asks_phone_then_hands_off(self):
        conv = Conversation(KB, offline())
        out = conv.handle("Пахнет газом на кухне")
        self.assertEqual(out["status"], "needs_phone")
        self.assertIn("112", out["reply"])
        out = conv.handle("+77025556677")
        self.assertEqual((out["status"], out["handoff_reason"]), ("handed_off", "urgent"))

    def test_whatsapp_known_phone_skips_question(self):
        conv = Conversation(KB, offline(), channel="whatsapp", known_phone="87011234567")
        conv.handle("Нужно собрать шкаф")
        conv.handle("Турксибский")
        out = conv.handle("в субботу утром")
        conv.handle("Ерлан")
        self.assertEqual(conv.lead.phone, "+77011234567")
        self.assertIn(conv.status, ("confirming",))

    def test_model_price_is_filtered_and_handoff_respected(self):
        provider = ReplayProvider([
            turn("Замена смесителя стоит 5000 тг. В каком районе?", task="замена смесителя"),
            turn("Этот вопрос уточнит сотрудник.", intent="handoff", reason="out_of_scope"),
        ])
        conv = Conversation(KB, provider, known_phone="+77011234567")
        out = conv.handle("Сколько стоит заменить смеситель?")
        self.assertNotIn("5000", out["reply"])
        self.assertIn("price_removed", conv.flags)
        out = conv.handle("А вы продаёте ламинат оптом?")
        self.assertEqual((out["status"], out["handoff_reason"]), ("handed_off", "out_of_scope"))

    def test_model_confirmation_and_provider_error(self):
        provider = ReplayProvider([
            turn("Принято.", task="повесить полку", district="Медеуский", time_window="завтра", phone="87011234567"),
            ProviderError("timeout"),
        ])
        conv = Conversation(KB, provider)
        out = conv.handle("Повесить полку, Медеуский, завтра, 87011234567")
        self.assertEqual(out["status"], "collecting")          # complete, but the optional name is asked once
        self.assertIn("Как к вам обращаться?", out["reply"])
        out = conv.handle("а можно ещё вопрос про гарантию?")
        self.assertEqual((out["status"], out["handoff_reason"]), ("handed_off", "model_refusal"))

    def test_invalid_model_phone_is_rejected(self):
        provider = ReplayProvider([turn("Спасибо.", task="люстра", phone="12")])
        conv = Conversation(KB, provider)
        out = conv.handle("люстра, телефон 12")
        self.assertEqual(conv.lead.phone, "")
        self.assertIn("+7 7XX", out["reply"])


class Sinks(unittest.TestCase):
    def test_telegram_and_webhook_payloads(self):
        sent = []

        class Resp(io.BytesIO):
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def opener(req, timeout=0):
            sent.append((req.full_url, json.loads(req.data.decode("utf-8"))))
            return Resp(b'{"ok": true}')

        self.assertTrue(TelegramSink("T", "42", opener).deliver("card", {}, "lead_ready")["ok"])
        self.assertTrue(WebhookSink("https://example.invalid/hook", opener).deliver("card", {"a": 1}, "urgent")["ok"])
        self.assertIn("/botT/sendMessage", sent[0][0])
        self.assertEqual(sent[0][1]["chat_id"], "42")
        self.assertEqual(sent[1][1]["reason"], "urgent")


class Gemini(unittest.TestCase):
    def test_parses_openai_compatible_response(self):
        body = {"choices": [{"message": {"content": json.dumps(turn("Здравствуйте! В каком районе?", task="кран"))}}],
                "usage": {"prompt_tokens": 1200, "completion_tokens": 40}}

        class Resp(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False

        seen = {}

        def opener(req, timeout=0):
            seen["auth"] = req.headers.get("Authorization")
            seen["body"] = json.loads(req.data.decode("utf-8"))
            return Resp(json.dumps(body).encode("utf-8"))

        conv = Conversation(KB, GeminiProvider(api_key="k", opener=opener))
        out = conv.handle("Течёт кран")
        self.assertEqual(seen["auth"], "Bearer k")
        self.assertEqual(seen["body"]["response_format"]["type"], "json_schema")
        self.assertEqual(out["lead"]["task"], "кран")
        self.assertEqual(conv.usage["input_tokens"], 1200)


class Web(unittest.TestCase):
    def test_server_roundtrip(self):
        server, app = make_server("127.0.0.1", 0, "offline", sinks=[])
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            html = urllib.request.urlopen(base + "/", timeout=5).read().decode("utf-8")
            self.assertIn("Okno", html)
            req = urllib.request.Request(base + "/api/message", method="POST",
                                         data=json.dumps({"text": "Течёт смеситель"}).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
            out = json.loads(urllib.request.urlopen(req, timeout=5).read().decode("utf-8"))
            self.assertEqual(out["status"], "collecting")
            self.assertTrue(out["sid"])
        finally:
            server.shutdown()
            server.server_close()


class Evals(unittest.TestCase):
    def test_offline_eval_passes_threshold(self):
        dialogs = json.loads(evalrun.DIALOGS.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(dialogs), 20)
        results = [evalrun.run_dialog(d, offline(), KB) for d in dialogs]
        passed = sum(r["passed"] for r in results)
        self.assertGreaterEqual(passed / len(results), 0.9, [r for r in results if not r["passed"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class Privacy(unittest.TestCase):
    def test_phone_never_reaches_external_model(self):
        seen = []

        class Capture(ReplayProvider):
            def next_turn(self, ctx):
                seen.append(ctx.user_content + " ".join(m["content"] for m in ctx.history))
                return super().next_turn(ctx)

        provider = Capture([turn("Принято. В каком районе?", task="полка"),
                            turn("Спасибо.", district="Медеуский", time_window="завтра")])
        conv = Conversation(KB, provider)
        conv.handle("Повесить полку, мой номер 8 701 123 45 67")
        conv.handle("Медеуский, завтра")
        self.assertEqual(conv.lead.phone, "+77011234567")
        for text in seen:
            self.assertNotIn("123 45 67", text)
            self.assertNotIn("7011234567", text)
        self.assertIn("[телефон]", seen[0])
        self.assertIn('"phone": "указан"', seen[1])

    def test_offline_mode_keeps_text(self):
        self.assertFalse(OfflineProvider.sends_data_out)
        self.assertEqual(phone.redact("звоните 87011234567 или 112"), "звоните [телефон] или 112")

    def test_privacy_notice_once(self):
        kb = dict(KB, privacy_notice="Мы обрабатываем имя и телефон только для заявки.")
        conv = Conversation(kb, offline())
        first = conv.handle("Течёт кран")["reply"]
        second = conv.handle("Медеуский")["reply"]
        self.assertIn("только для заявки", first)
        self.assertNotIn("только для заявки", second)
