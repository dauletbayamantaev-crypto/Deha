"""Avtomatik eslatmalar: deadline yaqinlashuvi, kechikish, kunlik va haftalik xulosa."""

import logging
import sqlite3
from datetime import datetime, timedelta

from telegram.error import Forbidden, TelegramError
from telegram.ext import ContextTypes

from app import handlers, tasks, tzform
from app.config import Config

logger = logging.getLogger(__name__)

MONDAY = 0


def _now(context: ContextTypes.DEFAULT_TYPE) -> datetime:
    return datetime.now(context.bot_data["tz"]).replace(tzinfo=None, second=0, microsecond=0)


async def _send(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str) -> None:
    try:
        await context.bot.send_message(
            chat_id=chat_id, text=text, parse_mode="HTML", disable_web_page_preview=True
        )
    except Forbidden:
        logger.warning("Bot %s guruhidan chiqarilgan, xabar yuborilmadi.", chat_id)
    except TelegramError:
        logger.exception("Chat %s ga xabar yuborishda xatolik.", chat_id)


async def send_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deadline yaqinlashganda va o'tib ketganda guruhga eslatadi."""
    conn: sqlite3.Connection = context.bot_data["db"]
    config: Config = context.bot_data["config"]
    now = _now(context)

    for task in tasks.list_open_everywhere(conn):
        deadline = task.deadline_dt
        author = handlers.mention(task.author_name, task.author_username, task.author_id)

        if deadline < now and not task.reminded & tasks.REMINDED_OVERDUE:
            late = (now - deadline).total_seconds() / 3600
            await _send(
                context,
                task.chat_id,
                f"⚠️ <b>#{task.number}</b> ({handlers.esc(task.brand)}) deadline'i "
                f"{tzform.format_hours(late)} oldin o'tdi.\n"
                f"Holat: {tasks.STATUS_LABEL[task.status]} · TZ bergan: {author}",
            )
            tasks.mark_reminded(conn, task.id, tasks.REMINDED_OVERDUE)
            continue

        soon = now + timedelta(hours=config.reminder_lead_hours)
        if (
            task.status == tasks.STATUS_NEW
            and now <= deadline <= soon
            and not task.reminded & tasks.REMINDED_SOON
        ):
            left = (deadline - now).total_seconds() / 3600
            await _send(
                context,
                task.chat_id,
                f"⏳ <b>#{task.number}</b> ({handlers.esc(task.brand)}) — "
                f"{tzform.format_hours(left)} qoldi, ish hali boshlanmagan.\n"
                f"Dizayner: /boshladim {task.number} · TZ bergan: {author}",
            )
            tasks.mark_reminded(conn, task.id, tasks.REMINDED_SOON)


async def send_daily_digest(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Har kuni ertalab — o'sha kungi navbat."""
    conn: sqlite3.Connection = context.bot_data["db"]
    now = _now(context)

    by_chat: dict[int, list[tasks.Task]] = {}
    for task in tasks.list_open_everywhere(conn):
        by_chat.setdefault(task.chat_id, []).append(task)

    for chat_id, queue in by_chat.items():
        text = handlers.render_queue(queue, now, title="☀️ <b>Bugungi navbat</b>")
        today_end = now.replace(hour=23, minute=59)
        due_today = [t for t in queue if t.deadline_dt <= today_end]
        if due_today:
            numbers = ", ".join(f"#{t.number}" for t in due_today)
            text += f"\n\n🎯 Bugun topshiriladi: {numbers}"
        await _send(context, chat_id, text)


async def send_weekly_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dushanba ertalab — o'tgan haftaning ochiq statistikasi."""
    now = _now(context)
    if now.weekday() != MONDAY:
        return

    conn: sqlite3.Connection = context.bot_data["db"]
    start = (now - timedelta(days=7)).replace(hour=0, minute=0)
    end = now + timedelta(minutes=1)
    chat_ids = {task.chat_id for task in tasks.list_created_between_all(conn, start, end)}

    for chat_id in chat_ids:
        text = handlers.build_report(conn, chat_id, start, end, "📊 <b>O'tgan hafta</b>")
        await _send(context, chat_id, text)
