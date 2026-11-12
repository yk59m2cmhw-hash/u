"""WhatsApp Business Platform through Meta's Cloud API (official). Unofficial WhatsApp APIs are not used:
they break WhatsApp's terms and get numbers banned (decision D-020).

Environment:
  WHATSAPP_TOKEN            access token of the app / system user
  WHATSAPP_PHONE_NUMBER_ID  business phone number id
  WHATSAPP_APP_SECRET       app secret, to verify webhook signatures
  WHATSAPP_VERIFY_TOKEN     any string you also enter in the Meta dashboard
  WHATSAPP_GRAPH_VERSION    Graph API version (default below; check Meta's changelog)
"""
import hashlib
import hmac
import json
import os
import urllib.request

DEFAULT_GRAPH_VERSION = "v23.0"


def verify_subscription(params, verify_token):
    """GET handshake: return the challenge to echo back, or None to refuse."""
    if params.get("hub.mode") == "subscribe" and verify_token and params.get("hub.verify_token") == verify_token:
        return params.get("hub.challenge", "")
    return None


def verify_signature(app_secret, raw_body, header):
    """X-Hub-Signature-256: 'sha256=<hex HMAC-SHA256 of the raw body with the app secret>'."""
    if not app_secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256="):])


def parse_inbound(payload):
    """Text messages from a webhook payload: [{'user': wa_id, 'phone': '+7...', 'text': ..., 'name': ...}]."""
    out = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            names = {c.get("wa_id"): c.get("profile", {}).get("name", "") for c in value.get("contacts", [])}
            for msg in value.get("messages", []):
                if msg.get("type") != "text":
                    out.append({"user": msg.get("from"), "phone": "+" + str(msg.get("from", "")), "text": "",
                                "name": names.get(msg.get("from"), ""), "unsupported": msg.get("type")})
                    continue
                out.append({"user": msg.get("from"), "phone": "+" + str(msg.get("from", "")),
                            "text": msg.get("text", {}).get("body", ""), "name": names.get(msg.get("from"), "")})
    return out


class WhatsAppClient:
    def __init__(self, token=None, phone_number_id=None, version=None, opener=None):
        self.token = token or os.environ.get("WHATSAPP_TOKEN", "")
        self.phone_number_id = phone_number_id or os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
        self.version = version or os.environ.get("WHATSAPP_GRAPH_VERSION", DEFAULT_GRAPH_VERSION)
        self._open = opener or urllib.request.urlopen

    def send_text(self, to, text):
        url = f"https://graph.facebook.com/{self.version}/{self.phone_number_id}/messages"
        body = {"messaging_product": "whatsapp", "to": str(to).lstrip("+"), "type": "text",
                "text": {"body": text[:4096]}}
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {self.token}"})
        with self._open(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
