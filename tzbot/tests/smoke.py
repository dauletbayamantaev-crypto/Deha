"""Botni Telegram'siz sinash: soxta Update/Bot obyektlari bilan.

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

from app import handlers, render, scheduler, store, tzform  # noqa: E402
from app.config import Config  # noqa: E402

GROUP_ID = -1001234567890
TOPIC_ID = 45
NOW = datetime(2026, 9, 16, 10, 0)

SMM = (1, "Aziz Karimov", "smm_aziz")
DESIGNER = (2, "Dilnoza", "dilnoza")
OUTSIDER = (3, "Begona", "begona")

CONFIG = Config(
    bot_token="test", timezone="Asia/Tashkent", db_path=":memory:",
    digest_hour=9, digest_minute=30, reminder_lead_hours=2, rush_hours=4,
)


# ---- soxta Telegram obyektlari ----

@dataclass
class FakeUser:
    id: int
    full_name: str
    username: Optional[str]
    is_bot: bool = False

    @property
    def first_name(self) -> str:
        return self.full_name.split()[0]


@dataclass
class FakeChat:
    id: int
    type: str
    title: Optional[str] = None


@dataclass
class FakeMessage:
    text: str
    message_thread_id: Optional[int] = None
    is_topic_message: bool = False
    reply_to_message: Any = None
    replies: list[str] = field(default_factory=list)

    async def reply_text(self, text: str, **kwargs: Any) -> "FakeMessage":
        self.replies.append(text)
        return self


@dataclass
class FakeQuery:
    data: str
    message: FakeMessage
    edits: list[str] = field(default_factory=list)

    async def answer(self) -> None:
        pass

    async def edit_message_text(self, text: str, **kwargs: Any) -> None:
        self.edits.append(text)


@dataclass
class SentMessage:
    chat_id: int
    text: str
    kwargs: dict[str, Any]
    message_id: int


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[SentMessage] = []
        self._next_id = 1000

    async def send_message(self, chat_id: int, text: str, **kwargs: Any) -> SentMessage:
        self._next_id += 1
        message = SentMessage(chat_id, text, kwargs, self._next_id)
        self.sent.append(message)
        return message

    def to(self, chat_id: int) -> list[SentMessage]:
        return [m for m in self.sent if m.chat_id == chat_id]


@dataclass
class FakeUpdate:
    effective_chat: FakeChat
    effective_user: FakeUser
    effective_message: FakeMessage
    callback_query: Optional[FakeQuery] = None


class FakeContext:
    def __init__(self, bot: FakeBot, bot_data: dict[str, Any], args: Optional[list[str]] = None,
                 user_data: Optional[dict[str, Any]] = None) -> None:
        self.bot = bot
        self.bot_data = bot_data
        self.args = args or []
        self.user_data = user_data if user_data is not None else {}


def in_group(user: tuple, text: str, thread_id: Optional[int] = None) -> FakeUpdate:
    user_id, name, username = user
    return FakeUpdate(
        effective_chat=FakeChat(GROUP_ID, ChatType.SUPERGROUP, "Deha jamoa"),
        effective_user=FakeUser(user_id, name, username),
        effective_message=FakeMessage(text, thread_id, thread_id is not None),
    )


def in_private(user: tuple, text: str) -> FakeUpdate:
    user_id, name, username = user
    return FakeUpdate(
        effective_chat=FakeChat(user_id, ChatType.PRIVATE),
        effective_user=FakeUser(user_id, name, username),
        effective_message=FakeMessage(text),
    )


def press(update: FakeUpdate, data: str) -> FakeUpdate:
    """Tugma bosilishini taqlid qiladi."""
    query = FakeQuery(data, update.effective_message)
    return FakeUpdate(update.effective_chat, update.effective_user,
                      update.effective_message, query)


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


TEMPLATE_TZ = """/tz
Mijoz: Xazna
Tasnif: Xazna uchun karusel post
Mavzu: Xalqaro o'tkazmalar xazna ilovasidan amalga oshirish qo'llanmasi
Deadline: 20.09.2026 18:00
Dizayner: @dilnoza
Matn:
1. Page
Lorem ipsum

2. Page
Lorem ipsum
Izoh: logotip oq bo'lsin"""


async def main() -> None:
    conn = store.connect(":memory:")
    bot = FakeBot()
    bot_data = {"db": conn, "config": CONFIG, "tz": None}
    handlers.now_local = lambda context: NOW
    scheduler._now = lambda context: NOW

    def ctx(args: Optional[list[str]] = None, user_data: Optional[dict] = None) -> FakeContext:
        return FakeContext(bot, bot_data, args, user_data)

    print("\n1. Foydalanuvchi va guruh eslab qolinadi")
    update = in_private(DESIGNER, "/start")
    await handlers.remember(update, ctx())
    check("Dizayner shaxsiy chati saqlandi", store.find_user(conn, "dilnoza") == (2, 2))
    update = in_group(SMM, "/start")
    await handlers.remember(update, ctx())
    check("Guruh ro'yxatga olindi", store.get_group(conn, GROUP_ID)[1] == "Deha jamoa")
    check("SMM shaxsiy chati hali yo'q", store.find_user(conn, "smm_aziz") == (1, None))
    await handlers.remember(in_private(SMM, "/start"), ctx())
    check("SMM /start bosgach saqlandi", store.find_user(conn, "smm_aziz") == (1, 1))

    print("\n2. Topikni ro'yxatga olish")
    update = in_group(SMM, "/topik Xazna", thread_id=TOPIC_ID)
    await handlers.topic_command(update, ctx())
    check("Topik saqlandi", store.get_topic_name(conn, GROUP_ID, TOPIC_ID) == "Xazna", last(update))
    update = in_group(SMM, "/topik")
    await handlers.topic_command(update, ctx())
    check("Ro'yxat ko'rsatildi", "Xazna" in last(update), last(update))

    print("\n3. Shablon bilan TZ — topik ichida")
    update = in_group(SMM, TEMPLATE_TZ, thread_id=TOPIC_ID)
    state = await handlers.tz_start(update, ctx())
    check("Suhbat tugadi", state == ConversationHandler.END)
    task = store.get_by_code(conn, "ID_160926")
    check("TZ yaratildi", task is not None)
    check("To'g'ri topikka biriktirildi", task.thread_id == TOPIC_ID, str(task.thread_id))
    check("Dizayner biriktirildi", task.designer_list == ["dilnoza"], task.designers)

    posted = [m for m in bot.to(GROUP_ID) if m.kwargs.get("message_thread_id") == TOPIC_ID]
    check("Guruhdagi topikka yuborildi", len(posted) == 1, str(bot.sent))
    body = posted[0].text
    for line in ["ID_160926", "Mijoz:", "Tasnif:", "Mavzu:", "Deadline:", "Dizayner:",
                 "1. Page", "Izoh:", "#xazna", "#karusel"]:
        check(f"Xabarda «{line}» bor", line in body, body)
    check("Muallif ko'rsatildi", "@smm_aziz tomonidan berildi" in body, body)
    check("Deadline formati to'g'ri", "20.09.2026 18:00" in body, body)

    dm = bot.to(2)
    check("Dizaynerga bildirishnoma bordi", len(dm) == 1, str(dm))
    check("Bildirishnomada TZ bor", "ID_160926" in dm[0].text)
    check("Bildirishnomada havola bor", "t.me/c/1234567890/45/" in dm[0].text, dm[0].text)
    check("Muallifga tasdiq berildi", "TZ yuborildi" in last(update), last(update))

    print("\n4. Savol-javob oqimi — shaxsiy chatdan")
    data: dict[str, Any] = {}
    update = in_private(SMM, "/tz")
    state = await handlers.tz_start(update, ctx(user_data=data))
    check("Topik so'raldi", state == handlers.ASK_TOPIC, str(state))
    check("Guruh avtomatik tanlandi", data["tz"]["chat_id"] == GROUP_ID)

    update = press(update, f"top:{TOPIC_ID}")
    state = await handlers.ask_topic(update, ctx(user_data=data))
    check("Mijoz so'raldi", state == handlers.ASK_CLIENT)

    update = in_private(SMM, "Xazna")
    state = await handlers.ask_client(update, ctx(user_data=data))
    check("Tasnif tugmalari chiqdi", state == handlers.ASK_KIND)

    update = press(update, "kind:karusel")
    state = await handlers.ask_kind(update, ctx(user_data=data))
    check("Tasnif avtomatik yig'ildi",
          data["tz"]["tasnif"] == "Xazna uchun karusel post", data["tz"]["tasnif"])
    check("Mavzu so'raldi", state == handlers.ASK_SUBJECT)

    update = in_private(SMM, "Xalqaro o'tkazmalar qo'llanmasi")
    state = await handlers.ask_subject(update, ctx(user_data=data))
    check("Deadline so'raldi", state == handlers.ASK_DEADLINE)

    update = press(update, "dl:tom18")
    state = await handlers.ask_deadline_button(update, ctx(user_data=data))
    check("Deadline tugmadan olindi", data["tz"]["deadline"] == "17-09-2026 18:00",
          data["tz"]["deadline"])
    check("Dizayner so'raldi", state == handlers.ASK_DESIGNERS)

    update = in_private(SMM, "kimdir")
    state = await handlers.ask_designers(update, ctx(user_data=data))
    check("Xato username rad etilmadi (matn ham username bo'la oladi)",
          state == handlers.ASK_BODY)
    data["tz"]["designers"] = "@dilnoza @begona"

    update = in_private(SMM, "1. Page\nLorem\n\n2. Page\nIpsum")
    state = await handlers.ask_body(update, ctx(user_data=data))
    check("Izoh so'raldi", state == handlers.ASK_NOTE)

    before = len(bot.sent)
    update = press(update, "note:skip")
    state = await handlers.ask_note_button(update, ctx(user_data=data))
    check("TZ yakunlandi", state == ConversationHandler.END)
    task2 = store.get_by_code(conn, "ID_160926-2")
    check("Ikkinchi TZ ID si to'g'ri", task2 is not None, "ID_160926-2 topilmadi")
    check("Ikki dizayner saqlandi", task2.designer_list == ["dilnoza", "begona"], task2.designers)
    new_sent = bot.sent[before:]
    check("Guruhga yuborildi", any(m.chat_id == GROUP_ID for m in new_sent))
    check("Ro'yxatdan o'tmaganga ogohlantirish",
          "@begona" in last(update) and "start" in last(update), last(update))

    print("\n5. To'liqsiz TZ rad etiladi")
    update = in_group(SMM, "/tz\nMijoz: Xazna\nDeadline: tezroq", thread_id=TOPIC_ID)
    state = await handlers.tz_start(update, ctx())
    check("Qabul qilinmadi", "qabul qilinmadi" in last(update), last(update))
    for missing in ["Mavzu", "Dizayner", "Matn"]:
        check(f"«{missing}» yetishmasligi aytildi", missing in last(update))

    print("\n6. TZ ni yopish")
    update = in_private(OUTSIDER, "/tayyor ID_160926")
    await handlers.finish_task(update, ctx(["ID_160926"]))
    check("Begona yopa olmadi", "faqat biriktirilgan" in last(update), last(update))
    handlers.now_local = lambda context: datetime(2026, 9, 20, 19, 0)
    update = in_private(DESIGNER, "/tayyor id_160926")
    await handlers.finish_task(update, ctx(["id_160926"]))
    check("Dizayner yopdi (registr farq qilmaydi)", "tayyor" in last(update), last(update))
    check("Kechikish hisoblandi", "kechikib" in last(update), last(update))
    check("Holat yangilandi", store.get_by_code(conn, "ID_160926").status == store.STATUS_DONE)
    echo = [m for m in bot.to(GROUP_ID) if m.text.startswith("✅")]
    check("Guruhga ham yozildi", len(echo) == 1, str(len(echo)))
    check("Javob TZ xabariga ulandi", echo[0].kwargs.get("reply_to_message_id") is not None)
    update = in_private(DESIGNER, "/tayyor ID_160926")
    await handlers.finish_task(update, ctx(["ID_160926"]))
    check("Ikki marta yopilmaydi", "Tayyor" in last(update), last(update))
    handlers.now_local = lambda context: NOW

    print("\n7. Navbat va hisobot")
    update = in_private(DESIGNER, "/navbat")
    await handlers.queue_command(update, ctx())
    check("Dizayner o'z TZ sini ko'rdi", "ID_160926-2" in last(update), last(update))
    update = in_private(OUTSIDER, "/navbat")
    await handlers.queue_command(update, ctx())
    check("Begonada TZ yo'q", "Ochiq TZ yo'q" in last(update), last(update))
    update = in_group(SMM, "/hisobot")
    await handlers.report(update, ctx())
    check("Hisobot tuzildi", "Jami TZ" in last(update), last(update))
    check("Dizayner statistikasi bor", "Dizaynerlar bajardi" in last(update), last(update))

    print("\n8. Eslatmalar topikka boradi")
    scheduler._now = lambda context: datetime(2026, 9, 17, 19, 0)  # ID_160926-2 kechikdi
    before = len(bot.sent)
    await scheduler.send_reminders(FakeContext(bot, bot_data))
    fresh = bot.sent[before:]
    group_ping = [m for m in fresh if m.chat_id == GROUP_ID]
    check("Guruhga eslatma bordi", len(group_ping) == 1, str(fresh))
    check("Eslatma topikka bordi", group_ping[0].kwargs.get("message_thread_id") == TOPIC_ID)
    check("Dizaynerga ham bordi", any(m.chat_id == 2 for m in fresh))
    before = len(bot.sent)
    await scheduler.send_reminders(FakeContext(bot, bot_data))
    check("Takrorlanmaydi", len(bot.sent) == before)

    print("\n9. Namunadagi ko'rinish")
    print("-" * 52)
    sample = render.render_task(store.get_by_code(conn, "ID_160926"), with_hint=True)
    print(sample.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
          .replace("&#x27;", "'"))
    print("-" * 52)

    print(f"\nHammasi o'tdi: {PASSED} ta tekshiruv ✅\n")


if __name__ == "__main__":
    asyncio.run(main())
