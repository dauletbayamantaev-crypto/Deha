import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    timezone: str
    reminder_hour: int
    reminder_minute: int
    db_path: str
    team_name: str


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
        reminder_hour=int(os.environ.get("REMINDER_HOUR", "9")),
        reminder_minute=int(os.environ.get("REMINDER_MINUTE", "0")),
        db_path=os.environ.get("DB_PATH", "birthdays.db"),
        team_name=os.environ.get("TEAM_NAME", "Jamoa"),
    )
