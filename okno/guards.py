"""Deterministic checks that sit on top of any model: prices, visit promises, emergencies, intents.

The agent must never quote a price for the work and never confirm a visit. Whatever the model
writes, `sanitize_reply` removes such sentences and adds a safe explanation instead.
"""
import re

_I = re.IGNORECASE

# A number followed by a currency, or "от/до/около N тыс", or "N тысяч".
PRICE_PATTERNS = [
    re.compile(r"\d[\d\s.,]*\s*(?:тг|тенге|₸|kzt|руб|₽|\$|usd|долл|евро|€)", _I),
    re.compile(r"(?:от|до|около|примерно|где-то|порядка|в районе)\s*\d[\d\s.,]*\s*(?:тыс|т\.|к\b|000)", _I),
    re.compile(r"\b\d+\s*(?:тыс(?:яч[аи]?)?|тыщ)\b", _I),
    re.compile(r"(?:стоит|стоимость|цена|обойд[её]тся|будет стоить)[^.!?\n]{0,25}\d", _I),
]

VISIT_PATTERNS = [
    re.compile(r"(?:мастер|сотрудник|специалист|бригада)\w*\s+(?:приедет|подъедет|выедет|будет у вас)", _I),
    re.compile(r"выезд\w*\s+(?:подтвержд|назначен|согласован|запланирован)", _I),
    re.compile(r"(?:записал[аи]?|записываю|забронировал[аи]?)\s+вас\s+на", _I),
    re.compile(r"ждите\s+(?:мастера|специалиста|сотрудника|нас)", _I),
    re.compile(r"(?:приедем|подъедем|будем у вас)\s+(?:сегодня|завтра|послезавтра|в\s|к\s)", _I),
    re.compile(r"подтверждаю\s+(?:выезд|визит|время)", _I),
]

PRICE_SAFE = "Стоимость работ назовёт сотрудник после уточнения деталей."
VISIT_SAFE = "Время выезда подтвердит сотрудник, когда свяжется с вами."

URGENT = {
    "gas": re.compile(r"газ(?!ел|он)|газом|запах газа|газ ағып", _I),
    "fire": re.compile(r"пожар|горит|дым(?!ох)|задымл|өрт", _I),
    "water": re.compile(r"затоп|заливает|залил[аи]? соседей|прорвал|хлещет|потоп|фонтан|су ағып", _I),
    "electric": re.compile(r"искрит|искры|ударил[оа]? током|бь[её]тся током|оплавил|замыкани|қысқа тұйықталу", _I),
}

SAFETY = {
    "gas": "Если чувствуете запах газа: не включайте свет и электроприборы, откройте окна, выйдите из помещения и звоните 112.",
    "fire": "При пожаре или задымлении покиньте помещение и сразу звоните 112.",
    "water": "Если возможно, перекройте воду краном на входе в квартиру и обесточьте мокрые розетки.",
    "electric": "Не трогайте розетку и провода; если возможно, отключите автомат в щитке.",
}

HUMAN_REQUEST = re.compile(r"оператор|менеджер|живой|живого|человек|позовите|соедините|свяжите с|позвоните мне сейчас|адаммен", _I)
COMPLAINT = re.compile(r"жалоб|испортил|сломал[аи]? после|плохо сделал|некачествен|верните деньги|опять течёт|опять течет|недовол", _I)
OFF_SALES = re.compile(r"продаёте|продаете|купить у вас|у вас есть в наличии|магазин", _I)

YES = re.compile(r"^\s*(?:да|да,? ?вс[её] верно|верно|вс[её] верно|вс[её] так|да,? ?вс[её] так|ок|окей|ok|okay|подтверждаю|правильно|иә|ия|дұрыс|ага|угу)\b", _I)
NO = re.compile(r"^\s*(?:нет|не так|неверно|неправильно|жоқ|не совсем)\b", _I)
DECLINE = re.compile(r"^\s*(?:нет,? спасибо|не надо|не нужно|спасибо,? не нужно|пока не нужно|рахмет,? керек емес)\b", _I)

_KAZAKH_LETTERS = set("әғқңөұүһіӘҒҚҢӨҰҮҺІ")
_KAZAKH_WORDS = re.compile(r"\b(?:сәлем|салем|сәлеметсіз|рахмет|керек|ертең|бүгін|кешке|таңертең|ауданы|иә|жоқ|қайда)\b", _I)


def _sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [p for p in parts if p.strip()]


def has_price(text):
    return any(p.search(text or "") for p in PRICE_PATTERNS)


def has_visit_promise(text):
    return any(p.search(text or "") for p in VISIT_PATTERNS)


def sanitize_reply(text):
    """Remove sentences with prices or visit promises. Returns (clean_text, flags)."""
    if not (text or "").strip():
        return "", []
    flags, kept = [], []
    for s in _sentences(text or ""):
        if has_price(s):
            flags.append("price_removed")
            continue
        if has_visit_promise(s):
            flags.append("visit_promise_removed")
            continue
        kept.append(s)
    if "price_removed" in flags and PRICE_SAFE not in kept:
        kept.append(PRICE_SAFE)
    if "visit_promise_removed" in flags and VISIT_SAFE not in kept:
        kept.append(VISIT_SAFE)
    clean = " ".join(kept).strip()
    return (clean or PRICE_SAFE), flags


def detect_urgent(text):
    for kind, pattern in URGENT.items():
        if pattern.search(text or ""):
            return kind
    return None


def detect_language(text, current="ru"):
    t = text or ""
    if any(ch in _KAZAKH_LETTERS for ch in t) or _KAZAKH_WORDS.search(t):
        return "kk"
    return current


def is_yes(text):
    return bool(YES.search(text or ""))


def is_no(text):
    return bool(NO.search(text or ""))


def is_decline(text):
    return bool(DECLINE.search(text or ""))


def wants_human(text):
    return bool(HUMAN_REQUEST.search(text or ""))


def is_complaint(text):
    return bool(COMPLAINT.search(text or ""))


def is_sales_question(text):
    return bool(OFF_SALES.search(text or ""))


OTHER_CITY = re.compile(r"астан|шымкент|караганд|актоб|актау|атырау|павлодар|усть-каменогорск|өскемен|семей|тараз|"
                        r"костана|кызылорд|уральск|петропавловск|талдыкорган|туркестан|кокшетау|экибастуз|нур-султан", _I)
CANCEL = re.compile(r"передумал|уже не нужно|не нужно уже|отмените|отменяю|отмена заявки|ой,? не надо|не надо уже|керек емес", _I)


def mentions_other_city(text, home_city):
    m = OTHER_CITY.search(text or "")
    return bool(m) and (home_city or "").lower()[:5] not in m.group(0).lower()


def is_cancel(text):
    return bool(CANCEL.search(text or ""))
