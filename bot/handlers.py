import sqlite3
from datetime import date

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from bot import database as db
from bot.dateparse import parse_birthday

HELP_TEXT = (
    "🎂 *Tug'ilgan kunlar boti*\n\n"
    "/setbirthday KK-OO yoki KK-OO-YYYY — tug'ilgan kuningizni saqlash\n"
    "  Masalan: `/setbirthday 15-03` yoki `/setbirthday 15-03-1998`\n"
    "/mybirthday — saqlangan tug'ilgan kuningizni ko'rish\n"
    "/removebirthday — tug'ilgan kuningizni o'chirish\n"
    "/birthdays — guruhdagi barcha tug'ilgan kunlar ro'yxati\n"
    "/help — shu xabarni ko'rsatish\n\n"
    "Bot har kuni ertalab guruhga o'sha kuni tug'ilgan kuni bo'lganlarni "
    "avtomatik eslatib turadi."
)

USAGE_TEXT = (
    "Format: `/setbirthday KK-OO` yoki `/setbirthday KK-OO-YYYY`\n"
    "Masalan: `/setbirthday 15-03` yoki `/setbirthday 15-03-1998`"
)


def _mention(full_name: str, username: str | None, user_id: int) -> str:
    if username:
        return f"@{username}"
    escaped = full_name.replace("[", "").replace("]", "")
    return f"[{escaped}](tg://user?id={user_id})"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def set_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    conn: sqlite3.Connection = context.bot_data["db"]

    if chat.type == ChatType.PRIVATE:
        await update.message.reply_text(
            "Bu buyruq faqat jamoa guruhida ishlaydi. Guruhga qo'shing va o'sha yerda ishlating."
        )
        return

    if not context.args:
        await update.message.reply_text(USAGE_TEXT, parse_mode="Markdown")
        return

    parsed = parse_birthday(" ".join(context.args))
    if parsed is None:
        await update.message.reply_text(
            "❌ Sana noto'g'ri formatda yoki mavjud emas.\n\n" + USAGE_TEXT,
            parse_mode="Markdown",
        )
        return

    day, month, year = parsed
    full_name = user.full_name or user.first_name
    db.upsert_birthday(conn, chat.id, user.id, full_name, user.username, day, month, year)

    date_str = f"{day:02d}.{month:02d}" + (f".{year}" if year else "")
    await update.message.reply_text(f"✅ {full_name} uchun tug'ilgan kun saqlandi: {date_str}")


async def my_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    conn: sqlite3.Connection = context.bot_data["db"]

    if chat.type == ChatType.PRIVATE:
        await update.message.reply_text("Bu buyruq faqat guruhda ishlaydi.")
        return

    b = db.get_birthday(conn, chat.id, user.id)
    if b is None:
        await update.message.reply_text(
            "Sizning tug'ilgan kuningiz saqlanmagan. /setbirthday orqali qo'shing."
        )
        return

    date_str = f"{b.day:02d}.{b.month:02d}" + (f".{b.year}" if b.year else "")
    await update.message.reply_text(f"🎂 Sizning tug'ilgan kuningiz: {date_str}")


async def remove_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    conn: sqlite3.Connection = context.bot_data["db"]

    if chat.type == ChatType.PRIVATE:
        await update.message.reply_text("Bu buyruq faqat guruhda ishlaydi.")
        return

    removed = db.delete_birthday(conn, chat.id, user.id)
    if removed:
        await update.message.reply_text("🗑 Tug'ilgan kuningiz o'chirildi.")
    else:
        await update.message.reply_text("Sizda saqlangan tug'ilgan kun topilmadi.")


async def list_birthdays(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    conn: sqlite3.Connection = context.bot_data["db"]

    if chat.type == ChatType.PRIVATE:
        await update.message.reply_text("Bu buyruq faqat guruhda ishlaydi.")
        return

    entries = db.list_birthdays_for_chat(conn, chat.id)
    if not entries:
        await update.message.reply_text(
            "Bu guruhda hali hech kim tug'ilgan kunini saqlamagan. /setbirthday bilan qo'shing."
        )
        return

    today = date.today()
    entries.sort(key=lambda b: db.days_until_next(b, today))

    lines = ["🎂 *Guruh tug'ilgan kunlari:*\n"]
    for b in entries:
        date_str = f"{b.day:02d}.{b.month:02d}"
        name = _mention(b.full_name, b.username, b.user_id)
        left = db.days_until_next(b, today)
        if left == 0:
            suffix = " — 🎉 bugun!"
        elif left == 1:
            suffix = " — ertaga"
        else:
            suffix = f" — {left} kundan keyin"
        lines.append(f"• {date_str} — {name}{suffix}")

    await update.message.reply_text(
        "\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True
    )
