"""Telegram buyruqlari: TZ qabul qilish, navbat, hisobot."""

import html
import logging
import re
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, User
from telegram.constants import ChatType
from telegram.ext import ContextTypes, ConversationHandler

from app import tasks, tzform
from app.config import Config
from app.dateparse import parse_deadline

logger = logging.getLogger(__name__)

(
    ASK_BRAND,
    ASK_TYPE,
    ASK_FORMAT,
    ASK_FORMAT_CUSTOM,
    ASK_COPY,
    ASK_MATERIALS,
    ASK_REFERENCE,
    ASK_DEADLINE,
    ASK_REASON,
) = range(9)

FORMAT_CHOICES = ("1080x1080", "1080x1350", "1080x1920", "1920x1080")

QUEUE_PAGE_SIZE = 25

HELP_TEXT = (
    "🎯 <b>TZ va navbat boti</b>\n\n"
    "<b>SMM uchun:</b>\n"
    "/tz — yangi TZ berish (savol-javob tartibida)\n"
    "/shablon — bir xabarda yuboriladigan shablon\n"
    "/mentz — mening ochiq TZ larim\n\n"
    "<b>Dizayner uchun:</b>\n"
    "/boshladim 12 — 12-TZ ni ishga olish\n"
    "/tayyor 12 — 12-TZ ni yopish\n\n"
    "<b>Hamma uchun:</b>\n"
    "/navbat — hozirgi navbat\n"
    "/bekor 12 — TZ ni bekor qilish\n"
    "/hisobot — 7 kunlik statistika\n"
    "/qoida — ishlash qoidalari\n\n"
    "Bot to'liq bo'lmagan TZ ni qabul qilmaydi: brend, ish turi, format, matn, "
    "materiallar va deadline majburiy."
)


def rules_text(config: Config) -> str:
    lines = [
        "📜 <b>SMM ↔ Dizayn ish qoidalari</b>\n",
        "<b>1. TZ faqat bot orqali.</b> Guruhga shunchaki yozilgan «shuni qilib ber» "
        "topshiriq hisoblanmaydi va navbatga tushmaydi.\n",
        "<b>2. To'liq bo'lmagan TZ qabul qilinmaydi.</b> Brend, ish turi, format, matn, "
        "materiallar va deadline — oltitasi ham bo'lishi shart.\n",
        "<b>3. Navbat — deadline bo'yicha.</b> Kim birinchi yozgani emas, muddati yaqini "
        "birinchi bajariladi. Navbat /navbat da hamma uchun ochiq.\n",
        "<b>4. Minimal muddat:</b>",
    ]
    for work in tzform.WORK_TYPES:
        lines.append(f"   • {work.label} — {work.min_hours} soat")
    lines += [
        "\n<b>5. Shoshilinch ish — sabab bilan.</b> Muddat standartdan qisqa bo'lsa, bot "
        "«Sabab» so'raydi. Sabab TZ kartasida ko'rinadi va haftalik hisobotga tushadi.\n",
        f"<b>6. Bir vaqtda {config.wip_limit} ta ish.</b> Dizayner {config.wip_limit} tadan ortiq "
        "ishni parallel boshlay olmaydi — yangisi navbatda kutadi.\n",
        "<b>7. TZ berilgandan keyin o'zgarmaydi.</b> Matn yoki format o'zgarsa — bu yangi TZ, "
        "yangi deadline bilan.\n",
        "<b>8. Har dushanba hisobot.</b> Kim nechta TZ berdi, nechtasi shoshilinch edi, "
        "nechtasi o'z vaqtida topshirildi — hammasi ochiq.",
    ]
    return "\n".join(lines)


# ---- kichik yordamchilar ----

def _config(context: ContextTypes.DEFAULT_TYPE) -> Config:
    return context.bot_data["config"]


def _conn(context: ContextTypes.DEFAULT_TYPE) -> sqlite3.Connection:
    return context.bot_data["db"]


def now_local(context: ContextTypes.DEFAULT_TYPE) -> datetime:
    return datetime.now(context.bot_data["tz"]).replace(tzinfo=None, second=0, microsecond=0)


def esc(text: Optional[str]) -> str:
    return html.escape(text or "")


def mention(name: str, username: Optional[str], user_id: int) -> str:
    if username:
        return f"@{esc(username)}"
    return f'<a href="tg://user?id={user_id}">{esc(name)}</a>'


def _user_mention(user: User) -> str:
    return mention(user.full_name or user.first_name, user.username, user.id)


def is_designer(config: Config, user: User) -> bool:
    """DESIGNER_USERNAMES bo'sh bo'lsa — cheklov yo'q."""
    if not config.designers:
        return True
    return (user.username or "").lower() in config.designers


async def _require_group(update: Update) -> bool:
    if update.effective_chat.type == ChatType.PRIVATE:
        await update.effective_message.reply_text(
            "Bu buyruq faqat ish guruhida ishlaydi. Botni guruhga qo'shing."
        )
        return False
    return True


def _strip_command(text: Optional[str]) -> str:
    """«/tz Brend: ...» dan buyruqning o'zini olib tashlaydi."""
    if not text:
        return ""
    first, _, rest = text.partition("\n")
    head = re.sub(r"^/\w+(?:@\w+)?\s*", "", first).strip()
    return "\n".join(part for part in (head, rest.strip()) if part)


def _number_arg(context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    if not context.args:
        return None
    raw = context.args[0].lstrip("#")
    return int(raw) if raw.isdigit() else None


def clip(text: str, limit: int) -> str:
    """Telegram xabari 4096 belgidan oshmasligi uchun uzun matnni qisqartiradi."""
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rstrip() + " …"


def deadline_phrase(task: tasks.Task, now: datetime) -> str:
    left = (task.deadline_dt - now).total_seconds() / 3600
    stamp = f"{task.deadline_dt:%d.%m %H:%M}"
    if left < 0:
        return f"{stamp} — ⚠️ {tzform.format_hours(-left)} kechikdi"
    return f"{stamp} — {tzform.format_hours(left)} qoldi"


# ---- TZ kartasi ----

def render_card(task: tasks.Task, now: datetime, position: Optional[int] = None) -> str:
    work = tzform.WORK_TYPE_BY_KEY.get(task.work_type)
    label = work.label if work else esc(task.work_type)

    lines = [
        f"<b>TZ #{task.number}</b> · {label}",
        "",
        f"🏷 <b>Brend:</b> {esc(task.brand)}",
        f"📐 <b>Format:</b> {esc(task.fmt)}",
        f"✍️ <b>Matn:</b>\n{esc(clip(task.copy_text, 1500))}",
        f"📎 <b>Materiallar:</b> {esc(clip(task.materials, 500))}",
        f"🔗 <b>Referens:</b> {esc(clip(task.reference, 300))}",
    ]
    if task.note:
        lines.append(f"💬 <b>Izoh:</b> {esc(clip(task.note, 500))}")

    priority = tzform.PRIORITY_LABEL.get(task.priority, task.priority)
    if task.reason:
        priority += f" — {esc(task.reason)}"

    lines += [
        "",
        f"⏰ <b>Deadline:</b> {deadline_phrase(task, now)}",
        f"⚡️ <b>Prioritet:</b> {priority}",
        f"👤 <b>Bergan:</b> {mention(task.author_name, task.author_username, task.author_id)}",
    ]

    status = tasks.STATUS_LABEL.get(task.status, task.status)
    if task.assignee_id:
        status += f" · {mention(task.assignee_name or '', None, task.assignee_id)}"
    if position and task.status == tasks.STATUS_NEW:
        status += f" · navbatda {position}-o'rin"
    lines.append(f"📊 <b>Holat:</b> {status}")

    if task.status == tasks.STATUS_NEW:
        lines.append(f"\nDizayner: /boshladim {task.number}")
    return "\n".join(lines)


def render_queue(queue: list[tasks.Task], now: datetime, title: str = "📋 <b>Navbat</b>") -> str:
    if not queue:
        return f"{title}\n\nNavbat bo'sh. 🎉"

    lines = [f"{title} — {len(queue)} ta ochiq TZ\n"]
    shown, hidden = queue[:QUEUE_PAGE_SIZE], queue[QUEUE_PAGE_SIZE:]
    for index, task in enumerate(shown, start=1):
        marker = "▶️" if task.status == tasks.STATUS_IN_PROGRESS else f"{index}."
        flag = "🔥 " if task.priority == tzform.PRIORITY_URGENT else ""
        late = " ⚠️" if task.deadline_dt < now else ""
        who = mention(task.author_name, task.author_username, task.author_id)
        lines.append(
            f"{marker} {flag}<b>#{task.number}</b> {esc(task.brand)} · {esc(task.fmt)}\n"
            f"    ⏰ {task.deadline_dt:%d.%m %H:%M}{late} · {who}"
        )
    if hidden:
        lines.append(f"\n… va yana {len(hidden)} ta TZ navbatda.")
    return "\n".join(lines)


# ---- oddiy buyruqlar ----

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP_TEXT, parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP_TEXT, parse_mode="HTML")


async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(rules_text(_config(context)), parse_mode="HTML")


async def template(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "📋 Quyidagi shablonni nusxalab, to'ldirib yuboring "
        "(birinchi qatorda /tz bo'lsin):\n\n"
        f"<pre>/tz\n{esc(tzform.TEMPLATE)}</pre>\n"
        "Yoki savol-javob tartibida to'ldirish uchun shunchaki /tz yozing.",
        parse_mode="HTML",
    )


async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_group(update):
        return
    now = now_local(context)
    queue = tasks.list_open(_conn(context), update.effective_chat.id)
    await update.effective_message.reply_text(
        render_queue(queue, now), parse_mode="HTML", disable_web_page_preview=True
    )


async def my_tz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_group(update):
        return
    now = now_local(context)
    user = update.effective_user
    queue = tasks.list_open(_conn(context), update.effective_chat.id)
    mine = [t for t in queue if t.author_id == user.id or t.assignee_id == user.id]
    await update.effective_message.reply_text(
        render_queue(mine, now, title="📌 <b>Sizning ochiq TZ laringiz</b>"),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


# ---- TZ yaratish: bir xabarli shablon ----

async def _save_and_announce(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: tzform.ParsedTZ
) -> None:
    conn = _conn(context)
    now = now_local(context)
    user = update.effective_user
    chat_id = update.effective_chat.id

    task = tasks.create(
        conn,
        chat_id=chat_id,
        author_id=user.id,
        author_name=user.full_name or user.first_name,
        author_username=user.username,
        brand=parsed.brand,
        work_type=parsed.work_type.key,
        fmt=parsed.fmt,
        copy_text=parsed.copy_text,
        materials=parsed.materials,
        reference=parsed.reference,
        note=parsed.note,
        deadline=parsed.deadline,
        priority=parsed.priority,
        reason=parsed.reason,
        created_at=now,
    )

    queue = tasks.list_open(conn, chat_id)
    position = tasks.position_of(queue, task)
    await update.effective_message.reply_text(
        "✅ TZ qabul qilindi va navbatga qo'yildi.\n\n" + render_card(task, now, position),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


def _errors_text(errors: list[str]) -> str:
    listed = "\n".join(f"• {esc(err)}" for err in errors)
    return (
        "❌ <b>TZ qabul qilinmadi.</b> Quyidagilarni to'g'rilang:\n\n"
        f"{listed}\n\n"
        "Shablonni olish uchun /shablon, savol-javob tartibi uchun /tz yozing."
    )


async def tz_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_group(update):
        return ConversationHandler.END

    body = _strip_command(update.effective_message.text)
    if body and tzform.looks_like_template(body):
        parsed, errors = tzform.validate(tzform.parse_template(body), now_local(context))
        if errors:
            await update.effective_message.reply_text(_errors_text(errors), parse_mode="HTML")
        else:
            assert parsed is not None
            await _save_and_announce(update, context, parsed)
        return ConversationHandler.END

    context.user_data["tz"] = {}
    await update.effective_message.reply_text(
        f"{tzform.FIELD_BY_KEY['brand'].question}\n\n"
        "Bekor qilish uchun /cancel. Tezroq usul: /shablon",
        parse_mode="HTML",
    )
    return ASK_BRAND


# ---- TZ yaratish: savol-javob tartibi ----

def _draft(context: ContextTypes.DEFAULT_TYPE) -> dict[str, str]:
    return context.user_data.setdefault("tz", {})


def _needs_reason(draft: dict[str, str], now: datetime) -> bool:
    work_type = tzform.WORK_TYPE_BY_KEY.get(draft.get("work_type", ""))
    deadline = parse_deadline(draft.get("deadline", ""), now)
    if work_type is None or deadline is None or deadline <= now:
        return False
    lead_hours = (deadline - now).total_seconds() / 3600
    is_urgent = tzform.priority_for(work_type, lead_hours) == tzform.PRIORITY_URGENT
    return is_urgent and tzform.is_empty(draft.get("reason", ""))


async def _reject_empty(update: Update, field_key: str) -> None:
    field = tzform.FIELD_BY_KEY[field_key]
    await update.effective_message.reply_text(
        f"❌ Bu javob TZ uchun yetarli emas.\n\n{field.question}\n"
        f"Masalan: <code>{esc(field.example)}</code>",
        parse_mode="HTML",
    )


def _work_type_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(work.label, callback_data=f"wt:{work.key}")
        for work in tzform.WORK_TYPES
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(rows)


def _format_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(value, callback_data=f"fmt:{index}")
        for index, value in enumerate(FORMAT_CHOICES)
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton("✍️ Boshqa o'lcham", callback_data="fmt:custom")])
    return InlineKeyboardMarkup(rows)


async def ask_brand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    value = update.effective_message.text.strip()
    if tzform.is_empty(value):
        await _reject_empty(update, "brand")
        return ASK_BRAND

    _draft(context)["brand"] = value
    await update.effective_message.reply_text(
        tzform.FIELD_BY_KEY["work_type"].question, reply_markup=_work_type_keyboard()
    )
    return ASK_TYPE


async def ask_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    key = query.data.split(":", 1)[1]
    work = tzform.WORK_TYPE_BY_KEY[key]
    _draft(context)["work_type"] = key

    await query.edit_message_text(f"🗂 Ish turi: {work.label}")
    await query.message.reply_text(
        tzform.FIELD_BY_KEY["fmt"].question, reply_markup=_format_keyboard()
    )
    return ASK_FORMAT


async def ask_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]

    if choice == "custom":
        await query.edit_message_text("📐 O'lchamni yozing, masalan: 1200x628 yoki A4")
        return ASK_FORMAT_CUSTOM

    value = FORMAT_CHOICES[int(choice)]
    _draft(context)["fmt"] = value
    await query.edit_message_text(f"📐 Format: {value}")
    await query.message.reply_text(tzform.FIELD_BY_KEY["copy_text"].question)
    return ASK_COPY


async def ask_format_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    value = update.effective_message.text.strip()
    if tzform.is_empty(value):
        await _reject_empty(update, "fmt")
        return ASK_FORMAT_CUSTOM

    _draft(context)["fmt"] = value
    await update.effective_message.reply_text(tzform.FIELD_BY_KEY["copy_text"].question)
    return ASK_COPY


async def ask_copy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    value = update.effective_message.text.strip()
    if tzform.is_empty(value):
        await _reject_empty(update, "copy_text")
        return ASK_COPY

    _draft(context)["copy_text"] = value
    await update.effective_message.reply_text(tzform.FIELD_BY_KEY["materials"].question)
    return ASK_MATERIALS


async def ask_materials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    value = update.effective_message.text.strip()
    if tzform.is_empty(value):
        await _reject_empty(update, "materials")
        return ASK_MATERIALS

    _draft(context)["materials"] = value
    await update.effective_message.reply_text(tzform.FIELD_BY_KEY["reference"].question)
    return ASK_REFERENCE


async def ask_reference(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _draft(context)["reference"] = update.effective_message.text.strip()
    await update.effective_message.reply_text(tzform.FIELD_BY_KEY["deadline"].question)
    return ASK_DEADLINE


async def ask_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    now = now_local(context)
    draft = _draft(context)
    value = update.effective_message.text.strip()
    deadline = parse_deadline(value, now)

    if deadline is None:
        await update.effective_message.reply_text(
            "❌ Vaqtni tushunmadim.\n\n"
            "To'g'ri ko'rinishlar: <code>ertaga 15:00</code>, <code>bugun 18:30</code>, "
            "<code>18-09 12:00</code>",
            parse_mode="HTML",
        )
        return ASK_DEADLINE

    if deadline < now + timedelta(minutes=tzform.MIN_LEAD_MINUTES):
        await update.effective_message.reply_text(
            f"❌ {deadline:%d.%m %H:%M} — bu vaqt o'tib ketgan yoki juda yaqin. "
            "Kamida 15 daqiqa keyingi vaqtni ko'rsating."
        )
        return ASK_DEADLINE

    # Kanonik ko'rinishda saqlaymiz — keyin qayta o'qishda yil adashmasligi uchun
    draft["deadline"] = f"{deadline:%d-%m-%Y %H:%M}"

    if _needs_reason(draft, now):
        work = tzform.WORK_TYPE_BY_KEY[draft["work_type"]]
        lead_hours = (deadline - now).total_seconds() / 3600
        await update.effective_message.reply_text(
            f"⚠️ {work.label} uchun standart muddat — kamida {work.min_hours} soat, "
            f"siz {tzform.format_hours(lead_hours)} berdingiz.\n\n"
            f"{tzform.FIELD_BY_KEY['reason'].question}\n"
            "Boshqa vaqt kiritmoqchi bo'lsangiz — /cancel va qaytadan.",
            parse_mode="HTML",
        )
        return ASK_REASON

    return await _finish(update, context)


async def ask_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    value = update.effective_message.text.strip()
    if tzform.is_empty(value) or len(value) < 5:
        await update.effective_message.reply_text(
            "❌ Sabab aniq yozilishi kerak — u TZ kartasida va haftalik hisobotda ko'rinadi.\n"
            f"Masalan: <code>{esc(tzform.FIELD_BY_KEY['reason'].example)}</code>",
            parse_mode="HTML",
        )
        return ASK_REASON

    _draft(context)["reason"] = value
    return await _finish(update, context)


async def _finish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    now = now_local(context)
    draft = _draft(context)

    # Savollarga javob berish vaqtida muddat qisqarib, ish shoshilinchga aylanishi mumkin
    if _needs_reason(draft, now):
        await update.effective_message.reply_text(
            "⚠️ Javob berish davomida muddat qisqardi va ish shoshilinch bo'lib qoldi.\n"
            f"{tzform.FIELD_BY_KEY['reason'].question}"
        )
        return ASK_REASON

    parsed, errors = tzform.validate(draft, now)
    if errors:
        await update.effective_message.reply_text(_errors_text(errors), parse_mode="HTML")
        context.user_data.pop("tz", None)
        return ConversationHandler.END

    assert parsed is not None
    await _save_and_announce(update, context, parsed)
    context.user_data.pop("tz", None)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("tz", None)
    await update.effective_message.reply_text("Bekor qilindi. Yangi TZ uchun /tz.")
    return ConversationHandler.END


# ---- navbatni boshqarish ----

async def _find_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[tasks.Task]:
    number = _number_arg(context)
    if number is None:
        await update.effective_message.reply_text(
            "TZ raqamini ko'rsating. Masalan: /boshladim 12\nNavbat: /navbat"
        )
        return None

    task = tasks.get(_conn(context), update.effective_chat.id, number)
    if task is None:
        await update.effective_message.reply_text(f"#{number} raqamli TZ topilmadi.")
        return None
    return task


async def take_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_group(update):
        return

    config = _config(context)
    user = update.effective_user
    if not is_designer(config, user):
        await update.effective_message.reply_text("Bu buyruq dizaynerlar uchun.")
        return

    task = await _find_task(update, context)
    if task is None:
        return

    if task.status == tasks.STATUS_IN_PROGRESS:
        await update.effective_message.reply_text(f"#{task.number} allaqachon ishda.")
        return
    if task.status != tasks.STATUS_NEW:
        await update.effective_message.reply_text(
            f"#{task.number} holati: {tasks.STATUS_LABEL[task.status]} — ishga olib bo'lmaydi."
        )
        return

    conn = _conn(context)
    chat_id = update.effective_chat.id
    active = tasks.count_in_progress(conn, chat_id, user.id)
    if active >= config.wip_limit:
        open_now = [
            f"#{t.number} ({t.brand})"
            for t in tasks.list_open(conn, chat_id)
            if t.assignee_id == user.id and t.status == tasks.STATUS_IN_PROGRESS
        ]
        await update.effective_message.reply_text(
            f"⛔️ Bir vaqtda {config.wip_limit} tadan ortiq ish boshlab bo'lmaydi.\n"
            f"Hozir ishda: {', '.join(open_now)}\n"
            "Avval /tayyor bilan yoping.",
        )
        return

    now = now_local(context)
    tasks.take(conn, task.id, user.id, user.full_name or user.first_name, now)
    await update.effective_message.reply_text(
        f"▶️ <b>#{task.number}</b> ({esc(task.brand)}) ishga olindi — {_user_mention(user)}\n"
        f"⏰ {deadline_phrase(task, now)}\n"
        f"TZ bergan: {mention(task.author_name, task.author_username, task.author_id)}",
        parse_mode="HTML",
    )


async def finish_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_group(update):
        return

    config = _config(context)
    user = update.effective_user
    if not is_designer(config, user):
        await update.effective_message.reply_text("Bu buyruq dizaynerlar uchun.")
        return

    task = await _find_task(update, context)
    if task is None:
        return

    if task.status not in tasks.OPEN_STATUSES:
        await update.effective_message.reply_text(
            f"#{task.number} holati: {tasks.STATUS_LABEL[task.status]}."
        )
        return
    if task.assignee_id and task.assignee_id != user.id:
        await update.effective_message.reply_text(
            f"#{task.number} ni {esc(task.assignee_name or 'boshqa dizayner')} olgan."
        )
        return

    now = now_local(context)
    tasks.finish(_conn(context), task.id, now)
    delta = (now - task.deadline_dt).total_seconds() / 3600
    verdict = (
        f"⚠️ {tzform.format_hours(delta)} kechikib topshirildi"
        if delta > 0
        else f"👍 deadline'dan {tzform.format_hours(-delta)} oldin"
    )
    await update.effective_message.reply_text(
        f"✅ <b>#{task.number}</b> ({esc(task.brand)}) tayyor — {verdict}\n"
        f"{mention(task.author_name, task.author_username, task.author_id)}, qabul qiling.",
        parse_mode="HTML",
    )


async def cancel_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_group(update):
        return

    task = await _find_task(update, context)
    if task is None:
        return

    user = update.effective_user
    if task.author_id != user.id and not is_designer(_config(context), user):
        await update.effective_message.reply_text(
            "TZ ni faqat uni bergan xodim yoki dizayner bekor qila oladi."
        )
        return
    if task.status not in tasks.OPEN_STATUSES:
        await update.effective_message.reply_text(
            f"#{task.number} holati: {tasks.STATUS_LABEL[task.status]}."
        )
        return

    tasks.cancel(_conn(context), task.id)
    await update.effective_message.reply_text(
        f"🚫 <b>#{task.number}</b> ({esc(task.brand)}) bekor qilindi.", parse_mode="HTML"
    )


# ---- hisobot ----

def build_report(
    conn: sqlite3.Connection, chat_id: int, start: datetime, end: datetime, title: str
) -> str:
    items = tasks.list_created_between(conn, chat_id, start, end)
    header = f"{title}\n<i>{start:%d.%m} — {end - timedelta(minutes=1):%d.%m}</i>"
    if not items:
        return f"{header}\n\nBu davrda bitta ham TZ berilmagan."

    done = [t for t in items if t.status == tasks.STATUS_DONE]
    late = [t for t in done if t.is_late]
    urgent = [t for t in items if t.priority == tzform.PRIORITY_URGENT]
    still_open = [t for t in items if t.status in tasks.OPEN_STATUSES]
    avg_lead = sum(t.lead_hours for t in items) / len(items)

    lines = [
        header,
        "",
        f"📥 Jami TZ: <b>{len(items)}</b>",
        f"✅ Tayyor: <b>{len(done)}</b>" + (f" (⚠️ {len(late)} tasi kechikkan)" if late else ""),
        f"🔄 Ochiq: <b>{len(still_open)}</b>",
        f"🔥 Shoshilinch: <b>{len(urgent)}</b> ({round(len(urgent) / len(items) * 100)}%)",
        f"⏱ O'rtacha berilgan muddat: <b>{tzform.format_hours(avg_lead)}</b>",
        "",
        "<b>Kim qancha TZ berdi:</b>",
    ]

    by_author: dict[int, list[tasks.Task]] = {}
    for task in items:
        by_author.setdefault(task.author_id, []).append(task)

    for author_tasks in sorted(by_author.values(), key=len, reverse=True):
        first = author_tasks[0]
        who = mention(first.author_name, first.author_username, first.author_id)
        rush = sum(1 for t in author_tasks if t.priority == tzform.PRIORITY_URGENT)
        lead = sum(t.lead_hours for t in author_tasks) / len(author_tasks)
        rush_part = f", 🔥 {rush} ta shoshilinch" if rush else ""
        lines.append(
            f"• {who} — {len(author_tasks)} ta{rush_part}, "
            f"o'rtacha muddat {tzform.format_hours(lead)}"
        )

    return "\n".join(lines)


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_group(update):
        return
    now = now_local(context)
    start = (now - timedelta(days=7)).replace(hour=0, minute=0)
    # Oraliq yuqori chegarasi ochiq, shu sabab ayni damdagi TZ ham kirishi uchun +1 daqiqa
    end = now + timedelta(minutes=1)
    text = build_report(
        _conn(context), update.effective_chat.id, start, end, "📊 <b>So'nggi 7 kun</b>"
    )
    await update.effective_message.reply_text(
        text, parse_mode="HTML", disable_web_page_preview=True
    )
