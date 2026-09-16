import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    timezone: str
    db_path: str
    team_name: str
    wip_limit: int
    designers: tuple[str, ...]  # @ belgisiz username'lar; bo'sh bo'lsa — cheklov yo'q
    digest_hour: int
    digest_minute: int
    reminder_lead_hours: int


def _usernames(raw: str) -> tuple[str, ...]:
    return tuple(
        name.strip().lstrip("@").lower() for name in raw.split(",") if name.strip()
    )


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
        team_name=os.environ.get("TEAM_NAME", "Jamoa"),
        wip_limit=int(os.environ.get("WIP_LIMIT", "2")),
        designers=_usernames(os.environ.get("DESIGNER_USERNAMES", "")),
        digest_hour=int(os.environ.get("DIGEST_HOUR", "9")),
        digest_minute=int(os.environ.get("DIGEST_MINUTE", "30")),
        reminder_lead_hours=int(os.environ.get("REMINDER_LEAD_HOURS", "2")),
    )
