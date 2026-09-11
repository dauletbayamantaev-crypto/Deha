import re
from datetime import date
from typing import Optional

_PATTERN = re.compile(r"^\s*(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{4}))?\s*$")

_LEAP_YEAR = 2000  # kabisa yili, 29-fevralni tekshirish uchun


def parse_birthday(text: str) -> Optional[tuple[int, int, Optional[int]]]:
    """"KK-OO" yoki "KK-OO-YYYY" formatini (day, month, year) ga aylantiradi.

    Sana yaroqsiz bo'lsa (masalan 31-04) None qaytaradi.
    """
    match = _PATTERN.match(text)
    if not match:
        return None

    day, month, year_str = match.groups()
    day, month = int(day), int(month)
    year = int(year_str) if year_str else None

    check_year = year if year else _LEAP_YEAR
    try:
        date(check_year, month, day)
    except ValueError:
        return None

    if year and not (1900 <= year <= date.today().year):
        return None

    return day, month, year
