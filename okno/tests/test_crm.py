"""CRM sinks. Run: python3 -m unittest discover -s okno/tests -t ."""
import io
import json
import unittest

from okno.crm import AmoCrmSink, Bitrix24Sink

LEAD = {"service": "Сантехника", "task": "течёт смеситель", "name": "Айгерим", "phone": "+77011234567",
        "channel": "whatsapp", "urgent": ""}


class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


class CRM(unittest.TestCase):
    def test_bitrix24_lead_add(self):
        seen = []

        def opener(req, timeout=0):
            seen.append((req.full_url, json.loads(req.data.decode("utf-8"))))
            return Resp(b'{"result": 101}')

        out = Bitrix24Sink("https://demo.bitrix24.kz/rest/1/abc", opener).deliver("card", LEAD, "lead_ready")
        self.assertEqual(out, {"sink": "bitrix24", "ok": True, "id": 101})
        url, body = seen[0]
        self.assertEqual(url, "https://demo.bitrix24.kz/rest/1/abc/crm.lead.add.json")
        self.assertEqual(body["fields"]["PHONE"][0]["VALUE"], "+77011234567")
        self.assertEqual(body["fields"]["TITLE"], "Okno: Сантехника")

    def test_amocrm_complex_and_note(self):
        seen = []

        def opener(req, timeout=0):
            seen.append((req.full_url, json.loads(req.data.decode("utf-8")), req.headers.get("Authorization")))
            return Resp(b'[{"id": 555, "contact_id": 7}]' if req.full_url.endswith("/complex") else b"{}")

        out = AmoCrmSink("https://demo.amocrm.ru/", "tok", opener).deliver("card", dict(LEAD, urgent="water"), "urgent")
        self.assertEqual(out["id"], 555)
        self.assertEqual(seen[0][0], "https://demo.amocrm.ru/api/v4/leads/complex")
        self.assertTrue(seen[0][1][0]["name"].startswith("СРОЧНО"))
        self.assertEqual(seen[0][2], "Bearer tok")
        self.assertEqual(seen[1][0], "https://demo.amocrm.ru/api/v4/leads/555/notes")


if __name__ == "__main__":
    unittest.main(verbosity=2)
