import calendar
import logging
import sqlite3
from datetime import date

from telegram.error import Forbidden, TelegramError
from telegram.ext import ContextTypes

from bot import database as db
from bot.handlers import _mention

logger = logging.getLogger(__name__)


async def send_daily_birthdays(context: ContextTypes.DEFAULT_TYPE) -> None:
    conn: sqlite3.Connection = context.bot_data["db"]
    today = date.today()

    entries = db.list_birthdays_on(conn, today.month, today.day)

    # 29-fevral tug'ilganlarni kabisa bo'lmagan yilda 28-fevralda ham tabriklaymiz
    if today.month == 2 and today.day == 28 and not calendar.isleap(today.year):
        entries += db.list_birthdays_on(conn, 2, 29)

    if not entries:
        return

    by_chat: dict[int, list[db.Birthday]] = {}
    for b in entries:
        by_chat.setdefault(b.chat_id, []).append(b)

    for chat_id, people in by_chat.items():
        mentions = []
        for b in people:
            mention = _mention(b.full_name, b.username, b.user_id)
            if b.year:
                age = today.year - b.year
                mention += f" ({age} yosh)"
            mentions.append(mention)

        if len(mentions) == 1:
            text = f"🎉🎂 Bugun {mentions[0]} ning tug'ilgan kuni! Tabriklaymiz! 🥳"
        else:
            joined = ", ".join(mentions)
            text = f"🎉🎂 Bugun {joined} ning tug'ilgan kuni! Barchalarini tabriklaymiz! 🥳"

        try:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        except Forbidden:
            logger.warning("Bot %s guruhidan chiqarilgan yoki bloklangan, o'tkazib yuborildi.", chat_id)
        except TelegramError:
            logger.exception("Chat %s ga eslatma yuborishda xatolik.", chat_id)
