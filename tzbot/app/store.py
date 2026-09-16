"""Ma'lumotlar bazasi: TZ lar, foydalanuvchilar, guruhlar va topiklar."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

STATUS_NEW = "new"
STATUS_DONE = "done"
STATUS_CANCELLED = "cancelled"

OPEN_STATUSES = (STATUS_NEW,)

STATUS_LABEL = {
    STATUS_NEW: "🆕 Bajarilmoqda",
    STATUS_DONE: "✅ Tayyor",
    STATUS_CANCELLED: "🚫 Bekor qilingan",
}

REMINDED_SOON = 1
REMINDED_OVERDUE = 2

TS = "%Y-%m-%d %H:%M"


def to_ts(moment: datetime) -> str:
    return moment.strftime(TS)


def from_ts(text: str) -> datetime:
    return datetime.strptime(text, TS)


def split_csv(value: Optional[str]) -> list[str]:
    return [part for part in (value or "").split(",") if part]


@dataclass
class Task:
    id: int
    code: str
    chat_id: int
    thread_id: Optional[int]
    author_id: int
    author_name: str
    author_username: Optional[str]
    designers: str  # "ali,vali" — @ belgisiz, vergul bilan
    designer_ids: str
    client: str
    kind: str
    tasnif: str
    subject: str
    body: str
    note: str
    deadline: str
    status: str
    created_at: str
    done_at: Optional[str]
    message_id: Optional[int]
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
    def designer_list(self) -> list[str]:
        return split_csv(self.designers)

    @property
    def designer_id_list(self) -> list[int]:
        return [int(value) for value in split_csv(self.designer_ids)]

    @property
    def is_late(self) -> bool:
        done = self.done_dt
        return done is not None and done > self.deadline_dt

    @property
    def lead_hours(self) -> float:
        return (self.deadline_dt - self.created_dt).total_seconds() / 3600


_COLUMNS = (
    "id, code, chat_id, thread_id, author_id, author_name, author_username, designers, "
    "designer_ids, client, kind, tasnif, subject, body, note, deadline, status, created_at, "
    "done_at, message_id, reminded"
)


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            code            TEXT NOT NULL UNIQUE,
            chat_id         INTEGER NOT NULL,
            thread_id       INTEGER,
            author_id       INTEGER NOT NULL,
            author_name     TEXT NOT NULL,
            author_username TEXT,
            designers       TEXT NOT NULL DEFAULT '',
            designer_ids    TEXT NOT NULL DEFAULT '',
            client          TEXT NOT NULL,
            kind            TEXT NOT NULL,
            tasnif          TEXT NOT NULL,
            subject         TEXT NOT NULL,
            body            TEXT NOT NULL,
            note            TEXT NOT NULL DEFAULT '',
            deadline        TEXT NOT NULL,
            status          TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            done_at         TEXT,
            message_id      INTEGER,
            reminded        INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status, deadline);

        CREATE TABLE IF NOT EXISTS users (
            user_id         INTEGER PRIMARY KEY,
            username        TEXT,
            full_name       TEXT NOT NULL,
            private_chat_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS groups (
            chat_id INTEGER PRIMARY KEY,
            title   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS topics (
            chat_id   INTEGER NOT NULL,
            thread_id INTEGER NOT NULL,
            name      TEXT NOT NULL,
            PRIMARY KEY (chat_id, thread_id)
        );
        """
    )
    conn.commit()
    return conn


# ---- foydalanuvchilar ----

def remember_user(
    conn: sqlite3.Connection,
    user_id: int,
    username: Optional[str],
    full_name: str,
    private_chat_id: Optional[int] = None,
) -> None:
    """Foydalanuvchini eslab qoladi. private_chat_id faqat ma'lum bo'lsa yangilanadi."""
    conn.execute(
        """
        INSERT INTO users (user_id, username, full_name, private_chat_id)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username        = excluded.username,
            full_name       = excluded.full_name,
            private_chat_id = COALESCE(excluded.private_chat_id, users.private_chat_id)
        """,
        (user_id, (username or "").lower() or None, full_name, private_chat_id),
    )
    conn.commit()


def find_user(conn: sqlite3.Connection, username: str) -> Optional[tuple[int, Optional[int]]]:
    """username bo'yicha (user_id, private_chat_id) qaytaradi."""
    row = conn.execute(
        "SELECT user_id, private_chat_id FROM users WHERE username = ?",
        (username.lstrip("@").lower(),),
    ).fetchone()
    return (row[0], row[1]) if row else None


# ---- guruhlar va topiklar ----

def remember_group(conn: sqlite3.Connection, chat_id: int, title: str) -> None:
    conn.execute(
        "INSERT INTO groups (chat_id, title) VALUES (?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET title = excluded.title",
        (chat_id, title),
    )
    conn.commit()


def list_groups(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    return conn.execute("SELECT chat_id, title FROM groups ORDER BY title").fetchall()


def get_group(conn: sqlite3.Connection, chat_id: int) -> Optional[tuple[int, str]]:
    return conn.execute(
        "SELECT chat_id, title FROM groups WHERE chat_id = ?", (chat_id,)
    ).fetchone()


def remember_topic(conn: sqlite3.Connection, chat_id: int, thread_id: int, name: str) -> None:
    conn.execute(
        "INSERT INTO topics (chat_id, thread_id, name) VALUES (?, ?, ?) "
        "ON CONFLICT(chat_id, thread_id) DO UPDATE SET name = excluded.name",
        (chat_id, thread_id, name),
    )
    conn.commit()


def forget_topic(conn: sqlite3.Connection, chat_id: int, thread_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM topics WHERE chat_id = ? AND thread_id = ?", (chat_id, thread_id)
    )
    conn.commit()
    return cur.rowcount > 0


def list_topics(conn: sqlite3.Connection, chat_id: int) -> list[tuple[int, str]]:
    return conn.execute(
        "SELECT thread_id, name FROM topics WHERE chat_id = ? ORDER BY name", (chat_id,)
    ).fetchall()


def get_topic_name(conn: sqlite3.Connection, chat_id: int, thread_id: int) -> Optional[str]:
    row = conn.execute(
        "SELECT name FROM topics WHERE chat_id = ? AND thread_id = ?", (chat_id, thread_id)
    ).fetchone()
    return row[0] if row else None


# ---- TZ lar ----

def next_code(conn: sqlite3.Connection, now: datetime) -> str:
    """Kun bo'yicha ID: ID_160926, o'sha kunning keyingilari ID_160926-2, -3 ..."""
    base = f"ID_{now:%d%m%y}"
    candidate = base
    suffix = 1
    while conn.execute("SELECT 1 FROM tasks WHERE code = ?", (candidate,)).fetchone():
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate


def create_task(
    conn: sqlite3.Connection,
    *,
    code: str,
    chat_id: int,
    thread_id: Optional[int],
    author_id: int,
    author_name: str,
    author_username: Optional[str],
    designers: list[str],
    designer_ids: list[int],
    client: str,
    kind: str,
    tasnif: str,
    subject: str,
    body: str,
    note: str,
    deadline: datetime,
    created_at: datetime,
) -> Task:
    cur = conn.execute(
        """
        INSERT INTO tasks (
            code, chat_id, thread_id, author_id, author_name, author_username, designers,
            designer_ids, client, kind, tasnif, subject, body, note, deadline, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            code, chat_id, thread_id, author_id, author_name, author_username,
            ",".join(designers), ",".join(str(i) for i in designer_ids), client, kind,
            tasnif, subject, body, note, to_ts(deadline), STATUS_NEW, to_ts(created_at),
        ),
    )
    conn.commit()
    created = get_by_id(conn, cur.lastrowid)
    assert created is not None
    return created


def get_by_id(conn: sqlite3.Connection, task_id: int) -> Optional[Task]:
    row = conn.execute(f"SELECT {_COLUMNS} FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return Task(*row) if row else None


def get_by_code(conn: sqlite3.Connection, code: str) -> Optional[Task]:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM tasks WHERE code = ? COLLATE NOCASE", (code,)
    ).fetchone()
    return Task(*row) if row else None


def set_message_id(conn: sqlite3.Connection, task_id: int, message_id: int) -> None:
    conn.execute("UPDATE tasks SET message_id = ? WHERE id = ?", (message_id, task_id))
    conn.commit()


def list_open(conn: sqlite3.Connection, chat_id: Optional[int] = None) -> list[Task]:
    if chat_id is None:
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM tasks WHERE status = ? ORDER BY deadline", (STATUS_NEW,)
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM tasks WHERE status = ? AND chat_id = ? ORDER BY deadline",
            (STATUS_NEW, chat_id),
        ).fetchall()
    return [Task(*row) for row in rows]


def list_open_for_user(conn: sqlite3.Connection, user_id: int) -> list[Task]:
    """Foydalanuvchi bergan yoki unga biriktirilgan ochiq TZ lar."""
    return [
        task
        for task in list_open(conn)
        if task.author_id == user_id or user_id in task.designer_id_list
    ]


def list_created_between(
    conn: sqlite3.Connection, start: datetime, end: datetime, chat_id: Optional[int] = None
) -> list[Task]:
    query = f"SELECT {_COLUMNS} FROM tasks WHERE created_at >= ? AND created_at < ?"
    params: list = [to_ts(start), to_ts(end)]
    if chat_id is not None:
        query += " AND chat_id = ?"
        params.append(chat_id)
    return [Task(*row) for row in conn.execute(query, params).fetchall()]


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
