import re
from datetime import datetime, timedelta
from typing import Optional

_DEADLINE_DATE = re.compile(
    r"^\s*(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2,4}))?[\s,]+(\d{1,2})[:.](\d{2})\s*$"
)
_DEADLINE_TIME = re.compile(
    r"^\s*(bugun|ertaga|indinga)?\s*(\d{1,2})[:.](\d{2})\s*$", re.IGNORECASE
)
_DAY_WORDS = {"bugun": 0, "ertaga": 1, "indinga": 2}


def parse_deadline(text: str, now: datetime) -> Optional[datetime]:
    """Deadline matnini datetime ga aylantiradi.

    Qabul qilinadigan ko'rinishlar: "18-09 15:00", "18-09-2026 15:00",
    "ertaga 12:30", "bugun 18:00", "18:00".

    `now` — mahalliy vaqt (naive), natija ham naive mahalliy vaqt bo'ladi.
    Format tanilmasa None qaytaradi.
    """
    text = text.strip()

    match = _DEADLINE_DATE.match(text)
    if match:
        day, month, year_str, hour, minute = match.groups()
        year = int(year_str) if year_str else now.year
        if year < 100:
            year += 2000
        try:
            result = datetime(year, int(month), int(day), int(hour), int(minute))
        except ValueError:
            return None
        # Yil ko'rsatilmagan va sana ancha o'tib ketgan bo'lsa — keyingi yil nazarda tutilgan
        if year_str is None and result < now - timedelta(days=7):
            try:
                result = result.replace(year=year + 1)
            except ValueError:
                return None
        return result

    match = _DEADLINE_TIME.match(text)
    if match:
        word, hour, minute = match.groups()
        try:
            base = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
        except ValueError:
            return None
        return base + timedelta(days=_DAY_WORDS.get((word or "bugun").lower(), 0))

    return None
