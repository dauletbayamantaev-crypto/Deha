"""TZ (texnik topshiriq) shabloni: maydonlar, parser va tekshiruvlar.

Bu modul Telegram'dan mustaqil — faqat matnni o'qiydi, tekshiradi va
xatoliklar ro'yxatini qaytaradi. Shu sabab uni alohida sinash oson.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from app.dateparse import parse_deadline


# ---- ish turlari va ular uchun minimal muddat ----

@dataclass(frozen=True)
class WorkType:
    key: str
    label: str
    min_hours: int  # shu turdagi ish uchun eng kam yo'l qo'yiladigan muddat


WORK_TYPES: tuple[WorkType, ...] = (
    WorkType("post", "📱 Post / story maketi", 3),
    WorkType("karusel", "🎠 Karusel (2+ slayd)", 6),
    WorkType("video", "🎬 Reels / video montaj", 24),
    WorkType("print", "🖨 Banner / print maketi", 24),
    WorkType("brending", "🎨 Logo / brending", 72),
    WorkType("boshqa", "✍️ Boshqa", 4),
)

WORK_TYPE_BY_KEY: dict[str, WorkType] = {w.key: w for w in WORK_TYPES}

_WORK_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "karusel": ("karusel", "carousel", "slayd", "slide"),
    "video": ("video", "reels", "rils", "montaj", "animatsiya", "anim"),
    "print": ("print", "banner", "bosma", "billboard", "vizitka", "buklet", "roll"),
    "brending": ("logo", "brend", "brand", "firma uslubi", "identity", "guideline"),
    "post": ("post", "story", "stori", "feed", "maket", "publikatsiya"),
    "boshqa": ("boshqa", "other", "turli"),
}


# ---- prioritet ----

PRIORITY_URGENT = "urgent"
PRIORITY_NORMAL = "normal"
PRIORITY_PLANNED = "planned"

PRIORITY_LABEL = {
    PRIORITY_URGENT: "🔥 Shoshilinch",
    PRIORITY_NORMAL: "🟡 Oddiy",
    PRIORITY_PLANNED: "🟢 Rejali",
}


def priority_for(work_type: WorkType, lead_hours: float) -> str:
    """Prioritetni TZ beruvchi emas, berilgan muddat belgilaydi."""
    if lead_hours < work_type.min_hours:
        return PRIORITY_URGENT
    if lead_hours < 24:
        return PRIORITY_NORMAL
    return PRIORITY_PLANNED


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
        "brand", "Brend",
        ("brend", "brand", "mijoz", "klient", "kompaniya"),
        "🏷 Qaysi brend / mijoz uchun?",
        "Nestle",
    ),
    Field(
        "work_type", "Ish turi",
        ("ish turi", "ish", "turi", "tur", "vazifa", "task"),
        "🗂 Ish turi qanday?",
        "post",
    ),
    Field(
        "fmt", "Format",
        ("format", "o'lcham", "olcham", "razmer", "size", "hajmi"),
        "📐 Format / o'lcham qanday?",
        "1080x1350",
    ),
    Field(
        "copy_text", "Matn",
        ("matn", "text", "tekst", "kontent", "copy", "kopirayt"),
        "✍️ Maketdagi matn: sarlavha, tavsif, CTA — to'liq yozing.\n"
        "Matn kerak bo'lmasa «matnsiz» deb yozing.",
        "Sarlavha: Kuzgi chegirma -30% | CTA: Buyurtma bering",
    ),
    Field(
        "materials", "Materiallar",
        ("materiallar", "material", "fayllar", "fayl", "surat", "rasm", "foto", "logotip"),
        "📎 Materiallar qayerda? Havola bering yoki qayerdan olishni aniq yozing.",
        "https://drive.google.com/... (logotip + 4 ta foto)",
    ),
    Field(
        "reference", "Referens",
        ("referens", "reference", "namuna", "misol", "ref"),
        "🔗 Referens bormi? Bo'lmasa «yo'q» deb yozing.",
        "https://pin.it/... yoki yo'q",
        required=False,
    ),
    Field(
        "deadline", "Deadline",
        ("deadline", "dedlayn", "dedline", "muddat", "qachon", "srok"),
        "⏰ Deadline qachon? Masalan: «ertaga 15:00» yoki «18-09 12:00»",
        "ertaga 15:00",
    ),
    Field(
        "reason", "Sabab",
        ("sabab", "nega", "prichina"),
        "🔥 Bu muddat standartdan qisqa — nega shoshilinch ekanini yozing.",
        "Mijoz aksiyani bugun kechqurun e'lon qilmoqchi",
        required=False,
    ),
    Field(
        "note", "Izoh",
        ("izoh", "qoshimcha", "qo'shimcha", "note", "eslatma"),
        "💬 Qo'shimcha izoh (ixtiyoriy).",
        "Logotip oq rangda bo'lsin",
        required=False,
    ),
)

FIELD_BY_KEY: dict[str, Field] = {f.key: f for f in FIELDS}

# Savol-javob tartibida so'raladigan maydonlar
# ("reason" faqat shoshilinch bo'lsa so'raladi, "note" faqat shablonda bor)
GUIDED_STEPS: tuple[str, ...] = (
    "brand", "work_type", "fmt", "copy_text", "materials", "reference", "deadline",
)

TEMPLATE = (
    "Brend: \n"
    "Ish turi: post / karusel / video / print / brending\n"
    "Format: 1080x1350\n"
    "Matn: \n"
    "Materiallar: \n"
    "Referens: \n"
    "Deadline: kun-oy soat:daqiqa\n"
    "Izoh: "
)


# ---- matnni tozalash yordamchilari ----

_APOSTROPHES = ("ʻ", "ʼ", "‘", "’", "`", "´")

_EMPTY_VALUES = {
    "", "-", "--", "—", ".", "?", "??", "yoq", "yuq", "net", "no",
    "bilmadim", "keyin", "keyinroq", "aniq emas", "malum emas", "ozingiz bilasiz",
    "har doimgidek", "odatdagidek", "tez", "tezroq", "hozir", "bugun", "imkon qadar tez",
}


def _fold(text: str) -> str:
    lowered = text.strip().lower()
    for char in _APOSTROPHES:
        lowered = lowered.replace(char, "'")
    return lowered


def _key_form(text: str) -> str:
    return _fold(text).replace("'", "").rstrip(":").strip()


def is_empty(value: str) -> bool:
    """«yo'q», «keyin», «tezroq» kabi javoblar to'ldirilgan hisoblanmaydi."""
    return _key_form(value) in _EMPTY_VALUES


def parse_work_type(text: str) -> Optional[WorkType]:
    folded = _key_form(text)
    if folded in WORK_TYPE_BY_KEY:
        return WORK_TYPE_BY_KEY[folded]
    for key, words in _WORK_TYPE_KEYWORDS.items():
        if any(word in folded for word in words):
            return WORK_TYPE_BY_KEY[key]
    return None


# ---- shablonni o'qish ----

_ALIAS_TO_KEY: dict[str, str] = {}
for _field in FIELDS:
    for _alias in _field.aliases:
        _ALIAS_TO_KEY[_key_form(_alias)] = _field.key

_LINE = re.compile(r"^\s*([^:\n]{2,30}?)\s*:\s*(.*)$")


def parse_template(text: str) -> dict[str, str]:
    """Shablon ko'rinishidagi matndan maydonlarni ajratadi.

    Tanilgan kalit («Brend:», «Deadline: ...») yangi maydonni boshlaydi, qolgan
    qatorlar oldingi maydonning davomi bo'ladi — shu sabab «Matn» bir nechta
    qatordan iborat bo'lishi mumkin.
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
            collected[current].append(line.strip())

    return {key: "\n".join(parts).strip() for key, parts in collected.items()}


def looks_like_template(text: str) -> bool:
    """Matnda kamida bitta tanilgan maydon bormi?"""
    return bool(parse_template(text))


# ---- tekshirish ----

@dataclass
class ParsedTZ:
    brand: str
    work_type: WorkType
    fmt: str
    copy_text: str
    materials: str
    reference: str
    deadline: datetime
    reason: str
    note: str
    priority: str
    lead_hours: float


MIN_LEAD_MINUTES = 15


def validate(values: dict[str, str], now: datetime) -> tuple[Optional[ParsedTZ], list[str]]:
    """Maydonlarni tekshiradi. Xatolik bo'lsa (None, xabarlar) qaytaradi."""
    errors: list[str] = []
    clean = {f.key: values.get(f.key, "").strip() for f in FIELDS}

    for f in FIELDS:
        if f.required and (not clean[f.key] or is_empty(clean[f.key])):
            errors.append(f"{f.label} — to'ldirilmagan. Masalan: {f.example}")

    work_type = parse_work_type(clean["work_type"]) if clean["work_type"] else None
    if clean["work_type"] and work_type is None:
        allowed = ", ".join(w.key for w in WORK_TYPES)
        errors.append(f"Ish turi tushunarsiz: «{clean['work_type']}». Mumkin: {allowed}")

    deadline: Optional[datetime] = None
    if clean["deadline"] and not is_empty(clean["deadline"]):
        deadline = parse_deadline(clean["deadline"], now)
        if deadline is None:
            errors.append(
                f"Deadline formati tushunarsiz: «{clean['deadline']}». "
                "To'g'ri ko'rinish: 18-09 15:00, ertaga 12:30, bugun 18:00"
            )
        elif deadline < now + timedelta(minutes=MIN_LEAD_MINUTES):
            errors.append(
                f"Deadline o'tib ketgan yoki juda yaqin: {deadline:%d.%m %H:%M}. "
                "Kamida 15 daqiqa keyingi vaqtni ko'rsating."
            )

    lead_hours = 0.0
    priority = PRIORITY_NORMAL
    if work_type and deadline and deadline > now:
        lead_hours = (deadline - now).total_seconds() / 3600
        priority = priority_for(work_type, lead_hours)
        if priority == PRIORITY_URGENT and is_empty(clean["reason"]):
            suggested = now + timedelta(hours=work_type.min_hours)
            errors.append(
                f"{work_type.label} uchun standart muddat — kamida {work_type.min_hours} soat, "
                f"siz {format_hours(lead_hours)} berdingiz.\n"
                f"Yo deadline'ni {suggested:%d.%m %H:%M} dan keyinga qo'ying, "
                "yo «Sabab:» qatorida nega shoshilinch ekanini yozing."
            )

    if errors:
        return None, errors

    assert work_type is not None and deadline is not None
    return (
        ParsedTZ(
            brand=clean["brand"],
            work_type=work_type,
            fmt=clean["fmt"],
            copy_text=clean["copy_text"],
            materials=clean["materials"],
            reference=clean["reference"] or "yo'q",
            deadline=deadline,
            reason=clean["reason"],
            note=clean["note"],
            priority=priority,
            lead_hours=lead_hours,
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
