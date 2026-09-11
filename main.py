import datetime
import logging
from zoneinfo import ZoneInfo

from telegram.ext import Application, CommandHandler

from bot import database as db
from bot import handlers
from bot.config import load_config
from bot.scheduler import send_daily_birthdays

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    config = load_config()

    application = Application.builder().token(config.bot_token).build()
    application.bot_data["db"] = db.connect(config.db_path)

    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("setbirthday", handlers.set_birthday))
    application.add_handler(CommandHandler("mybirthday", handlers.my_birthday))
    application.add_handler(CommandHandler("removebirthday", handlers.remove_birthday))
    application.add_handler(CommandHandler("birthdays", handlers.list_birthdays))

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
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
