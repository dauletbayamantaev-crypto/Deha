"""Botni Telegram'siz sinash: soxta Update obyektlari bilan buyruqlarni chaqiradi.

Ishga tushirish:  cd tzbot && python tests/smoke.py
"""

import asyncio
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram.constants import ChatType  # noqa: E402
from telegram.ext import ConversationHandler  # noqa: E402

from app import handlers, tasks, tzform  # noqa: E402
from app.config import Config  # noqa: E402

CHAT_ID = -100123
NOW = datetime(2026, 9, 16, 10, 0)

SMM_ALI = (1, "Ali Valiyev", "smm_ali")
SMM_DILNOZA = (2, "Dilnoza", "smm_dilnoza")
DESIGNER = (9, "Dizayner", "dizayner")

CONFIG = Config(
    bot_token="test", timezone="Asia/Tashkent", db_path=":memory:", team_name="Deha",
    wip_limit=2, designers=("dizayner",), digest_hour=9, digest_minute=30,
    reminder_lead_hours=2,
)


# ---- soxta Telegram obyektlari ----

@dataclass
class FakeUser:
    id: int
    full_name: str
    username: Optional[str]

    @property
    def first_name(self) -> str:
        return self.full_name.split()[0]


@dataclass
class FakeChat:
    id: int
    type: str = ChatType.GROUP


@dataclass
class FakeMessage:
    text: str
    replies: list[str] = field(default_factory=list)

    async def reply_text(self, text: str, **kwargs: Any) -> "FakeMessage":
        self.replies.append(text)
        return self


@dataclass
class FakeUpdate:
    effective_chat: FakeChat
    effective_user: FakeUser
    effective_message: FakeMessage
    callback_query: None = None

    @property
    def message(self) -> FakeMessage:
        return self.effective_message


class FakeContext:
    def __init__(self, bot_data: dict[str, Any], args: Optional[list[str]] = None) -> None:
        self.bot_data = bot_data
        self.args = args or []
        self.user_data: dict[str, Any] = {}


def make(user: tuple[int, str, Optional[str]], text: str) -> FakeUpdate:
    user_id, name, username = user
    return FakeUpdate(
        effective_chat=FakeChat(CHAT_ID),
        effective_user=FakeUser(user_id, name, username),
        effective_message=FakeMessage(text),
    )


# ---- tekshiruv yordamchilari ----

PASSED = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASSED
    if condition:
        PASSED += 1
        print(f"  ✅ {label}")
    else:
        print(f"  ❌ {label}\n     {detail}")
        sys.exit(1)


def last(update: FakeUpdate) -> str:
    return update.effective_message.replies[-1] if update.effective_message.replies else ""


FULL_TZ = """/tz
Brend: Nestle
Ish turi: karusel
Format: 1080x1350
Matn: Sarlavha: Kuzgi chegirma -30%
CTA: Buyurtma bering
Materiallar: https://drive.google.com/abc
Referens: https://pin.it/x
Deadline: 18-09 15:00"""

RUSH_TZ = """/tz
Brend: Coca
Ish turi: reels
Format: 1080x1920
Matn: matnsiz
Materiallar: https://drive.google.com/coca
Deadline: bugun 16:00"""


async def main() -> None:
    conn = tasks.connect(":memory:")
    bot_data = {"db": conn, "config": CONFIG, "tz": None}
    handlers.now_local = lambda context: NOW  # vaqtni qotirib qo'yamiz

    print("\n1. To'liq bo'lmagan TZ rad etiladi")
    update = make(SMM_ALI, "/tz\nBrend: Nestle\nIsh turi: post\nDeadline: tezroq")
    state = await handlers.tz_start(update, FakeContext(bot_data))
    check("TZ qabul qilinmadi", "qabul qilinmadi" in last(update), last(update))
    check("Matn yetishmasligi aytildi", "Matn" in last(update))
    check("Suhbat boshlanmadi", state == ConversationHandler.END)
    check("Bazaga yozilmadi", tasks.get(conn, CHAT_ID, 1) is None)

    print("\n2. Shoshilinch TZ sababsiz o'tmaydi")
    update = make(SMM_DILNOZA, RUSH_TZ)
    await handlers.tz_start(update, FakeContext(bot_data))
    check("Standart muddat eslatildi", "standart muddat" in last(update), last(update))
    update = make(SMM_DILNOZA, RUSH_TZ + "\nSabab: mijoz bugun efirga chiqmoqchi")
    await handlers.tz_start(update, FakeContext(bot_data))
    check("Sabab bilan qabul qilindi", "TZ qabul qilindi" in last(update), last(update))
    rush = tasks.get(conn, CHAT_ID, 1)
    check("Prioritet shoshilinch", rush.priority == tzform.PRIORITY_URGENT, rush.priority)
    check("Sabab saqlandi", "efirga" in rush.reason)

    print("\n3. To'liq TZ qabul qilinadi")
    update = make(SMM_ALI, FULL_TZ)
    await handlers.tz_start(update, FakeContext(bot_data))
    check("Karta chiqdi", "TZ #2" in last(update), last(update))
    planned = tasks.get(conn, CHAT_ID, 2)
    check("Ish turi aniqlandi", planned.work_type == "karusel", planned.work_type)
    check("Ko'p qatorli matn saqlandi", "CTA" in planned.copy_text)

    print("\n4. Navbat deadline bo'yicha tuziladi")
    update = make(SMM_ALI, "/navbat")
    await handlers.queue_command(update, FakeContext(bot_data))
    text = last(update)
    check("Yaqin deadline birinchi", text.index("#1") < text.index("#2"), text)

    print("\n5. Faqat dizayner ishga oladi")
    update = make(SMM_ALI, "/boshladim 1")
    await handlers.take_task(update, FakeContext(bot_data, ["1"]))
    check("SMM ga ruxsat yo'q", "dizaynerlar uchun" in last(update), last(update))
    update = make(DESIGNER, "/boshladim 1")
    await handlers.take_task(update, FakeContext(bot_data, ["1"]))
    check("Dizayner oldi", "ishga olindi" in last(update), last(update))
    check("Holat o'zgardi", tasks.get(conn, CHAT_ID, 1).status == tasks.STATUS_IN_PROGRESS)

    print("\n6. WIP limit ushlab turadi")
    update = make(DESIGNER, "/boshladim 2")
    await handlers.take_task(update, FakeContext(bot_data, ["2"]))
    check("Ikkinchisi ochildi", "ishga olindi" in last(update), last(update))
    update = make(SMM_ALI, FULL_TZ.replace("18-09", "19-09"))
    await handlers.tz_start(update, FakeContext(bot_data))
    update = make(DESIGNER, "/boshladim 3")
    await handlers.take_task(update, FakeContext(bot_data, ["3"]))
    check("Uchinchisi to'xtatildi", "ortiq ish boshlab bo'lmaydi" in last(update), last(update))

    print("\n7. Yopish va kechikishni hisoblash")
    handlers.now_local = lambda context: NOW + timedelta(hours=8)  # 18:00, deadline 16:00 edi
    update = make(DESIGNER, "/tayyor 1")
    await handlers.finish_task(update, FakeContext(bot_data, ["1"]))
    check("Kechikish ko'rsatildi", "kechikib" in last(update), last(update))
    check("Holat tayyor", tasks.get(conn, CHAT_ID, 1).status == tasks.STATUS_DONE)
    update = make(DESIGNER, "/tayyor 1")
    await handlers.finish_task(update, FakeContext(bot_data, ["1"]))
    check("Ikki marta yopilmaydi", "Tayyor" in last(update), last(update))
    handlers.now_local = lambda context: NOW

    print("\n8. Bekor qilish huquqi")
    update = make(SMM_DILNOZA, "/bekor 2")
    await handlers.cancel_task(update, FakeContext(bot_data, ["2"]))
    check("Begona bekor qila olmaydi", "faqat uni bergan" in last(update), last(update))
    update = make(SMM_ALI, "/bekor 2")
    await handlers.cancel_task(update, FakeContext(bot_data, ["2"]))
    check("Muallif bekor qildi", "bekor qilindi" in last(update), last(update))

    print("\n9. Noto'g'ri raqam va yo'q TZ")
    update = make(DESIGNER, "/boshladim")
    await handlers.take_task(update, FakeContext(bot_data, []))
    check("Raqam so'raldi", "raqamini ko'rsating" in last(update), last(update))
    update = make(DESIGNER, "/boshladim 99")
    await handlers.take_task(update, FakeContext(bot_data, ["99"]))
    check("Yo'q TZ aytildi", "topilmadi" in last(update), last(update))

    print("\n10. Shaxsiy chatda ishlamaydi")
    update = make(SMM_ALI, "/navbat")
    update.effective_chat.type = ChatType.PRIVATE
    await handlers.queue_command(update, FakeContext(bot_data))
    check("Guruh talab qilindi", "ish guruhida" in last(update), last(update))

    print("\n11. Savol-javob oqimi")
    context = FakeContext(bot_data)
    update = make(SMM_ALI, "/tz")
    state = await handlers.tz_start(update, context)
    check("Brend so'raldi", state == handlers.ASK_BRAND)
    update = make(SMM_ALI, "yo'q")
    state = await handlers.ask_brand(update, context)
    check("Bo'sh javob rad etildi", state == handlers.ASK_BRAND and "yetarli emas" in last(update))
    update = make(SMM_ALI, "Artel")
    state = await handlers.ask_brand(update, context)
    check("Brend qabul qilindi", state == handlers.ASK_TYPE)
    context.user_data["tz"].update({"work_type": "video", "fmt": "1080x1920",
                                    "copy_text": "matnsiz", "materials": "drive havola",
                                    "reference": "yo'q"})
    update = make(SMM_ALI, "bugun 13:00")
    state = await handlers.ask_deadline(update, context)
    check("Shoshilinch uchun sabab so'raldi", state == handlers.ASK_REASON, last(update))
    update = make(SMM_ALI, "yo'q")
    state = await handlers.ask_reason(update, context)
    check("Quruq sabab rad etildi", state == handlers.ASK_REASON, last(update))
    update = make(SMM_ALI, "Mijoz bugun tender topshiradi")
    state = await handlers.ask_reason(update, context)
    check("TZ yakunlandi", state == ConversationHandler.END and "qabul qilindi" in last(update),
          last(update))

    print("\n12. Hisobot va qoidalar")
    update = make(SMM_ALI, "/hisobot")
    await handlers.report(update, FakeContext(bot_data))
    check("Hisobot tuzildi", "Jami TZ" in last(update), last(update))
    check("Shoshilinchlar sanaldi", "Shoshilinch" in last(update))
    update = make(SMM_ALI, "/qoida")
    await handlers.rules(update, FakeContext(bot_data))
    check("Qoidalar chiqdi", "Navbat" in last(update))
    update = make(SMM_ALI, "/shablon")
    await handlers.template(update, FakeContext(bot_data))
    check("Shablon chiqdi", "Deadline" in last(update))

    print(f"\n{'=' * 50}\nHammasi o'tdi: {PASSED} ta tekshiruv ✅\n")


if __name__ == "__main__":
    asyncio.run(main())
