"""Channel adapters, webhooks and the owner panel. Run: python3 -m unittest discover -s okno/tests -t ."""
import hashlib
import hmac
import io
import json
import pathlib
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from okno import kb as kbmod
from okno.channels import telegram as tg
from okno.channels import whatsapp as wa
from okno.channels.router import NON_TEXT_REPLY, Router
from okno.handoff import JsonlSink
from okno.web import make_server

KB = kbmod.load()

WA_PAYLOAD = {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [{"field": "messages", "value": {
    "messaging_product": "whatsapp", "metadata": {"display_phone_number": "77000000000", "phone_number_id": "123"},
    "contacts": [{"profile": {"name": "Айгерим"}, "wa_id": "77011234567"}],
    "messages": [{"from": "77011234567", "id": "wamid.1", "timestamp": "1700000000", "type": "text",
                  "text": {"body": "Течёт смеситель на кухне"}}]}}]}]}
TG_UPDATE = {"update_id": 1, "message": {"message_id": 5, "from": {"id": 42, "first_name": "Ерлан"},
                                          "chat": {"id": 42, "type": "private"}, "date": 1700000000,
                                          "text": "Нужно собрать шкаф"}}


class FakeClient:
    def __init__(self):
        self.sent = []

    def send_text(self, to, text):
        self.sent.append((str(to), text))
        return {"ok": True}


class Adapters(unittest.TestCase):
    def test_whatsapp_signature(self):
        body = json.dumps(WA_PAYLOAD).encode("utf-8")
        sig = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
        self.assertTrue(wa.verify_signature("secret", body, sig))
        self.assertFalse(wa.verify_signature("secret", body + b" ", sig))
        self.assertFalse(wa.verify_signature("", body, sig))

    def test_whatsapp_subscription(self):
        ok = {"hub.mode": "subscribe", "hub.verify_token": "t", "hub.challenge": "42"}
        self.assertEqual(wa.verify_subscription(ok, "t"), "42")
        self.assertIsNone(wa.verify_subscription(dict(ok, **{"hub.verify_token": "x"}), "t"))

    def test_whatsapp_parse_and_send(self):
        msgs = wa.parse_inbound(WA_PAYLOAD)
        self.assertEqual(msgs[0]["phone"], "+77011234567")
        self.assertEqual(msgs[0]["name"], "Айгерим")
        seen = {}

        class Resp(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def opener(req, timeout=0):
            seen["url"], seen["body"] = req.full_url, json.loads(req.data.decode("utf-8"))
            seen["auth"] = req.headers.get("Authorization")
            return Resp(b'{"messages": [{"id": "wamid.2"}]}')

        wa.WhatsAppClient("tok", "123", "v23.0", opener).send_text("+77011234567", "Здравствуйте!")
        self.assertEqual(seen["url"], "https://graph.facebook.com/v23.0/123/messages")
        self.assertEqual(seen["body"]["to"], "77011234567")
        self.assertEqual(seen["auth"], "Bearer tok")

    def test_telegram_parse_and_secret(self):
        m = tg.parse_update(TG_UPDATE)
        self.assertEqual((m["user"], m["text"]), ("42", "Нужно собрать шкаф"))
        self.assertIsNone(tg.parse_update({"message": {"chat": {"id": -1, "type": "group"}, "text": "x"}}))
        self.assertTrue(tg.verify_secret("s", "s"))
        self.assertFalse(tg.verify_secret("s", "x"))
        self.assertFalse(tg.verify_secret("", ""))


class RouterTests(unittest.TestCase):
    def test_whatsapp_phone_is_known_and_sessions_persist(self):
        r = Router(KB, "offline")
        msg = wa.parse_inbound(WA_PAYLOAD)[0]
        r.handle("whatsapp", msg)
        conv = r.sessions[("whatsapp", "77011234567")][0]
        self.assertEqual(conv.lead.phone, "+77011234567")
        r.handle("whatsapp", dict(msg, text="Бостандыкский"))
        self.assertEqual(conv.lead.district, "Бостандыкский")
        self.assertEqual(r.handle("whatsapp", dict(msg, text="", unsupported="image")), NON_TEXT_REPLY)

    def test_new_session_after_handoff(self):
        r = Router(KB, "offline")
        user = {"user": "7", "text": "Позовите менеджера", "phone": "+77011112233"}
        r.handle("whatsapp", user)
        first = r.sessions[("whatsapp", "7")][0]
        self.assertEqual(first.status, "handed_off")
        r.handle("whatsapp", dict(user, text="Нужно повесить полку"))
        self.assertIsNot(r.sessions[("whatsapp", "7")][0], first)


class Server(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.kb_path = pathlib.Path(self.dir) / "company.json"
        shutil.copy(kbmod.DEFAULT_KB, self.kb_path)
        self.leads = pathlib.Path(self.dir) / "leads.jsonl"
        self.wa, self.tg = FakeClient(), FakeClient()
        env = {"WHATSAPP_APP_SECRET": "secret", "WHATSAPP_VERIFY_TOKEN": "vt", "TELEGRAM_WEBHOOK_SECRET": "ts",
               "OKNO_ADMIN_TOKEN": "adm", "OKNO_LEADS_FILE": str(self.leads)}
        self.server, self.app = make_server("127.0.0.1", 0, "offline", kb_path=self.kb_path,
                                            sinks=[JsonlSink(self.leads)], env=env,
                                            wa_client=self.wa, tg_client=self.tg, async_channels=False)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def req(self, path, data=None, headers=None, method=None):
        body = None if data is None else (data if isinstance(data, bytes) else json.dumps(data).encode("utf-8"))
        r = urllib.request.Request(self.base + path, data=body, headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(r, timeout=5) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def test_whatsapp_webhook(self):
        self.assertEqual(self.req("/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=vt&hub.challenge=99"), (200, "99"))
        self.assertEqual(self.req("/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=no&hub.challenge=99")[0], 403)
        body = json.dumps(WA_PAYLOAD).encode("utf-8")
        self.assertEqual(self.req("/webhooks/whatsapp", body, {"X-Hub-Signature-256": "sha256=bad"})[0], 403)
        sig = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
        self.assertEqual(self.req("/webhooks/whatsapp", body, {"X-Hub-Signature-256": sig})[0], 200)
        self.assertEqual(self.wa.sent[0][0], "77011234567")
        self.assertIn("В каком районе", self.wa.sent[0][1])

    def test_telegram_webhook(self):
        self.assertEqual(self.req("/webhooks/telegram", TG_UPDATE, {"X-Telegram-Bot-Api-Secret-Token": "x"})[0], 403)
        self.assertEqual(self.req("/webhooks/telegram", TG_UPDATE, {"X-Telegram-Bot-Api-Secret-Token": "ts"})[0], 200)
        self.assertEqual(self.tg.sent[0][0], "42")

    def test_admin_panel(self):
        self.assertEqual(self.req("/admin")[0], 404)
        self.assertEqual(self.req("/admin?token=adm")[0], 200)
        # a lead appears after a handed-off dialog
        for text in ["Позовите менеджера", "+77011112233"]:
            self.req("/api/message", {"sid": "s1", "text": text})
        code, body = self.req("/api/admin/leads", headers={"X-Okno-Token": "adm"})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["leads"][0]["reason"], "human_request")
        code, csv_text = self.req("/api/admin/leads.csv?token=adm")
        self.assertIn("+77011112233", csv_text)
        # knowledge base update: invalid is rejected, valid is saved and used
        self.assertEqual(self.req("/api/admin/kb", {"company": "X"}, {"X-Okno-Token": "adm"})[0], 400)
        kb = json.loads(self.kb_path.read_text(encoding="utf-8"))
        kb["company"] = "Тест Мастер"
        self.assertEqual(self.req("/api/admin/kb", kb, {"X-Okno-Token": "adm"})[0], 200)
        self.assertEqual(json.loads(self.req("/api/info")[1])["company"], "Тест Мастер")
        self.assertEqual(self.req("/api/admin/kb", kb, {"X-Okno-Token": "wrong"})[0], 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
