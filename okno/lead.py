"""The lead (request) the agent collects and hands over to staff."""
from dataclasses import asdict, dataclass, field

from . import kb as kbmod
from . import phone as phonemod

REQUIRED = ("task", "district", "time_window", "phone")
ASK_ORDER = ("task", "district", "time_window", "name", "phone")
LABELS = {
    "service": "Услуга",
    "task": "Задача",
    "district": "Район",
    "address_hint": "Ориентир",
    "time_window": "Удобное время",
    "name": "Имя",
    "phone": "Телефон",
}
MAX_LEN = 500


@dataclass
class Lead:
    service: str = ""
    task: str = ""
    district: str = ""
    address_hint: str = ""
    time_window: str = ""
    name: str = ""
    phone: str = ""
    urgent: str = ""          # "", or gas / fire / water / electric
    language: str = "ru"
    channel: str = "web"
    notes: list = field(default_factory=list)

    def missing(self):
        return [f for f in REQUIRED if not getattr(self, f)]

    def is_complete(self):
        return not self.missing()

    def merge(self, updates, kb):
        """Apply model or rule updates with validation. Returns a list of rejected fields."""
        rejected = []
        for key, value in (updates or {}).items():
            if key not in LABELS or value is None:
                continue
            value = str(value).strip()[:MAX_LEN]
            if not value:
                continue
            if key == "phone":
                norm = phonemod.normalize(value) or phonemod.extract(value)
                if not norm:
                    rejected.append("phone")
                    continue
                value = norm
            if key == "district":
                value = kbmod.match_district(value, kb) or value
                note = kbmod.district_note(value, kb)
                if note and note not in self.notes:
                    self.notes.append(f"{value}: {note}")
            setattr(self, key, value)
        return rejected

    def to_dict(self):
        return asdict(self)

    def card(self, company, reason="lead_ready"):
        """Plain-text card for staff (Telegram, console)."""
        title = {"lead_ready": "Новая заявка", "urgent": "СРОЧНО: авария", "human_request": "Клиент просит сотрудника",
                 "complaint": "Жалоба клиента", "out_of_scope": "Вопрос вне базы знаний",
                 "too_long": "Диалог затянулся", "model_refusal": "Нужен сотрудник"}.get(reason, "Заявка")
        lines = [f"{title} — {company}"]
        if self.urgent:
            lines.append(f"Тип аварии: {self.urgent}")
        for key in ("service", "task", "district", "address_hint", "time_window", "name", "phone"):
            val = getattr(self, key)
            if val:
                lines.append(f"{LABELS[key]}: {val}")
        for n in self.notes:
            lines.append(f"Примечание: {n}")
        lines.append(f"Канал: {self.channel}; язык клиента: {self.language}")
        lines.append("Цену и время выезда агент НЕ называл — их подтверждает сотрудник.")
        return "\n".join(lines)
