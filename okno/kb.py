"""Company knowledge base: loading, matching and rendering for prompts."""
import json
import pathlib

DEFAULT_KB = pathlib.Path(__file__).resolve().parent / "data" / "demo_company.json"


def load(path=None):
    with open(path or DEFAULT_KB, encoding="utf-8") as f:
        kb = json.load(f)
    for key in ("company", "services", "districts", "faq", "hours"):
        if key not in kb:
            raise ValueError(f"knowledge base is missing '{key}'")
    return kb


def match_district(text, kb):
    """Canonical district name if the text mentions one (or a known alias), else None."""
    low = (text or "").lower()
    for d in kb["districts"]:
        if d["name"].lower() in low or any(a in low for a in d.get("aliases", [])):
            return d["name"]
    return None


def district_note(name, kb):
    for d in kb["districts"]:
        if d["name"] == name:
            return d.get("note", "")
    return ""


def match_service(text, kb):
    low = (text or "").lower()
    best, best_len = None, 0
    for s in kb["services"]:
        for k in s["keywords"]:
            if k in low and len(k) > best_len:
                best, best_len = s["name"], len(k)
    return best


def faq_answers(text, kb):
    """Answers whose keywords occur in the text, in knowledge-base order (topic, answer)."""
    low = (text or "").lower()
    return [(f["topic"], f["answer"]) for f in kb["faq"] if any(k in low for k in f["keywords"])]


def render(kb):
    """Plain-text knowledge base for the model prompt."""
    lines = [f"Компания: {kb['company']} ({kb.get('city', '')}). {kb.get('about', '')}",
             f"Часы работы: {kb['hours']}", "Услуги:"]
    lines += [f"- {s['name']}: {s['examples']}" for s in kb["services"]]
    lines.append("Районы выезда:")
    lines += [f"- {d['name']}" + (f" ({d['note']})" if d.get("note") else "") for d in kb["districts"]]
    lines.append("Ответы на частые вопросы:")
    lines += [f"- [{f['topic']}] {f['answer']}" for f in kb["faq"]]
    if kb.get("emergency_note"):
        lines.append(f"Безопасность: {kb['emergency_note']}")
    if kb.get("callback_promise"):
        lines.append(f"Что обещать после передачи заявки: {kb['callback_promise']}")
    return "\n".join(lines)
