"""Telegram bot for customers (Bot API). Free to use, no per-message fees.

Environment:
  TELEGRAM_CUSTOMER_BOT_TOKEN  bot that talks to customers (falls back to TELEGRAM_BOT_TOKEN)
  TELEGRAM_WEBHOOK_SECRET      secret_token passed to setWebhook; checked on every update
"""
import hmac
import json
import os
import urllib.request


def verify_secret(expected, header):
    return bool(expected) and bool(header) and hmac.compare_digest(expected, header)


def parse_update(update):
    """{'user': chat_id, 'text': ..., 'name': ...} for a private text message, else None."""
    msg = update.get("message") or update.get("edited_message")
    if not msg or msg.get("chat", {}).get("type") != "private":
        return None
    return {"user": str(msg["chat"]["id"]), "text": msg.get("text", ""),
            "name": msg.get("from", {}).get("first_name", ""), "unsupported": None if "text" in msg else "non-text"}


class TelegramClient:
    def __init__(self, token=None, opener=None):
        self.token = token or os.environ.get("TELEGRAM_CUSTOMER_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._open = opener or urllib.request.urlopen

    def _call(self, method, body):
        req = urllib.request.Request(f"https://api.telegram.org/bot{self.token}/{method}",
                                     data=json.dumps(body).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json"})
        with self._open(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def send_text(self, chat_id, text):
        return self._call("sendMessage", {"chat_id": chat_id, "text": text[:4096]})

    def set_webhook(self, url, secret):
        return self._call("setWebhook", {"url": url, "secret_token": secret, "allowed_updates": ["message"]})
