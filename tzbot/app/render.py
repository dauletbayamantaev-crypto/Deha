"""Telegram xabarlarini namunadagi ko'rinishda yig'ish."""

import html
from datetime import datetime
from typing import Optional

from app import store, tzform

MAX_BODY = 2500
MAX_FIELD = 400
QUEUE_PAGE_SIZE = 25


def esc(text: Optional[str]) -> str:
    return html.escape(text or "")


def clip(text: str, limit: int) -> str:
    """Telegram xabari 4096 belgidan oshmasligi uchun uzun matnni qisqartiradi."""
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rstrip() + " …"


def mention(name: str, username: Optional[str], user_id: int) -> str:
    if username:
        return f"@{esc(username)}"
    return f'<a href="tg://user?id={user_id}">{esc(name)}</a>'


def designers_line(task: store.Task) -> str:
    names = task.designer_list
    return " ".join(f"@{esc(name)}" for name in names) if names else "—"


def hashtags(task: store.Task) -> str:
    kind = tzform.KIND_BY_KEY.get(task.kind)
    tags = [f"#{tzform.slug(task.client)}"]
    if kind:
        tags.append(f"#{kind.tag}")
    return " ".join(tags)


def render_task(task: store.Task, *, with_hint: bool = True) -> str:
    """Guruhga yuboriladigan TZ xabari."""
    author = mention(task.author_name, task.author_username, task.author_id)

    lines = [
        f"<b>{esc(task.code)}</b>",
        f"TZ (Texnik topshiriq) {author} tomonidan berildi.",
        f"<b>Mijoz:</b> {esc(clip(task.client, MAX_FIELD))}",
        f"<b>Tasnif:</b> {esc(clip(task.tasnif, MAX_FIELD))}",
        f"<b>Mavzu:</b> {esc(clip(task.subject, MAX_FIELD))}",
        f"<b>Deadline:</b> {task.deadline_dt:%d.%m.%Y %H:%M}",
        f"<b>Dizayner:</b> {designers_line(task)}",
        "",
        esc(clip(task.body, MAX_BODY)),
    ]

    if task.note:
        lines += ["", f"<b>Izoh:</b> {esc(clip(task.note, MAX_FIELD))}"]

    lines += ["", hashtags(task)]

    if task.status != store.STATUS_NEW:
        lines.append(f"\n<b>Holat:</b> {store.STATUS_LABEL[task.status]}")
    elif with_hint:
        lines.append(f"\n<i>Tayyor bo'lgach: /tayyor {esc(task.code)}</i>")

    return "\n".join(lines)


def render_notification(task: store.Task, group_title: str, link: Optional[str]) -> str:
    """Dizaynerga shaxsiy chatda boradigan bildirishnoma."""
    header = f"🔔 <b>Sizga yangi TZ biriktirildi</b>\n📍 {esc(group_title)}"
    if link:
        header += f' · <a href="{link}">guruhda ochish</a>'
    return f"{header}\n\n{render_task(task)}"


def render_queue(
    tasks: list[store.Task], now: datetime, title: str = "📋 <b>Ochiq TZ lar</b>"
) -> str:
    if not tasks:
        return f"{title}\n\nOchiq TZ yo'q. 🎉"

    lines = [f"{title} — {len(tasks)} ta\n"]
    shown, hidden = tasks[:QUEUE_PAGE_SIZE], tasks[QUEUE_PAGE_SIZE:]
    for task in shown:
        late = " ⚠️" if task.deadline_dt < now else ""
        lines.append(
            f"<b>{esc(task.code)}</b> · {esc(task.client)} · {esc(clip(task.subject, 60))}\n"
            f"    ⏰ {task.deadline_dt:%d.%m %H:%M}{late} · 👤 {designers_line(task)}"
        )
    if hidden:
        lines.append(f"\n… va yana {len(hidden)} ta.")
    return "\n".join(lines)


def render_report(
    tasks: list[store.Task], start: datetime, end: datetime, rush_hours: int, title: str
) -> str:
    header = f"{title}\n<i>{start:%d.%m} — {end:%d.%m}</i>"
    if not tasks:
        return f"{header}\n\nBu davrda bitta ham TZ berilmagan."

    done = [t for t in tasks if t.status == store.STATUS_DONE]
    late = [t for t in done if t.is_late]
    rush = [t for t in tasks if t.lead_hours < rush_hours]
    still_open = [t for t in tasks if t.status in store.OPEN_STATUSES]
    avg_lead = sum(t.lead_hours for t in tasks) / len(tasks)

    lines = [
        header,
        "",
        f"📥 Jami TZ: <b>{len(tasks)}</b>",
        f"✅ Tayyor: <b>{len(done)}</b>" + (f" (⚠️ {len(late)} tasi kechikkan)" if late else ""),
        f"🔄 Ochiq: <b>{len(still_open)}</b>",
        f"🔥 {rush_hours} soatdan kam muddat bilan berilgan: <b>{len(rush)}</b> "
        f"({round(len(rush) / len(tasks) * 100)}%)",
        f"⏱ O'rtacha berilgan muddat: <b>{tzform.format_hours(avg_lead)}</b>",
        "",
        "<b>Kim qancha TZ berdi:</b>",
    ]

    by_author: dict[int, list[store.Task]] = {}
    for task in tasks:
        by_author.setdefault(task.author_id, []).append(task)

    for author_tasks in sorted(by_author.values(), key=len, reverse=True):
        first = author_tasks[0]
        who = mention(first.author_name, first.author_username, first.author_id)
        rushed = sum(1 for t in author_tasks if t.lead_hours < rush_hours)
        lead = sum(t.lead_hours for t in author_tasks) / len(author_tasks)
        rush_part = f", 🔥 {rushed} ta shoshilinch" if rushed else ""
        lines.append(
            f"• {who} — {len(author_tasks)} ta{rush_part}, "
            f"o'rtacha muddat {tzform.format_hours(lead)}"
        )

    designer_counts: dict[str, int] = {}
    for task in done:
        for name in task.designer_list:
            designer_counts[name] = designer_counts.get(name, 0) + 1
    if designer_counts:
        lines += ["", "<b>Dizaynerlar bajardi:</b>"]
        for name, count in sorted(designer_counts.items(), key=lambda pair: -pair[1]):
            lines.append(f"• @{esc(name)} — {count} ta")

    return "\n".join(lines)


def message_link(chat_id: int, message_id: int, thread_id: Optional[int] = None) -> Optional[str]:
    """Supergruppa xabariga havola: https://t.me/c/<id>/<thread>/<message>."""
    text = str(chat_id)
    if not text.startswith("-100"):
        return None
    internal = text[4:]
    if thread_id:
        return f"https://t.me/c/{internal}/{thread_id}/{message_id}"
    return f"https://t.me/c/{internal}/{message_id}"
