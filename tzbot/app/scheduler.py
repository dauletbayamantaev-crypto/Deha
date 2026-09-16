"""Avtomatik eslatmalar: deadline yaqinlashuvi, kechikish, kunlik va haftalik xulosa."""

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from telegram.error import TelegramError
from telegram.ext import ContextTypes

from app import render, store, tzform
from app.config import Config

logger = logging.getLogger(__name__)

MONDAY = 0


def _now(context: ContextTypes.DEFAULT_TYPE) -> datetime:
    return datetime.now(context.bot_data["tz"]).replace(tzinfo=None, second=0, microsecond=0)


async def _send(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, thread_id: int | None = None
) -> None:
    kwargs: dict[str, Any] = {}
    if thread_id:
        kwargs["message_thread_id"] = thread_id
    try:
        await context.bot.send_message(
            chat_id=chat_id, text=text, parse_mode="HTML",
            disable_web_page_preview=True, **kwargs,
        )
    except TelegramError:
        logger.warning("Xabar yuborilmadi: chat=%s thread=%s", chat_id, thread_id)


async def _ping_designers(context: ContextTypes.DEFAULT_TYPE, task: store.Task, text: str) -> None:
    conn: sqlite3.Connection = context.bot_data["db"]
    for name in task.designer_list:
        found = store.find_user(conn, name)
        if found and found[1]:
            await _send(context, found[1], text)


async def send_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    conn: sqlite3.Connection = context.bot_data["db"]
    config: Config = context.bot_data["config"]
    now = _now(context)

    for task in store.list_open(conn):
        deadline = task.deadline_dt
        who = render.designers_line(task)

        if deadline < now and not task.reminded & store.REMINDED_OVERDUE:
            late = (now - deadline).total_seconds() / 3600
            text = (
                f"⚠️ <b>{render.esc(task.code)}</b> ({render.esc(task.client)}) deadline'i "
                f"{tzform.format_hours(late)} oldin o'tdi.\nDizayner: {who}"
            )
            await _send(context, task.chat_id, text, task.thread_id)
            await _ping_designers(context, task, text)
            store.mark_reminded(conn, task.id, store.REMINDED_OVERDUE)
            continue

        soon = now + timedelta(hours=config.reminder_lead_hours)
        if now <= deadline <= soon and not task.reminded & store.REMINDED_SOON:
            left = (deadline - now).total_seconds() / 3600
            text = (
                f"⏳ <b>{render.esc(task.code)}</b> ({render.esc(task.client)}) — "
                f"{tzform.format_hours(left)} qoldi.\nDizayner: {who}"
            )
            await _send(context, task.chat_id, text, task.thread_id)
            await _ping_designers(context, task, text)
            store.mark_reminded(conn, task.id, store.REMINDED_SOON)


async def send_daily_digest(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Har kuni ertalab — har bir guruhga o'sha kungi ochiq TZ lar."""
    conn: sqlite3.Connection = context.bot_data["db"]
    now = _now(context)

    by_chat: dict[int, list[store.Task]] = {}
    for task in store.list_open(conn):
        by_chat.setdefault(task.chat_id, []).append(task)

    for chat_id, tasks in by_chat.items():
        text = render.render_queue(tasks, now, title="☀️ <b>Bugungi ochiq TZ lar</b>")
        today_end = now.replace(hour=23, minute=59)
        due_today = [t for t in tasks if t.deadline_dt <= today_end]
        if due_today:
            codes = ", ".join(t.code for t in due_today)
            text += f"\n\n🎯 Bugun topshiriladi: {codes}"
        await _send(context, chat_id, text)


async def send_weekly_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dushanba ertalab — o'tgan haftaning ochiq statistikasi."""
    now = _now(context)
    if now.weekday() != MONDAY:
        return

    conn: sqlite3.Connection = context.bot_data["db"]
    config: Config = context.bot_data["config"]
    start = (now - timedelta(days=7)).replace(hour=0, minute=0)
    end = now + timedelta(minutes=1)

    tasks = store.list_created_between(conn, start, end)
    by_chat: dict[int, list[store.Task]] = {}
    for task in tasks:
        by_chat.setdefault(task.chat_id, []).append(task)

    for chat_id, chat_tasks in by_chat.items():
        text = render.render_report(
            chat_tasks, start, now, config.rush_hours, "📊 <b>O'tgan hafta</b>"
        )
        await _send(context, chat_id, text)
