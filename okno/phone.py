"""Phone number extraction and normalisation (Kazakhstan-first, E.164 output)."""
import re

_CANDIDATE = re.compile(r"(?<![\d+])\+?\d[\d\s\-()]{6,}\d")


def normalize(raw):
    """Return an E.164 string like '+77011234567', or None if the input is not a phone number.

    Accepts '+7 701 123 45 67', '8 (701) 123-45-67', '87011234567', '7011234567'.
    Kazakhstan numbers start with +7 7; other +7 numbers are accepted as well, other countries
    only when written with a leading '+' and 10-15 digits.
    """
    if not raw:
        return None
    raw = str(raw).strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] in "78":
        return "+7" + digits[1:]
    if len(digits) == 10 and digits[0] == "7":
        return "+7" + digits
    if raw.startswith("+") and 10 <= len(digits) <= 15:
        return "+" + digits
    return None


def is_kz(e164):
    return bool(e164) and e164.startswith("+77") and len(e164) == 12


def extract(text):
    """First valid phone number found in free text, normalised; None if there is none."""
    for m in _CANDIDATE.finditer(text or ""):
        p = normalize(m.group(0))
        if p:
            return p
    return None


def looks_like_phone_attempt(text):
    """True when the message is mostly digits but not a valid number (e.g. '123')."""
    digits = re.sub(r"\D", "", text or "")
    return bool(digits) and len(digits) >= 3 and extract(text) is None and len(digits) >= len(text.strip()) * 0.5


def redact(text, placeholder="[телефон]"):
    """Replace every valid phone number in text with a placeholder (before sending text to an external model)."""
    def repl(m):
        return placeholder if normalize(m.group(0)) else m.group(0)
    return _CANDIDATE.sub(repl, text or "")
