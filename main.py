import datetime
import logging
from zoneinfo import ZoneInfo

from telegram import BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot import database as db
from bot import handlers
from bot.config import load_config
from bot.scheduler import send_daily_birthdays

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

COMMANDS = [
    BotCommand("newbirthday", "Tug'ilgan kuningizni qo'shish"),
    BotCommand("comingbirthday", "Yaqinlashib kelayotgan tug'ilgan kunlar"),
    BotCommand("mybirthday", "Mening saqlangan tug'ilgan kunim"),
    BotCommand("removebirthday", "Tug'ilgan kunimni o'chirish"),
    BotCommand("help", "Yordam"),
]


async def _post_init(application: Application) -> None:
    await application.bot.set_my_commands(COMMANDS)


def main() -> None:
    config = load_config()

    application = Application.builder().token(config.bot_token).post_init(_post_init).build()
    application.bot_data["db"] = db.connect(config.db_path)
    application.bot_data["team_name"] = config.team_name

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("newbirthday", handlers.new_birthday_start)],
        states={
            handlers.ASK_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.new_birthday_date)
            ],
            handlers.ASK_GENDER: [
                CallbackQueryHandler(handlers.new_birthday_gender, pattern=r"^gender:")
            ],
        },
        fallbacks=[CommandHandler("cancel", handlers.cancel)],
    )

    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("mybirthday", handlers.my_birthday))
    application.add_handler(CommandHandler("removebirthday", handlers.remove_birthday))
    application.add_handler(CommandHandler("comingbirthday", handlers.list_birthdays))

    tz = ZoneInfo(config.timezone)
    reminder_time = datetime.time(
        hour=config.reminder_hour, minute=config.reminder_minute, tzinfo=tz
    )
    application.job_queue.run_daily(send_daily_birthdays, time=reminder_time, name="daily_birthdays")

    logger.info(
        "Bot ishga tushdi. Har kuni %02d:%02d (%s) da eslatmalar yuboriladi.",
        config.reminder_hour,
        config.reminder_minute,
        config.timezone,
    )
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
