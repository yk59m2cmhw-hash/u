"""Where a finished lead goes: a JSON Lines file, a Telegram staff chat, a webhook (CRM)."""
import json
import os
import pathlib
import time
import urllib.request


class JsonlSink:
    def __init__(self, path):
        self.path = pathlib.Path(path)

    def deliver(self, card, lead, reason):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "reason": reason, "lead": lead}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return {"sink": "jsonl", "ok": True, "path": str(self.path)}


class TelegramSink:
    """Posts the card to a staff chat through the Telegram Bot API."""
    def __init__(self, token, chat_id, opener=None):
        self.url = f"https://api.telegram.org/bot{token}/sendMessage"
        self.chat_id = chat_id
        self._open = opener or urllib.request.urlopen

    def deliver(self, card, lead, reason):
        body = json.dumps({"chat_id": self.chat_id, "text": card}).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        with self._open(req, timeout=15) as resp:
            ok = json.loads(resp.read().decode("utf-8")).get("ok", False)
        return {"sink": "telegram", "ok": bool(ok)}


class WebhookSink:
    """POSTs {reason, lead, card} as JSON - for a CRM's incoming webhook or any automation."""
    def __init__(self, url, opener=None):
        self.url = url
        self._open = opener or urllib.request.urlopen

    def deliver(self, card, lead, reason):
        body = json.dumps({"reason": reason, "lead": lead, "card": card}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        with self._open(req, timeout=15) as resp:
            return {"sink": "webhook", "ok": 200 <= resp.status < 300}


def sinks_from_env(default_file="data/leads.jsonl"):
    """JSONL always; Telegram if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID; webhook if OKNO_WEBHOOK_URL."""
    sinks = [JsonlSink(os.environ.get("OKNO_LEADS_FILE", default_file))]
    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
        sinks.append(TelegramSink(os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]))
    if os.environ.get("OKNO_WEBHOOK_URL"):
        sinks.append(WebhookSink(os.environ["OKNO_WEBHOOK_URL"]))
    return sinks
