"""TZ maydonlari, shablon parseri va tekshiruvlar (Telegram'dan mustaqil)."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from app.dateparse import parse_deadline


# ---- ish turlari ----

@dataclass(frozen=True)
class Kind:
    key: str
    label: str  # tugmada va "Tasnif" da ko'rinadi
    tag: str    # hashtag


KINDS: tuple[Kind, ...] = (
    Kind("karusel", "Karusel post", "karusel"),
    Kind("post", "Feed post", "post"),
    Kind("story", "Story", "story"),
    Kind("reels", "Reels / video", "reels"),
    Kind("banner", "Banner / print", "banner"),
    Kind("boshqa", "Boshqa", "dizayn"),
)

KIND_BY_KEY: dict[str, Kind] = {k.key: k for k in KINDS}

_KIND_KEYWORDS: dict[str, tuple[str, ...]] = {
    "karusel": ("karusel", "carousel", "slayd", "slide"),
    "reels": ("reels", "rils", "video", "montaj", "animatsiya"),
    "story": ("story", "stori"),
    "banner": ("banner", "print", "bosma", "billboard", "vizitka", "buklet"),
    "post": ("post", "feed", "publikatsiya", "maket"),
}


def parse_kind(text: str) -> Kind:
    """Matndan ish turini topadi, topilmasa «Boshqa» qaytaradi."""
    folded = _fold(text)
    for key, words in _KIND_KEYWORDS.items():
        if any(word in folded for word in words):
            return KIND_BY_KEY[key]
    return KIND_BY_KEY["boshqa"]


def build_tasnif(client: str, kind_label: str) -> str:
    return f"{client} uchun {kind_label.lower()}"


# ---- maydonlar ----

@dataclass(frozen=True)
class Field:
    key: str
    label: str
    aliases: tuple[str, ...]
    question: str
    example: str
    required: bool = True


FIELDS: tuple[Field, ...] = (
    Field(
        "client", "Mijoz",
        ("mijoz", "brend", "brand", "klient", "kompaniya"),
        "🏷 <b>Mijoz</b> kim?",
        "Xazna",
    ),
    Field(
        "tasnif", "Tasnif",
        ("tasnif", "tur", "turi", "ish turi", "vazifa"),
        "🗂 <b>Tasnif</b> — qanday ish?",
        "Xazna uchun karusel post",
    ),
    Field(
        "subject", "Mavzu",
        ("mavzu", "tema", "sarlavha", "tematika"),
        "📌 <b>Mavzu</b> nima haqida?",
        "Xalqaro o'tkazmalar qo'llanmasi",
    ),
    Field(
        "deadline", "Deadline",
        ("deadline", "dedline", "dedlayn", "muddat", "qachon", "srok"),
        "⏰ <b>Deadline</b> qachon?",
        "20.09.2026 18:00",
    ),
    Field(
        "designers", "Dizayner",
        ("dizayner", "dizaynerlar", "masul", "mas'ul", "ijrochi"),
        "👤 <b>Dizayner</b> kim? @username ko'rinishida yozing.\n"
        "Bir nechta bo'lsa bo'sh joy bilan: @ali @vali",
        "@nickname",
    ),
    Field(
        "body", "Matn",
        ("matn", "tz", "kontent", "text", "tekst", "sahifalar", "kopirayt"),
        "✍️ <b>TZ matnini</b> bitta xabarda yuboring.\n"
        "Masalan:\n<code>1. Page\nLorem ipsum\n\n2. Page\nLorem ipsum</code>",
        "1. Page ...",
    ),
    Field(
        "note", "Izoh",
        ("izoh", "qoshimcha", "qo'shimcha", "note", "eslatma"),
        "💬 <b>Izoh</b> bormi? Bo'lmasa «yo'q» deb yozing.",
        "Logotip oq rangda bo'lsin",
        required=False,
    ),
)

FIELD_BY_KEY: dict[str, Field] = {f.key: f for f in FIELDS}

TEMPLATE = (
    "Mijoz: \n"
    "Tasnif: \n"
    "Mavzu: \n"
    "Deadline: 20.09.2026 18:00\n"
    "Dizayner: @nickname\n"
    "Matn:\n"
    "1. Page\n"
    "\n"
    "2. Page\n"
    "\n"
    "Izoh: "
)


# ---- matn yordamchilari ----

_APOSTROPHES = ("ʻ", "ʼ", "‘", "’", "`", "´")

_EMPTY_VALUES = {
    "", "-", "--", "—", ".", "?", "??", "yoq", "yuq", "net", "no",
    "bilmadim", "keyin", "keyinroq", "aniq emas", "malum emas", "ozingiz bilasiz",
    "har doimgidek", "odatdagidek", "tez", "tezroq", "hozir", "imkon qadar tez",
}

_USERNAME = re.compile(r"@?([A-Za-z][A-Za-z0-9_]{3,31})")


def _fold(text: str) -> str:
    lowered = text.strip().lower()
    for char in _APOSTROPHES:
        lowered = lowered.replace(char, "'")
    return lowered


def _key_form(text: str) -> str:
    return _fold(text).replace("'", "").rstrip(":").strip()


def is_empty(value: str) -> bool:
    return _key_form(value) in _EMPTY_VALUES


def slug(text: str) -> str:
    """«Xazna» -> «xazna», «Coca Cola» -> «coca_cola» (hashtag uchun)."""
    letters: list[str] = []
    for char in _fold(text).replace("'", ""):
        if char.isalnum():
            letters.append(char)
        elif letters and letters[-1] != "_":
            letters.append("_")
    return "".join(letters).strip("_") or "mijoz"


def parse_usernames(text: str) -> list[str]:
    """«@ali, @vali» -> ['ali', 'vali'] (takrorlanmaydi, tartib saqlanadi)."""
    found: list[str] = []
    for match in _USERNAME.finditer(text):
        name = match.group(1).lower()
        if name not in found:
            found.append(name)
    return found


# ---- shablonni o'qish ----

_ALIAS_TO_KEY: dict[str, str] = {}
for _field in FIELDS:
    for _alias in _field.aliases:
        _ALIAS_TO_KEY[_key_form(_alias)] = _field.key

_LINE = re.compile(r"^\s*([^:\n]{2,30}?)\s*:\s*(.*)$")


def parse_template(text: str) -> dict[str, str]:
    """Tanilgan kalit yangi maydonni boshlaydi, qolgan qatorlar davomi bo'ladi.

    Shu sabab «Matn» bir nechta qator va bo'sh qatorlardan iborat bo'la oladi.
    """
    collected: dict[str, list[str]] = {}
    current: Optional[str] = None

    for line in text.splitlines():
        match = _LINE.match(line)
        key = _ALIAS_TO_KEY.get(_key_form(match.group(1))) if match else None
        if key:
            current = key
            collected.setdefault(key, []).append(match.group(2).strip())
        elif current:
            collected[current].append(line.rstrip())

    return {key: "\n".join(parts).strip() for key, parts in collected.items()}


def looks_like_template(text: str) -> bool:
    return bool(parse_template(text))


# ---- tekshirish ----

@dataclass
class ParsedTZ:
    client: str
    kind: Kind
    tasnif: str
    subject: str
    deadline: datetime
    designers: list[str]
    body: str
    note: str

    @property
    def lead_hours(self) -> float:
        return 0.0


MIN_LEAD_MINUTES = 15


def validate(values: dict[str, str], now: datetime) -> tuple[Optional[ParsedTZ], list[str]]:
    errors: list[str] = []
    clean = {f.key: values.get(f.key, "").strip() for f in FIELDS}

    for f in FIELDS:
        if f.required and (not clean[f.key] or is_empty(clean[f.key])):
            errors.append(f"{f.label} — to'ldirilmagan. Masalan: {f.example}")

    designers = parse_usernames(clean["designers"])
    if clean["designers"] and not designers:
        errors.append(
            f"Dizayner @username ko'rinishida yozilishi kerak: «{clean['designers']}» "
            "tushunarsiz. Masalan: @nickname"
        )

    deadline: Optional[datetime] = None
    if clean["deadline"] and not is_empty(clean["deadline"]):
        deadline = parse_deadline(clean["deadline"], now)
        if deadline is None:
            errors.append(
                f"Deadline formati tushunarsiz: «{clean['deadline']}». "
                "To'g'ri ko'rinish: 20.09.2026 18:00, ertaga 15:00, bugun 18:00"
            )
        elif deadline < now + timedelta(minutes=MIN_LEAD_MINUTES):
            errors.append(
                f"Deadline o'tib ketgan yoki juda yaqin: {deadline:%d.%m.%Y %H:%M}. "
                "Kamida 15 daqiqa keyingi vaqtni ko'rsating."
            )

    if errors:
        return None, errors

    assert deadline is not None
    kind = parse_kind(clean["tasnif"])
    note = "" if is_empty(clean["note"]) else clean["note"]
    return (
        ParsedTZ(
            client=clean["client"],
            kind=kind,
            tasnif=clean["tasnif"],
            subject=clean["subject"],
            deadline=deadline,
            designers=designers,
            body=clean["body"],
            note=note,
        ),
        [],
    )


def format_hours(hours: float) -> str:
    """4.5 -> «4 soat 30 daqiqa», 30 -> «1 kun 6 soat»."""
    total_minutes = max(0, int(round(hours * 60)))
    days, rest = divmod(total_minutes, 24 * 60)
    hrs, minutes = divmod(rest, 60)
    parts = []
    if days:
        parts.append(f"{days} kun")
    if hrs:
        parts.append(f"{hrs} soat")
    if minutes and not days:
        parts.append(f"{minutes} daqiqa")
    return " ".join(parts) or "0 daqiqa"
