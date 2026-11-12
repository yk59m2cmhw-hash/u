"""Keeps one Conversation per (channel, customer) and turns inbound messages into replies."""
import threading
import time

from ..agent import Conversation
from ..providers import make_provider

NON_TEXT_REPLY = "Пока я понимаю только текст. Опишите, пожалуйста, задачу словами."
SESSION_TTL = 24 * 3600


class Router:
    def __init__(self, kb, provider_name="auto", model=None, sinks=None, clock=time.time):
        self.kb, self.provider_name, self.model = kb, provider_name, model
        self.sinks = sinks or []
        self.sessions, self.lock, self.clock = {}, threading.Lock(), clock

    def _conversation(self, channel, user, known_phone=None):
        key = (channel, user)
        now = self.clock()
        with self.lock:
            item = self.sessions.get(key)
            stale = item and (now - item[1] > SESSION_TTL or item[0].status in ("handed_off", "closed"))
            if item is None or stale:
                conv = Conversation(self.kb, make_provider(self.provider_name, self.kb, self.model),
                                    channel=channel, known_phone=known_phone, sinks=self.sinks)
                item = [conv, now]
                self.sessions[key] = item
            item[1] = now
            return item[0]

    def handle(self, channel, message):
        """message: {'user', 'text', optional 'phone', 'name', 'unsupported'}. Returns the reply text."""
        conv = self._conversation(channel, message["user"], message.get("phone"))
        if message.get("unsupported") and not message.get("text"):
            return NON_TEXT_REPLY
        return conv.handle(message.get("text", ""))["reply"]
