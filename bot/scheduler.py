import calendar
import logging
import sqlite3
from datetime import date

from telegram.error import Forbidden, TelegramError
from telegram.ext import ContextTypes

from bot import database as db
from bot.handlers import _mention

logger = logging.getLogger(__name__)

_ADJECTIVE = {
    "M": "zabardast",
    "F": "go'zal",
}
_DEFAULT_ADJECTIVE = "qadrli"


def _congratulation(team_name: str, mention: str, gender: str | None, age: int | None) -> str:
    adjective = _ADJECTIVE.get(gender, _DEFAULT_ADJECTIVE)
    age_part = f" ({age} yosh)" if age is not None else ""
    return (
        f"🎉 {team_name} jamoasining {adjective} xodimi {mention}{age_part}!\n"
        "Sizni bugungi tug'ilgan kuningiz bilan tabriklaymiz! 🥳"
    )


async def send_daily_birthdays(context: ContextTypes.DEFAULT_TYPE) -> None:
    conn: sqlite3.Connection = context.bot_data["db"]
    team_name: str = context.bot_data["team_name"]
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
        messages = []
        for b in people:
            mention = _mention(b.full_name, b.username, b.user_id)
            age = (today.year - b.year) if b.year else None
            messages.append(_congratulation(team_name, mention, b.gender, age))

        text = "\n\n".join(messages)

        try:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        except Forbidden:
            logger.warning("Bot %s guruhidan chiqarilgan yoki bloklangan, o'tkazib yuborildi.", chat_id)
        except TelegramError:
            logger.exception("Chat %s ga eslatma yuborishda xatolik.", chat_id)
