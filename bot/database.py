import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Birthday:
    chat_id: int
    user_id: int
    full_name: str
    username: Optional[str]
    day: int
    month: int
    year: Optional[int]


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS birthdays (
            chat_id   INTEGER NOT NULL,
            user_id   INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            username  TEXT,
            day       INTEGER NOT NULL,
            month     INTEGER NOT NULL,
            year      INTEGER,
            PRIMARY KEY (chat_id, user_id)
        )
        """
    )
    conn.commit()
    return conn


def upsert_birthday(
    conn: sqlite3.Connection,
    chat_id: int,
    user_id: int,
    full_name: str,
    username: Optional[str],
    day: int,
    month: int,
    year: Optional[int],
) -> None:
    conn.execute(
        """
        INSERT INTO birthdays (chat_id, user_id, full_name, username, day, month, year)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(chat_id, user_id) DO UPDATE SET
            full_name = excluded.full_name,
            username  = excluded.username,
            day       = excluded.day,
            month     = excluded.month,
            year      = excluded.year
        """,
        (chat_id, user_id, full_name, username, day, month, year),
    )
    conn.commit()


def delete_birthday(conn: sqlite3.Connection, chat_id: int, user_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM birthdays WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id),
    )
    conn.commit()
    return cur.rowcount > 0


def get_birthday(conn: sqlite3.Connection, chat_id: int, user_id: int) -> Optional[Birthday]:
    row = conn.execute(
        "SELECT chat_id, user_id, full_name, username, day, month, year "
        "FROM birthdays WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id),
    ).fetchone()
    return Birthday(*row) if row else None


def list_birthdays_for_chat(conn: sqlite3.Connection, chat_id: int) -> list[Birthday]:
    rows = conn.execute(
        "SELECT chat_id, user_id, full_name, username, day, month, year "
        "FROM birthdays WHERE chat_id = ?",
        (chat_id,),
    ).fetchall()
    return [Birthday(*row) for row in rows]


def list_birthdays_on(conn: sqlite3.Connection, month: int, day: int) -> list[Birthday]:
    rows = conn.execute(
        "SELECT chat_id, user_id, full_name, username, day, month, year "
        "FROM birthdays WHERE month = ? AND day = ?",
        (month, day),
    ).fetchall()
    return [Birthday(*row) for row in rows]


def _safe_date(year: int, month: int, day: int) -> date:
    # 29-fevral tug'ilganlar uchun kabisa bo'lmagan yilda 28-fevralga tushiriladi
    if month == 2 and day == 29:
        try:
            return date(year, 2, 29)
        except ValueError:
            return date(year, 2, 28)
    return date(year, month, day)


def days_until_next(b: Birthday, today: date) -> int:
    next_occurrence = _safe_date(today.year, b.month, b.day)
    if next_occurrence < today:
        next_occurrence = _safe_date(today.year + 1, b.month, b.day)
    return (next_occurrence - today).days
