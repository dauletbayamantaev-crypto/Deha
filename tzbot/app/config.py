import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    timezone: str
    db_path: str
    digest_hour: int
    digest_minute: int
    reminder_lead_hours: int
    rush_hours: int  # hisobotda "shoshilinch" deb sanaladigan muddat chegarasi


def load_config() -> Config:
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "BOT_TOKEN topilmadi. .env faylida BOT_TOKEN=... qiymatini kiriting "
            "(.env.example asosida)."
        )
    return Config(
        bot_token=token,
        timezone=os.environ.get("TIMEZONE", "Asia/Tashkent"),
        db_path=os.environ.get("DB_PATH", "tasks.db"),
        digest_hour=int(os.environ.get("DIGEST_HOUR", "9")),
        digest_minute=int(os.environ.get("DIGEST_MINUTE", "30")),
        reminder_lead_hours=int(os.environ.get("REMINDER_LEAD_HOURS", "2")),
        rush_hours=int(os.environ.get("RUSH_HOURS", "4")),
    )
