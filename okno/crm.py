"""CRM handoff sinks: Bitrix24 (incoming webhook) and amoCRM / Kommo (API v4 with a long-lived token).

Environment:
  BITRIX24_WEBHOOK_URL   e.g. https://<portal>.bitrix24.kz/rest/<user_id>/<code>/   (CRM scope)
  AMOCRM_BASE_URL        e.g. https://<subdomain>.amocrm.ru   (or kommo.com)
  AMOCRM_TOKEN           long-lived token of a private integration
"""
import json
import urllib.request


def _title(lead):
    what = lead.get("service") or (lead.get("task") or "")[:60] or "Заявка"
    urgent = "СРОЧНО: " if lead.get("urgent") else ""
    return f"{urgent}Okno: {what}"


class Bitrix24Sink:
    def __init__(self, webhook_url, opener=None):
        self.base = webhook_url.rstrip("/") + "/"
        self._open = opener or urllib.request.urlopen

    def deliver(self, card, lead, reason):
        fields = {"TITLE": _title(lead), "NAME": lead.get("name") or "Клиент", "COMMENTS": card,
                  "SOURCE_DESCRIPTION": f"Okno, канал: {lead.get('channel', '')}, причина: {reason}"}
        if lead.get("phone"):
            fields["PHONE"] = [{"VALUE": lead["phone"], "VALUE_TYPE": "MOBILE"}]
        body = json.dumps({"fields": fields, "params": {"REGISTER_SONET_EVENT": "Y"}}, ensure_ascii=False)
        req = urllib.request.Request(self.base + "crm.lead.add.json", data=body.encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json"})
        with self._open(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return {"sink": "bitrix24", "ok": "result" in data, "id": data.get("result")}


class AmoCrmSink:
    def __init__(self, base_url, token, opener=None):
        self.base = base_url.rstrip("/")
        self.token = token
        self._open = opener or urllib.request.urlopen

    def _post(self, path, body):
        req = urllib.request.Request(self.base + path, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                     method="POST", headers={"Content-Type": "application/json",
                                                             "Authorization": f"Bearer {self.token}"})
        with self._open(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8") or "null")

    def deliver(self, card, lead, reason):
        contact = {"first_name": lead.get("name") or "Клиент"}
        if lead.get("phone"):
            contact["custom_fields_values"] = [{"field_code": "PHONE",
                                                "values": [{"value": lead["phone"], "enum_code": "MOB"}]}]
        created = self._post("/api/v4/leads/complex", [{"name": _title(lead), "_embedded": {"contacts": [contact]}}])
        lead_id = created[0]["id"] if isinstance(created, list) and created else None
        if lead_id:
            self._post(f"/api/v4/leads/{lead_id}/notes", [{"note_type": "common", "params": {"text": card}}])
        return {"sink": "amocrm", "ok": bool(lead_id), "id": lead_id}
