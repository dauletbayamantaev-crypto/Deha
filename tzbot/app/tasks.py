"""TZ navbatining ma'lumotlar bazasi qatlami."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

STATUS_NEW = "new"
STATUS_IN_PROGRESS = "in_progress"
STATUS_DONE = "done"
STATUS_CANCELLED = "cancelled"

OPEN_STATUSES = (STATUS_NEW, STATUS_IN_PROGRESS)

STATUS_LABEL = {
    STATUS_NEW: "🆕 Navbatda",
    STATUS_IN_PROGRESS: "▶️ Ishda",
    STATUS_DONE: "✅ Tayyor",
    STATUS_CANCELLED: "🚫 Bekor qilingan",
}

# Eslatma bayroqlari (bitmask) — bir xil eslatma ikki marta yuborilmasligi uchun
REMINDED_SOON = 1
REMINDED_OVERDUE = 2

TS = "%Y-%m-%d %H:%M"


def to_ts(moment: datetime) -> str:
    return moment.strftime(TS)


def from_ts(text: str) -> datetime:
    return datetime.strptime(text, TS)


@dataclass
class Task:
    id: int
    chat_id: int
    number: int
    author_id: int
    author_name: str
    author_username: Optional[str]
    brand: str
    work_type: str
    fmt: str
    copy_text: str
    materials: str
    reference: str
    note: str
    deadline: str
    priority: str
    reason: str
    status: str
    created_at: str
    taken_at: Optional[str]
    done_at: Optional[str]
    assignee_id: Optional[int]
    assignee_name: Optional[str]
    reminded: int

    @property
    def deadline_dt(self) -> datetime:
        return from_ts(self.deadline)

    @property
    def created_dt(self) -> datetime:
        return from_ts(self.created_at)

    @property
    def done_dt(self) -> Optional[datetime]:
        return from_ts(self.done_at) if self.done_at else None

    @property
    def is_late(self) -> bool:
        done = self.done_dt
        return done is not None and done > self.deadline_dt

    @property
    def lead_hours(self) -> float:
        """TZ berilgan paytdan deadline'gacha necha soat bo'lgan."""
        return (self.deadline_dt - self.created_dt).total_seconds() / 3600


_COLUMNS = (
    "id, chat_id, number, author_id, author_name, author_username, brand, work_type, fmt, "
    "copy_text, materials, reference, note, deadline, priority, reason, status, created_at, "
    "taken_at, done_at, assignee_id, assignee_name, reminded"
)


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id         INTEGER NOT NULL,
            number          INTEGER NOT NULL,
            author_id       INTEGER NOT NULL,
            author_name     TEXT NOT NULL,
            author_username TEXT,
            brand           TEXT NOT NULL,
            work_type       TEXT NOT NULL,
            fmt             TEXT NOT NULL,
            copy_text       TEXT NOT NULL,
            materials       TEXT NOT NULL,
            reference       TEXT NOT NULL,
            note            TEXT NOT NULL DEFAULT '',
            deadline        TEXT NOT NULL,
            priority        TEXT NOT NULL,
            reason          TEXT NOT NULL DEFAULT '',
            status          TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            taken_at        TEXT,
            done_at         TEXT,
            assignee_id     INTEGER,
            assignee_name   TEXT,
            reminded        INTEGER NOT NULL DEFAULT 0,
            UNIQUE (chat_id, number)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status, deadline)")
    conn.commit()
    return conn


def create(
    conn: sqlite3.Connection,
    *,
    chat_id: int,
    author_id: int,
    author_name: str,
    author_username: Optional[str],
    brand: str,
    work_type: str,
    fmt: str,
    copy_text: str,
    materials: str,
    reference: str,
    note: str,
    deadline: datetime,
    priority: str,
    reason: str,
    created_at: datetime,
) -> Task:
    number = conn.execute(
        "SELECT COALESCE(MAX(number), 0) + 1 FROM tasks WHERE chat_id = ?", (chat_id,)
    ).fetchone()[0]
    cur = conn.execute(
        """
        INSERT INTO tasks (
            chat_id, number, author_id, author_name, author_username, brand, work_type, fmt,
            copy_text, materials, reference, note, deadline, priority, reason, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            chat_id, number, author_id, author_name, author_username, brand, work_type, fmt,
            copy_text, materials, reference, note, to_ts(deadline), priority, reason,
            STATUS_NEW, to_ts(created_at),
        ),
    )
    conn.commit()
    created = get_by_id(conn, cur.lastrowid)
    assert created is not None
    return created


def get_by_id(conn: sqlite3.Connection, task_id: int) -> Optional[Task]:
    row = conn.execute(f"SELECT {_COLUMNS} FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return Task(*row) if row else None


def get(conn: sqlite3.Connection, chat_id: int, number: int) -> Optional[Task]:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM tasks WHERE chat_id = ? AND number = ?", (chat_id, number)
    ).fetchone()
    return Task(*row) if row else None


def list_open(conn: sqlite3.Connection, chat_id: int) -> list[Task]:
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM tasks WHERE chat_id = ? AND status IN (?, ?)",
        (chat_id, STATUS_NEW, STATUS_IN_PROGRESS),
    ).fetchall()
    return sorted((Task(*row) for row in rows), key=queue_key)


def list_open_everywhere(conn: sqlite3.Connection) -> list[Task]:
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM tasks WHERE status IN (?, ?)",
        (STATUS_NEW, STATUS_IN_PROGRESS),
    ).fetchall()
    return sorted((Task(*row) for row in rows), key=queue_key)


def list_created_between(
    conn: sqlite3.Connection, chat_id: int, start: datetime, end: datetime
) -> list[Task]:
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM tasks WHERE chat_id = ? AND created_at >= ? AND created_at < ?",
        (chat_id, to_ts(start), to_ts(end)),
    ).fetchall()
    return [Task(*row) for row in rows]


def list_created_between_all(
    conn: sqlite3.Connection, start: datetime, end: datetime
) -> list[Task]:
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM tasks WHERE created_at >= ? AND created_at < ?",
        (to_ts(start), to_ts(end)),
    ).fetchall()
    return [Task(*row) for row in rows]


def queue_key(task: Task) -> tuple[int, str]:
    """Navbat tartibi: avval ishdagilar, so'ng deadline bo'yicha — eng yaqini birinchi."""
    return (0 if task.status == STATUS_IN_PROGRESS else 1, task.deadline)


def position_of(queue: list[Task], task: Task) -> int:
    for index, item in enumerate(queue, start=1):
        if item.id == task.id:
            return index
    return len(queue)


def count_in_progress(conn: sqlite3.Connection, chat_id: int, user_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE chat_id = ? AND assignee_id = ? AND status = ?",
        (chat_id, user_id, STATUS_IN_PROGRESS),
    ).fetchone()[0]


def take(
    conn: sqlite3.Connection, task_id: int, user_id: int, user_name: str, when: datetime
) -> None:
    conn.execute(
        "UPDATE tasks SET status = ?, assignee_id = ?, assignee_name = ?, taken_at = ? "
        "WHERE id = ?",
        (STATUS_IN_PROGRESS, user_id, user_name, to_ts(when), task_id),
    )
    conn.commit()


def finish(conn: sqlite3.Connection, task_id: int, when: datetime) -> None:
    conn.execute(
        "UPDATE tasks SET status = ?, done_at = ? WHERE id = ?",
        (STATUS_DONE, to_ts(when), task_id),
    )
    conn.commit()


def cancel(conn: sqlite3.Connection, task_id: int) -> None:
    conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (STATUS_CANCELLED, task_id))
    conn.commit()


def mark_reminded(conn: sqlite3.Connection, task_id: int, flag: int) -> None:
    conn.execute("UPDATE tasks SET reminded = reminded | ? WHERE id = ?", (flag, task_id))
    conn.commit()
