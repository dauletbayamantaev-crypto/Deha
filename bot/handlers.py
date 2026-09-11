import sqlite3
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes, ConversationHandler

from bot import database as db
from bot.dateparse import parse_birthday

ASK_DATE, ASK_GENDER = range(2)

HELP_TEXT = (
    "🎂 *Tug'ilgan kunlar boti*\n\n"
    "/newbirthday — tug'ilgan kuningizni qo'shish (savol-javob tartibida)\n"
    "/mybirthday — saqlangan tug'ilgan kuningizni ko'rish\n"
    "/removebirthday — tug'ilgan kuningizni o'chirish\n"
    "/comingbirthday — guruhdagi yaqinlashib kelayotgan tug'ilgan kunlar\n"
    "/help — shu xabarni ko'rsatish\n\n"
    "Bot har kuni ertalab guruhga o'sha kuni tug'ilgan kuni bo'lganlarni "
    "avtomatik eslatib turadi.\n\n"
    "Buyruqlarni xabar yozish maydonidagi \"/\" tugmasini bosib ham tanlashingiz mumkin."
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


# ---- /newbirthday: savol-javob tartibidagi suhbat ----

async def new_birthday_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat = update.effective_chat
    if chat.type == ChatType.PRIVATE:
        await update.message.reply_text(
            "Bu buyruq faqat jamoa guruhida ishlaydi. Guruhga qo'shing va o'sha yerda ishlating."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "🎂 Tug'ilgan kuningizni kiriting.\n\n"
        "Format: *kun-oy* yoki *kun-oy-yil*\n"
        "Masalan: `15-03` yoki `15-03-1998`\n\n"
        "Bekor qilish uchun /cancel yozing.",
        parse_mode="Markdown",
    )
    return ASK_DATE


async def new_birthday_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    parsed = parse_birthday(update.message.text.strip())
    if parsed is None:
        await update.message.reply_text(
            "❌ Sana noto'g'ri formatda yoki mavjud emas.\n\n"
            "Qaytadan urinib ko'ring, masalan: `15-03` yoki `15-03-1998`\n"
            "Bekor qilish uchun /cancel yozing.",
            parse_mode="Markdown",
        )
        return ASK_DATE

    context.user_data["pending_birthday"] = parsed
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👦 O'g'il bola", callback_data="gender:M"),
                InlineKeyboardButton("👧 Qiz bola", callback_data="gender:F"),
            ]
        ]
    )
    await update.message.reply_text("Jinsingizni tanlang:", reply_markup=keyboard)
    return ASK_GENDER


async def new_birthday_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    pending = context.user_data.pop("pending_birthday", None)
    if pending is None:
        await query.edit_message_text("Sessiya eskirgan, /newbirthday bilan qaytadan boshlang.")
        return ConversationHandler.END

    day, month, year = pending
    gender = query.data.split(":")[1]

    user = update.effective_user
    chat = update.effective_chat
    conn: sqlite3.Connection = context.bot_data["db"]
    full_name = user.full_name or user.first_name

    db.upsert_birthday(conn, chat.id, user.id, full_name, user.username, day, month, year, gender)

    date_str = f"{day:02d}.{month:02d}" + (f".{year}" if year else "")
    await query.edit_message_text(f"✅ {full_name} uchun tug'ilgan kun saqlandi: {date_str}")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("pending_birthday", None)
    await update.message.reply_text("Bekor qilindi.")
    return ConversationHandler.END


# ---- boshqa buyruqlar ----

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
            "Sizning tug'ilgan kuningiz saqlanmagan. /newbirthday orqali qo'shing."
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
            "Bu guruhda hali hech kim tug'ilgan kunini saqlamagan. /newbirthday bilan qo'shing."
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
