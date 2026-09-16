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

from app import handlers, scheduler, store
from app.config import load_config

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

COMMANDS = [
    BotCommand("tz", "Yangi TZ berish"),
    BotCommand("navbat", "Ochiq TZ lar"),
    BotCommand("tayyor", "TZ ni yopish — /tayyor ID_160926"),
    BotCommand("bekor", "TZ ni bekor qilish"),
    BotCommand("shablon", "TZ shabloni"),
    BotCommand("topik", "Topikni ro'yxatga olish"),
    BotCommand("hisobot", "7 kunlik statistika"),
    BotCommand("help", "Yordam"),
]

REMINDER_INTERVAL_SECONDS = 30 * 60


async def _post_init(application: Application) -> None:
    await application.bot.set_my_commands(COMMANDS)


def _build_tz_conversation() -> ConversationHandler:
    text_only = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[CommandHandler("tz", handlers.tz_start)],
        states={
            handlers.ASK_GROUP: [
                CallbackQueryHandler(handlers.ask_group, pattern=r"^grp:")
            ],
            handlers.ASK_TOPIC: [
                CallbackQueryHandler(handlers.ask_topic, pattern=r"^top:")
            ],
            handlers.ASK_CLIENT: [MessageHandler(text_only, handlers.ask_client)],
            handlers.ASK_KIND: [CallbackQueryHandler(handlers.ask_kind, pattern=r"^kind:")],
            handlers.ASK_KIND_CUSTOM: [MessageHandler(text_only, handlers.ask_kind_custom)],
            handlers.ASK_SUBJECT: [MessageHandler(text_only, handlers.ask_subject)],
            handlers.ASK_DEADLINE: [
                CallbackQueryHandler(handlers.ask_deadline_button, pattern=r"^dl:"),
                MessageHandler(text_only, handlers.ask_deadline_text),
            ],
            handlers.ASK_DESIGNERS: [MessageHandler(text_only, handlers.ask_designers)],
            handlers.ASK_BODY: [MessageHandler(text_only, handlers.ask_body)],
            handlers.ASK_NOTE: [
                CallbackQueryHandler(handlers.ask_note_button, pattern=r"^note:"),
                MessageHandler(text_only, handlers.ask_note_text),
            ],
        },
        fallbacks=[CommandHandler("cancel", handlers.cancel_conversation)],
    )


def main() -> None:
    config = load_config()

    application = (
        Application.builder().token(config.bot_token).post_init(_post_init).build()
    )
    application.bot_data["db"] = store.connect(config.db_path)
    application.bot_data["config"] = config
    application.bot_data["tz"] = ZoneInfo(config.timezone)

    # -1 guruhdagi handler har bir xabarda ishlaydi va asosiy handlerlarga xalaqit bermaydi
    application.add_handler(MessageHandler(filters.ALL, handlers.remember), group=-1)

    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("help", handlers.start))
    application.add_handler(CommandHandler("shablon", handlers.template))
    application.add_handler(_build_tz_conversation())
    application.add_handler(CommandHandler("navbat", handlers.queue_command))
    application.add_handler(CommandHandler("tayyor", handlers.finish_task))
    application.add_handler(CommandHandler("bekor", handlers.cancel_task))
    application.add_handler(CommandHandler("topik", handlers.topic_command))
    application.add_handler(CommandHandler("hisobot", handlers.report))

    tz = ZoneInfo(config.timezone)
    digest_time = datetime.time(
        hour=config.digest_hour, minute=config.digest_minute, tzinfo=tz
    )
    application.job_queue.run_repeating(
        scheduler.send_reminders,
        interval=REMINDER_INTERVAL_SECONDS,
        first=60,
        name="deadline_reminders",
    )
    application.job_queue.run_daily(
        scheduler.send_daily_digest, time=digest_time, name="daily_digest"
    )
    # Haftalik hisobot har kuni tekshiriladi, faqat dushanba kuni yuboriladi
    application.job_queue.run_daily(
        scheduler.send_weekly_report, time=digest_time, name="weekly_report"
    )

    logger.info(
        "TZ bot ishga tushdi. Kunlik xulosa %02d:%02d (%s).",
        config.digest_hour,
        config.digest_minute,
        config.timezone,
    )
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
