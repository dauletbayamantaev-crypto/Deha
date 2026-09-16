"""Telegram buyruqlari. Bot shaxsiy chatda ham, guruhda ham bir xil ishlaydi."""

import logging
import re
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType
from telegram.error import TelegramError
from telegram.ext import ContextTypes, ConversationHandler

from app import render, store, tzform
from app.config import Config
from app.dateparse import parse_deadline

logger = logging.getLogger(__name__)

(
    ASK_GROUP,
    ASK_TOPIC,
    ASK_CLIENT,
    ASK_KIND,
    ASK_KIND_CUSTOM,
    ASK_SUBJECT,
    ASK_DEADLINE,
    ASK_DESIGNERS,
    ASK_BODY,
    ASK_NOTE,
) = range(10)

HELP_TEXT = (
    "🎯 <b>TZ boti</b>\n\n"
    "Bot shaxsiy chatda ham, guruhda ham bir xil ishlaydi.\n\n"
    "<b>SMM menejer uchun:</b>\n"
    "/tz — yangi TZ berish\n"
    "/shablon — bitta xabarda yuboriladigan shablon\n\n"
    "<b>Dizayner uchun:</b>\n"
    "/tayyor ID_160926 — TZ ni yopish\n\n"
    "<b>Hamma uchun:</b>\n"
    "/navbat — ochiq TZ lar\n"
    "/bekor ID_160926 — TZ ni bekor qilish\n"
    "/hisobot — 7 kunlik statistika\n"
    "/topik Nomi — guruhdagi topikni ro'yxatga olish\n\n"
    "⚠️ <b>Muhim:</b> har bir dizayner botga shaxsiy chatda bir marta /start "
    "bosishi kerak — shundagina unga bildirishnoma boradi."
)


# ---- yordamchilar ----

def _config(context: ContextTypes.DEFAULT_TYPE) -> Config:
    return context.bot_data["config"]


def _conn(context: ContextTypes.DEFAULT_TYPE) -> sqlite3.Connection:
    return context.bot_data["db"]


def now_local(context: ContextTypes.DEFAULT_TYPE) -> datetime:
    return datetime.now(context.bot_data["tz"]).replace(tzinfo=None, second=0, microsecond=0)


def _draft(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    return context.user_data.setdefault("tz", {})


def _strip_command(text: Optional[str]) -> str:
    if not text:
        return ""
    first, _, rest = text.partition("\n")
    head = re.sub(r"^/\w+(?:@\w+)?\s*", "", first).strip()
    return "\n".join(part for part in (head, rest.strip()) if part)


async def _reply(update: Update, text: str, **kwargs: Any) -> Any:
    return await update.effective_message.reply_text(
        text, parse_mode="HTML", disable_web_page_preview=True, **kwargs
    )


# ---- foydalanuvchini eslab qolish (har bir xabarda) ----

async def remember(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if user is None or user.is_bot:
        return

    private_chat_id = chat.id if chat and chat.type == ChatType.PRIVATE else None
    store.remember_user(
        _conn(context), user.id, user.username, user.full_name or user.first_name,
        private_chat_id,
    )
    if chat and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        store.remember_group(_conn(context), chat.id, chat.title or "Guruh")


# ---- oddiy buyruqlar ----

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(update, HELP_TEXT)


async def template(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(
        update,
        "📋 Shablonni nusxalab, to'ldirib yuboring (birinchi qatorda /tz bo'lsin):\n\n"
        f"<pre>/tz\n{render.esc(tzform.TEMPLATE)}</pre>\n"
        "Yoki savol-javob tartibida to'ldirish uchun shunchaki /tz yozing.",
    )


async def topic_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guruhdagi topikni ro'yxatga oladi yoki ro'yxatni ko'rsatadi."""
    chat = update.effective_chat
    conn = _conn(context)

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await _reply(update, "Bu buyruq guruhda, topik ichida ishlatiladi.")
        return

    message = update.effective_message
    thread_id = message.message_thread_id if message.is_topic_message else None

    if thread_id is None:
        topics = store.list_topics(conn, chat.id)
        if not topics:
            await _reply(
                update,
                "Hali birorta topik ro'yxatga olinmagan.\n"
                "Har bir topikka kiring va <code>/topik Nomi</code> deb yozing.",
            )
            return
        listed = "\n".join(f"• {render.esc(name)}" for _, name in topics)
        await _reply(update, f"📂 <b>Ro'yxatdagi topiklar:</b>\n{listed}")
        return

    name = _strip_command(message.text)
    if not name:
        created = message.reply_to_message.forum_topic_created if message.reply_to_message else None
        name = created.name if created else ""
    if not name:
        current = store.get_topic_name(conn, chat.id, thread_id)
        hint = f"\nHozirgi nomi: <b>{render.esc(current)}</b>" if current else ""
        await _reply(update, f"Topik nomini yozing: <code>/topik Xazna</code>{hint}")
        return

    store.remember_topic(conn, chat.id, thread_id, name)
    await _reply(
        update,
        f"✅ Topik ro'yxatga olindi: <b>{render.esc(name)}</b>\n"
        "Endi /tz berayotganda shu topikni tanlash mumkin.",
    )


async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = _conn(context)
    chat = update.effective_chat
    now = now_local(context)

    if chat.type == ChatType.PRIVATE:
        tasks = store.list_open_for_user(conn, update.effective_user.id)
        title = "📌 <b>Sizga tegishli ochiq TZ lar</b>"
    else:
        tasks = store.list_open(conn, chat.id)
        title = "📋 <b>Guruhdagi ochiq TZ lar</b>"

    await _reply(update, render.render_queue(tasks, now, title))


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = _conn(context)
    chat = update.effective_chat
    config = _config(context)
    now = now_local(context)

    start_at = (now - timedelta(days=7)).replace(hour=0, minute=0)
    end_at = now + timedelta(minutes=1)
    chat_id = None if chat.type == ChatType.PRIVATE else chat.id
    tasks = store.list_created_between(conn, start_at, end_at, chat_id)

    await _reply(
        update,
        render.render_report(tasks, start_at, now, config.rush_hours, "📊 <b>So'nggi 7 kun</b>"),
    )


# ---- TZ berish ----

def _kind_keyboard() -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(k.label, callback_data=f"kind:{k.key}") for k in tzform.KINDS]
    return InlineKeyboardMarkup([buttons[i:i + 2] for i in range(0, len(buttons), 2)])


def _deadline_keyboard(now: datetime) -> InlineKeyboardMarkup:
    today = now.replace(hour=18, minute=0)
    tomorrow = today + timedelta(days=1)
    rows = []
    if today > now:
        rows.append([InlineKeyboardButton(f"Bugun 18:00", callback_data="dl:today18")])
    rows.append(
        [
            InlineKeyboardButton("Ertaga 12:00", callback_data="dl:tom12"),
            InlineKeyboardButton("Ertaga 18:00", callback_data="dl:tom18"),
        ]
    )
    rows.append([InlineKeyboardButton("✍️ Boshqa vaqt", callback_data="dl:custom")])
    return InlineKeyboardMarkup(rows)


def _note_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Izohsiz", callback_data="note:skip")]])


async def tz_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    conn = _conn(context)
    chat = update.effective_chat
    message = update.effective_message

    context.user_data["tz"] = {}
    draft = _draft(context)

    # Bitta xabarda yuborilgan shablon
    body = _strip_command(message.text)
    if body and tzform.looks_like_template(body):
        parsed, errors = tzform.validate(tzform.parse_template(body), now_local(context))
        if errors:
            await _reply(update, _errors_text(errors))
            return ConversationHandler.END
        assert parsed is not None
        draft["parsed"] = parsed
        return await _choose_destination(update, context, after_template=True)

    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        draft["chat_id"] = chat.id
        if message.is_topic_message and message.message_thread_id:
            draft["thread_id"] = message.message_thread_id
            return await _ask_client(update, context)
        return await _ask_topic(update, context, chat.id)

    groups = store.list_groups(conn)
    if not groups:
        await _reply(
            update,
            "❌ Bot hali birorta guruhga qo'shilmagan.\n"
            "Botni ish guruhingizga qo'shing va o'sha yerda /start yozing.",
        )
        return ConversationHandler.END
    if len(groups) == 1:
        draft["chat_id"] = groups[0][0]
        return await _ask_topic(update, context, groups[0][0])

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(title, callback_data=f"grp:{chat_id}")] for chat_id, title in groups]
    )
    await _reply(update, "📍 TZ qaysi guruhga yuborilsin?", reply_markup=keyboard)
    return ASK_GROUP


async def ask_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":", 1)[1])
    _draft(context)["chat_id"] = chat_id

    group = store.get_group(_conn(context), chat_id)
    await query.edit_message_text(f"📍 Guruh: {group[1] if group else chat_id}")
    return await _ask_topic(update, context, chat_id)


async def _ask_topic(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> int:
    topics = store.list_topics(_conn(context), chat_id)
    if not topics:
        _draft(context)["thread_id"] = None
        return await _ask_client(update, context)

    rows = [
        [InlineKeyboardButton(name, callback_data=f"top:{thread_id}")]
        for thread_id, name in topics
    ]
    rows.append([InlineKeyboardButton("📢 Umumiy (topiksiz)", callback_data="top:0")])
    await _reply(update, "📂 Qaysi topikka yuborilsin?", reply_markup=InlineKeyboardMarkup(rows))
    return ASK_TOPIC


async def ask_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    thread_id = int(query.data.split(":", 1)[1])
    draft = _draft(context)
    draft["thread_id"] = thread_id or None

    name = store.get_topic_name(_conn(context), draft["chat_id"], thread_id) if thread_id else None
    await query.edit_message_text(f"📂 Topik: {name or 'Umumiy'}")

    if draft.get("parsed") is not None:
        return await _publish(update, context)
    return await _ask_client(update, context)


async def _choose_destination(
    update: Update, context: ContextTypes.DEFAULT_TYPE, after_template: bool
) -> int:
    """Shablon orqali kelgan TZ uchun guruh/topikni aniqlaydi."""
    chat = update.effective_chat
    message = update.effective_message
    draft = _draft(context)
    conn = _conn(context)

    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        draft["chat_id"] = chat.id
        if message.is_topic_message and message.message_thread_id:
            draft["thread_id"] = message.message_thread_id
            return await _publish(update, context)
        return await _ask_topic(update, context, chat.id)

    groups = store.list_groups(conn)
    if not groups:
        await _reply(update, "❌ Bot hali birorta guruhga qo'shilmagan.")
        return ConversationHandler.END
    if len(groups) == 1:
        draft["chat_id"] = groups[0][0]
        return await _ask_topic(update, context, groups[0][0])

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(title, callback_data=f"grp:{chat_id}")] for chat_id, title in groups]
    )
    await _reply(update, "📍 TZ qaysi guruhga yuborilsin?", reply_markup=keyboard)
    return ASK_GROUP


async def _ask_client(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _reply(
        update,
        f"{tzform.FIELD_BY_KEY['client'].question}\n\n<i>Bekor qilish: /cancel</i>",
    )
    return ASK_CLIENT


async def _reject(update: Update, field_key: str) -> None:
    field = tzform.FIELD_BY_KEY[field_key]
    await _reply(
        update,
        f"❌ Bu javob TZ uchun yetarli emas.\n\n{field.question}\n"
        f"Masalan: <code>{render.esc(field.example)}</code>",
    )


async def ask_client(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    value = update.effective_message.text.strip()
    if tzform.is_empty(value):
        await _reject(update, "client")
        return ASK_CLIENT

    _draft(context)["client"] = value
    await _reply(update, tzform.FIELD_BY_KEY["tasnif"].question, reply_markup=_kind_keyboard())
    return ASK_KIND


async def ask_kind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    key = query.data.split(":", 1)[1]
    kind = tzform.KIND_BY_KEY[key]
    draft = _draft(context)

    if key == "boshqa":
        await query.edit_message_text("🗂 Ish turini qisqa yozing, masalan: sertifikat maketi")
        return ASK_KIND_CUSTOM

    draft["kind"] = key
    draft["tasnif"] = tzform.build_tasnif(draft["client"], kind.label)
    await query.edit_message_text(f"🗂 Tasnif: {draft['tasnif']}")
    await _reply(update, tzform.FIELD_BY_KEY["subject"].question)
    return ASK_SUBJECT


async def ask_kind_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    value = update.effective_message.text.strip()
    if tzform.is_empty(value):
        await _reject(update, "tasnif")
        return ASK_KIND_CUSTOM

    draft = _draft(context)
    draft["kind"] = tzform.parse_kind(value).key
    draft["tasnif"] = tzform.build_tasnif(draft["client"], value)
    await _reply(update, tzform.FIELD_BY_KEY["subject"].question)
    return ASK_SUBJECT


async def ask_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    value = update.effective_message.text.strip()
    if tzform.is_empty(value):
        await _reject(update, "subject")
        return ASK_SUBJECT

    _draft(context)["subject"] = value
    await _reply(
        update,
        tzform.FIELD_BY_KEY["deadline"].question + "\n"
        "<i>Tugmani bosing yoki o'zingiz yozing: 20.09.2026 18:00</i>",
        reply_markup=_deadline_keyboard(now_local(context)),
    )
    return ASK_DEADLINE


def _store_deadline(context: ContextTypes.DEFAULT_TYPE, deadline: datetime) -> None:
    _draft(context)["deadline"] = f"{deadline:%d-%m-%Y %H:%M}"


async def ask_deadline_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]
    now = now_local(context)

    if choice == "custom":
        await query.edit_message_text(
            "⏰ Deadline'ni yozing: 20.09.2026 18:00 / ertaga 15:00 / bugun 18:30"
        )
        return ASK_DEADLINE

    presets = {
        "today18": now.replace(hour=18, minute=0),
        "tom12": (now + timedelta(days=1)).replace(hour=12, minute=0),
        "tom18": (now + timedelta(days=1)).replace(hour=18, minute=0),
    }
    deadline = presets[choice]
    _store_deadline(context, deadline)
    await query.edit_message_text(f"⏰ Deadline: {deadline:%d.%m.%Y %H:%M}")
    await _reply(update, tzform.FIELD_BY_KEY["designers"].question)
    return ASK_DESIGNERS


async def ask_deadline_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    now = now_local(context)
    value = update.effective_message.text.strip()
    deadline = parse_deadline(value, now)

    if deadline is None:
        await _reply(
            update,
            "❌ Vaqtni tushunmadim.\n\nTo'g'ri ko'rinishlar: <code>20.09.2026 18:00</code>, "
            "<code>ertaga 15:00</code>, <code>bugun 18:30</code>",
        )
        return ASK_DEADLINE
    if deadline < now + timedelta(minutes=tzform.MIN_LEAD_MINUTES):
        await _reply(
            update,
            f"❌ {deadline:%d.%m.%Y %H:%M} — bu vaqt o'tib ketgan yoki juda yaqin.",
        )
        return ASK_DEADLINE

    _store_deadline(context, deadline)
    await _reply(update, tzform.FIELD_BY_KEY["designers"].question)
    return ASK_DESIGNERS


async def ask_designers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    value = update.effective_message.text.strip()
    names = tzform.parse_usernames(value)
    if not names:
        await _reject(update, "designers")
        return ASK_DESIGNERS

    _draft(context)["designers"] = " ".join(f"@{name}" for name in names)
    await _reply(update, tzform.FIELD_BY_KEY["body"].question)
    return ASK_BODY


async def ask_body(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    value = update.effective_message.text.strip()
    if tzform.is_empty(value):
        await _reject(update, "body")
        return ASK_BODY

    _draft(context)["body"] = value
    await _reply(update, tzform.FIELD_BY_KEY["note"].question, reply_markup=_note_keyboard())
    return ASK_NOTE


async def ask_note_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    _draft(context)["note"] = ""
    await query.edit_message_text("💬 Izohsiz")
    return await _publish(update, context)


async def ask_note_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    value = update.effective_message.text.strip()
    _draft(context)["note"] = "" if tzform.is_empty(value) else value
    return await _publish(update, context)


def _errors_text(errors: list[str]) -> str:
    listed = "\n".join(f"• {render.esc(err)}" for err in errors)
    return (
        "❌ <b>TZ qabul qilinmadi.</b> Quyidagilarni to'g'rilang:\n\n"
        f"{listed}\n\n"
        "Shablon: /shablon · Savol-javob: /tz"
    )


async def _publish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """TZ ni bazaga yozadi, guruhga yuboradi va dizaynerlarga xabar beradi."""
    conn = _conn(context)
    now = now_local(context)
    draft = _draft(context)
    user = update.effective_user

    parsed: Optional[tzform.ParsedTZ] = draft.get("parsed")
    if parsed is None:
        values = {
            "client": draft.get("client", ""),
            "tasnif": draft.get("tasnif", ""),
            "subject": draft.get("subject", ""),
            "deadline": draft.get("deadline", ""),
            "designers": draft.get("designers", ""),
            "body": draft.get("body", ""),
            "note": draft.get("note", ""),
        }
        parsed, errors = tzform.validate(values, now)
        if errors:
            await _reply(update, _errors_text(errors))
            context.user_data.pop("tz", None)
            return ConversationHandler.END
    assert parsed is not None

    designer_ids: list[int] = []
    unknown: list[str] = []
    targets: list[tuple[str, int]] = []  # (username, private_chat_id)
    for name in parsed.designers:
        found = store.find_user(conn, name)
        if found is None or found[1] is None:
            unknown.append(name)
            if found:
                designer_ids.append(found[0])
            continue
        designer_ids.append(found[0])
        targets.append((name, found[1]))

    task = store.create_task(
        conn,
        code=store.next_code(conn, now),
        chat_id=draft["chat_id"],
        thread_id=draft.get("thread_id"),
        author_id=user.id,
        author_name=user.full_name or user.first_name,
        author_username=user.username,
        designers=parsed.designers,
        designer_ids=designer_ids,
        client=parsed.client,
        kind=parsed.kind.key,
        tasnif=parsed.tasnif,
        subject=parsed.subject,
        body=parsed.body,
        note=parsed.note,
        deadline=parsed.deadline,
        created_at=now,
    )

    sent = await _send_to_group(context, task)
    group = store.get_group(conn, task.chat_id)
    group_title = group[1] if group else "Guruh"
    link = render.message_link(task.chat_id, sent, task.thread_id) if sent else None

    delivered = await _notify_designers(context, task, targets, group_title, link)

    summary = [f"✅ TZ yuborildi: <b>{render.esc(task.code)}</b> → {render.esc(group_title)}"]
    if link:
        summary.append(f'<a href="{link}">Guruhdagi xabarni ochish</a>')
    if delivered:
        summary.append("🔔 Bildirishnoma yuborildi: " + " ".join(f"@{n}" for n in delivered))
    if unknown:
        summary.append(
            "⚠️ Bularga shaxsiy bildirishnoma bormadi: "
            + " ".join(f"@{render.esc(n)}" for n in unknown)
            + "\nUlar botga /start bosishi kerak (guruhda baribir eslatildi)."
        )

    await _reply(update, "\n".join(summary))
    context.user_data.pop("tz", None)
    return ConversationHandler.END


async def _send_to_group(context: ContextTypes.DEFAULT_TYPE, task: store.Task) -> Optional[int]:
    kwargs: dict[str, Any] = {}
    if task.thread_id:
        kwargs["message_thread_id"] = task.thread_id
    try:
        message = await context.bot.send_message(
            chat_id=task.chat_id,
            text=render.render_task(task),
            parse_mode="HTML",
            disable_web_page_preview=True,
            **kwargs,
        )
    except TelegramError:
        logger.exception("TZ %s ni %s guruhiga yuborib bo'lmadi.", task.code, task.chat_id)
        return None

    store.set_message_id(_conn(context), task.id, message.message_id)
    return message.message_id


async def _notify_designers(
    context: ContextTypes.DEFAULT_TYPE,
    task: store.Task,
    targets: list[tuple[str, int]],
    group_title: str,
    link: Optional[str],
) -> list[str]:
    delivered: list[str] = []
    for name, private_chat_id in targets:
        try:
            await context.bot.send_message(
                chat_id=private_chat_id,
                text=render.render_notification(task, group_title, link),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            delivered.append(name)
        except TelegramError:
            logger.warning("@%s ga bildirishnoma yuborilmadi.", name)
    return delivered


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("tz", None)
    await _reply(update, "Bekor qilindi. Yangi TZ uchun /tz.")
    return ConversationHandler.END


# ---- TZ ni yopish va bekor qilish ----

def _code_arg(context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
    return context.args[0].strip() if context.args else None


async def _find_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[store.Task]:
    code = _code_arg(context)
    if not code:
        await _reply(
            update,
            "TZ raqamini ko'rsating. Masalan: <code>/tayyor ID_160926</code>\nRo'yxat: /navbat",
        )
        return None

    task = store.get_by_code(_conn(context), code)
    if task is None:
        await _reply(update, f"<b>{render.esc(code)}</b> topilmadi. Ro'yxat: /navbat")
        return None
    return task


def _may_close(task: store.Task, user_id: int, username: Optional[str]) -> bool:
    if user_id == task.author_id or user_id in task.designer_id_list:
        return True
    return (username or "").lower() in task.designer_list


async def finish_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    task = await _find_task(update, context)
    if task is None:
        return

    user = update.effective_user
    if not _may_close(task, user.id, user.username):
        await _reply(update, "Bu TZ ni faqat biriktirilgan dizayner yoki uni bergan xodim yopadi.")
        return
    if task.status != store.STATUS_NEW:
        await _reply(update, f"{task.code} holati: {store.STATUS_LABEL[task.status]}.")
        return

    now = now_local(context)
    store.finish(_conn(context), task.id, now)
    delta = (now - task.deadline_dt).total_seconds() / 3600
    verdict = (
        f"⚠️ {tzform.format_hours(delta)} kechikib topshirildi"
        if delta > 0
        else f"👍 deadline'dan {tzform.format_hours(-delta)} oldin"
    )
    text = (
        f"✅ <b>{render.esc(task.code)}</b> ({render.esc(task.client)}) tayyor — {verdict}\n"
        f"Dizayner: @{render.esc(user.username) if user.username else render.esc(user.full_name)}"
    )

    await _reply(update, text)
    await _echo_to_group(context, task, text, skip_chat_id=update.effective_chat.id)
    await _notify_author(context, task, text)


async def cancel_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    task = await _find_task(update, context)
    if task is None:
        return

    user = update.effective_user
    if not _may_close(task, user.id, user.username):
        await _reply(update, "TZ ni faqat uni bergan xodim yoki biriktirilgan dizayner bekor qiladi.")
        return
    if task.status != store.STATUS_NEW:
        await _reply(update, f"{task.code} holati: {store.STATUS_LABEL[task.status]}.")
        return

    store.cancel(_conn(context), task.id)
    text = f"🚫 <b>{render.esc(task.code)}</b> ({render.esc(task.client)}) bekor qilindi."
    await _reply(update, text)
    await _echo_to_group(context, task, text, skip_chat_id=update.effective_chat.id)


async def _echo_to_group(
    context: ContextTypes.DEFAULT_TYPE, task: store.Task, text: str, skip_chat_id: int
) -> None:
    """Holat o'zgarganini TZ turgan topikka yozadi."""
    if task.chat_id == skip_chat_id:
        return

    kwargs: dict[str, Any] = {}
    if task.thread_id:
        kwargs["message_thread_id"] = task.thread_id
    if task.message_id:
        kwargs["reply_to_message_id"] = task.message_id
    try:
        await context.bot.send_message(
            chat_id=task.chat_id, text=text, parse_mode="HTML", **kwargs
        )
    except TelegramError:
        kwargs.pop("reply_to_message_id", None)
        try:
            await context.bot.send_message(
                chat_id=task.chat_id, text=text, parse_mode="HTML", **kwargs
            )
        except TelegramError:
            logger.warning("Guruhga holat xabari yuborilmadi: %s", task.code)


async def _notify_author(
    context: ContextTypes.DEFAULT_TYPE, task: store.Task, text: str
) -> None:
    found = store.find_user(_conn(context), task.author_username or "")
    private_chat_id = found[1] if found else None
    if not private_chat_id:
        return
    try:
        await context.bot.send_message(
            chat_id=private_chat_id, text=text, parse_mode="HTML"
        )
    except TelegramError:
        logger.warning("Muallifga xabar yuborilmadi: %s", task.code)
