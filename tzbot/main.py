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

from app import handlers, scheduler, tasks
from app.config import load_config

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

COMMANDS = [
    BotCommand("tz", "Yangi TZ berish"),
    BotCommand("shablon", "TZ shablonini olish"),
    BotCommand("navbat", "Hozirgi navbat"),
    BotCommand("boshladim", "TZ ni ishga olish (dizayner)"),
    BotCommand("tayyor", "TZ ni yopish (dizayner)"),
    BotCommand("mentz", "Mening ochiq TZ larim"),
    BotCommand("bekor", "TZ ni bekor qilish"),
    BotCommand("hisobot", "7 kunlik statistika"),
    BotCommand("qoida", "Ishlash qoidalari"),
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
            handlers.ASK_BRAND: [MessageHandler(text_only, handlers.ask_brand)],
            handlers.ASK_TYPE: [CallbackQueryHandler(handlers.ask_type, pattern=r"^wt:")],
            handlers.ASK_FORMAT: [CallbackQueryHandler(handlers.ask_format, pattern=r"^fmt:")],
            handlers.ASK_FORMAT_CUSTOM: [
                MessageHandler(text_only, handlers.ask_format_custom)
            ],
            handlers.ASK_COPY: [MessageHandler(text_only, handlers.ask_copy)],
            handlers.ASK_MATERIALS: [MessageHandler(text_only, handlers.ask_materials)],
            handlers.ASK_REFERENCE: [MessageHandler(text_only, handlers.ask_reference)],
            handlers.ASK_DEADLINE: [MessageHandler(text_only, handlers.ask_deadline)],
            handlers.ASK_REASON: [MessageHandler(text_only, handlers.ask_reason)],
        },
        fallbacks=[CommandHandler("cancel", handlers.cancel)],
    )


def main() -> None:
    config = load_config()

    application = (
        Application.builder().token(config.bot_token).post_init(_post_init).build()
    )
    application.bot_data["db"] = tasks.connect(config.db_path)
    application.bot_data["config"] = config
    application.bot_data["tz"] = ZoneInfo(config.timezone)

    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("qoida", handlers.rules))
    application.add_handler(CommandHandler("shablon", handlers.template))
    application.add_handler(_build_tz_conversation())
    application.add_handler(CommandHandler("navbat", handlers.queue_command))
    application.add_handler(CommandHandler("mentz", handlers.my_tz))
    application.add_handler(CommandHandler("boshladim", handlers.take_task))
    application.add_handler(CommandHandler("tayyor", handlers.finish_task))
    application.add_handler(CommandHandler("bekor", handlers.cancel_task))
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
        "TZ bot ishga tushdi. Kunlik xulosa %02d:%02d (%s), WIP limit: %d.",
        config.digest_hour,
        config.digest_minute,
        config.timezone,
        config.wip_limit,
    )
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
