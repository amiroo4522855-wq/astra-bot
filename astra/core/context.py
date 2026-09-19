"""مدل پیام ورودی و شیء زمینه (Context) که به handlerها داده می‌شود."""
from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable

from .. import config
from ..core.db import Database, humanize_expiry
from ..core.utils import chunk_text, no_emoji, no_emoji_deep
from .client import RubikaClient, RubikaError
from .keyboards import main_menu


# --------------------------------------------------------------------------- #
# پیام ورودی
# --------------------------------------------------------------------------- #
def chat_kind(chat_id: str) -> str:
    """تشخیص نوع چت از روی شناسه‌ی روبیکا."""
    prefix = (chat_id or "")[:1].lower()
    if prefix == "u":
        return "private"
    if prefix == "c":
        return "channel"
    return "group"          # g (گروه) و b (سایر گفتگوها)


@dataclass
class Update:
    """نمایش یکپارچه‌ی پیام جدید یا کلیک روی دکمه."""

    kind: str = "message"           # message | callback
    chat_id: str = ""
    chat_type: str = "private"
    sender_id: str = ""
    message_id: str = ""
    text: str = ""
    button_id: str = ""
    start_id: str = ""
    first_name: str = ""
    username: str = ""
    sender_type: str = ""
    file_id: str = ""
    file_type: str = ""
    file_name: str = ""
    is_forwarded: bool = False
    reply_to: str = ""                # شناسه‌ی پیامی که به آن پاسخ داده شده
    media_kind: str = ""              # photo | document | sticker | voice | video | audio | animation
    callback_query_id: str = ""       # مخصوص تلگرام (پاسخ به callback_query)
    web_app_data: str = ""            # داده‌ی ارسالی از مینی‌اپ (Telegram Web App)
    raw: dict = field(default_factory=dict)

    @property
    def clean_text(self) -> str:
        return (self.text or "").strip()


def _first_key(data: dict, keys: tuple[str, ...], default: Any = "") -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, "", {}, []):
            return value
    return default


def _telegram_chat_kind(chat_type: str) -> str:
    if chat_type == "private":
        return "private"
    if chat_type == "channel":
        return "channel"
    return "group"


def parse_update(raw: dict) -> Update | None:
    """تبدیل بدنه‌ی وب‌هوک/آپدیت (روبیکا یا تلگرام) به شیء ‎Update‎."""
    if not raw:
        return None

    # ---------------- تلگرام ---------------- #
    callback_query = raw.get("callback_query")
    if callback_query:
        message = callback_query.get("message") or {}
        chat = message.get("chat") or {}
        sender = callback_query.get("from") or {}
        chat_id = str(chat.get("id", ""))
        return Update(
            kind="callback",
            chat_id=chat_id,
            chat_type=_telegram_chat_kind(chat.get("type", "private")),
            sender_id=str(sender.get("id", "")),
            message_id=str(message.get("message_id", "")),
            text=str(callback_query.get("data", "") or ""),
            button_id=str(callback_query.get("data", "") or ""),
            first_name=str(sender.get("first_name", "")),
            username=str(sender.get("username", "")),
            callback_query_id=str(callback_query.get("id", "")),
            raw=raw,
        )

    tg_message = raw.get("message") or raw.get("edited_message") or raw.get("channel_post")
    if isinstance(tg_message, dict) and tg_message.get("message_id") is not None:
        chat = tg_message.get("chat") or {}
        sender = tg_message.get("from") or {}
        chat_id = str(chat.get("id", ""))
        file_id = ""
        file_type = ""
        photos = tg_message.get("photo") or []
        if photos:
            file_id = str(photos[-1].get("file_id", ""))
            file_type = "Image"
        document = tg_message.get("document") or tg_message.get("video") or {}
        if document and not file_id:
            file_id = str(document.get("file_id", ""))
            file_type = "File"
        media_kind = ""
        for kind in ("sticker", "voice", "video_note", "video", "animation", "audio"):
            payload = tg_message.get(kind)
            if isinstance(payload, dict) and payload.get("file_id"):
                file_id = str(payload.get("file_id", ""))
                file_type = "Sticker" if kind == "sticker" else "File"
                media_kind = "voice" if kind in ("voice", "video_note") else kind
                break
        if file_type == "Image" and not media_kind:
            media_kind = "photo"
        if file_type == "File" and not media_kind:
            media_kind = "document"
        reply_to = str((tg_message.get("reply_to_message") or {}).get("message_id", ""))
        web_app_raw = (tg_message.get("web_app_data") or {}).get("data", "") or ""
        text = str(tg_message.get("text") or tg_message.get("caption") or "")
        return Update(
            kind="message",
            chat_id=chat_id,
            chat_type=_telegram_chat_kind(chat.get("type", "private")),
            sender_id=str(sender.get("id", "") or chat_id),
            message_id=str(tg_message.get("message_id", "")),
            text=text,
            web_app_data=str(web_app_raw),
            first_name=str(sender.get("first_name", "")),
            username=str(sender.get("username", "")),
            file_id=file_id,
            file_type=file_type,
            media_kind=media_kind,
            reply_to=reply_to,
            is_forwarded=bool(tg_message.get("forward_origin")
                              or tg_message.get("forward_from")),
            raw=raw,
        )

    # حالت ۱: وب‌هوک receiveInlineMessage (کلیک روی دکمه‌ی شیشه‌ای)
    inline = raw.get("inline_message") or raw.get("inlineMessage")
    if inline:
        aux = inline.get("aux_data") or {}
        chat_id = str(inline.get("chat_id", ""))
        return Update(
            kind="callback",
            chat_id=chat_id,
            chat_type=chat_kind(chat_id),
            sender_id=str(inline.get("sender_id", "")),
            message_id=str(inline.get("message_id", "")),
            text=str(inline.get("text", "") or ""),
            button_id=str(aux.get("button_id", "") or ""),
            start_id=str(aux.get("start_id", "") or ""),
            raw=raw,
        )

    # حالت ۲: پیام جدید
    update = raw.get("update", raw) or {}
    if update.get("type") and update.get("type") not in ("NewMessage", "StartedBot",
                                                         "NewBotMessage", "Message"):
        # رویدادهای دیگر (مثل عضویت در گروه) را هم به عنوان پیام ساده می‌گیریم
        if update.get("type") in ("RemovedFromGroup", "AddedToGroup"):
            chat_id = str(_first_key(update, ("chat_id", "object_guid"), ""))
            return Update(kind="system", chat_id=chat_id, chat_type=chat_kind(chat_id),
                          raw=raw, text=update.get("type", ""))
        return None

    message = update.get("new_message") or update.get("message") or update or {}
    if not isinstance(message, dict):
        return None

    chat_id = str(_first_key(update, ("chat_id", "object_guid"), "")
                  or _first_key(message, ("chat_id",), ""))
    aux = message.get("aux_data") or {}
    file_obj = message.get("file") or {}
    if not isinstance(file_obj, dict):
        file_obj = {}

    text = str(_first_key(message, ("text", "caption", "raw_text"), "") or "")
    button_id = str(aux.get("button_id", "") or "")
    sender_id = str(_first_key(message, ("sender_id", "author_id", "from_id"), ""))

    forwarded = bool(_first_key(message, ("is_forwarded", "forwarded"), False)) or \
        bool(message.get("forward_from") or message.get("forwarded_from"))

    return Update(
        kind="callback" if button_id else "message",
        chat_id=chat_id,
        chat_type=_first_key(update, ("chat_type",), chat_kind(chat_id)) or chat_kind(chat_id),
        sender_id=sender_id,
        message_id=str(_first_key(message, ("message_id", "id"), "")),
        text=text,
        button_id=button_id,
        start_id=str(aux.get("start_id", "") or ""),
        sender_type=str(message.get("sender_type", "") or ""),
        first_name=str(_first_key(message, ("first_name",), "")),
        username=str(_first_key(message, ("username",), "")),
        file_id=str(file_obj.get("file_id") or message.get("file_id") or ""),
        file_type=str(file_obj.get("type") or message.get("file_type") or ""),
        file_name=str(file_obj.get("file_name") or message.get("file_name") or ""),
        is_forwarded=forwarded,
        reply_to=str(_first_key(message, ("reply_to_message_id",), "") or ""),
        raw=raw,
    )


# --------------------------------------------------------------------------- #
# زمینه
# --------------------------------------------------------------------------- #
class Context:
    """همه‌ی چیزی که یک handler برای پاسخ‌دادن لازم دارد."""

    def __init__(self, client: RubikaClient, db: Database, update: Update,
                 arg: str = "") -> None:
        self.client = client
        self.db = db
        self.update = update
        self.arg = arg
        self.chat_id = update.chat_id
        self.chat_type = update.chat_type
        self.sender_id = update.sender_id or update.chat_id
        self.text = update.clean_text
        self.message_id = update.message_id
        self.is_private = update.chat_type == "private"
        self.is_group = update.chat_type in ("group", "channel")
        self._vip_until: int | None = None

    # ------------------------------------------------------------------ #
    # کاربر و سطح دسترسی
    # ------------------------------------------------------------------ #
    @property
    def is_admin(self) -> bool:
        return str(self.sender_id) in {str(a) for a in config.ADMIN_IDS}

    @property
    def vip_until(self) -> int:
        if self._vip_until is None:
            self._vip_until = int(self.db.vip_until(self.sender_id))
        return self._vip_until

    @property
    def is_vip(self) -> bool:
        return self.vip_until > int(time.time())

    @property
    def vip_remaining(self) -> str:
        return humanize_expiry(self.vip_until)

    # ------------------------------------------------------------------ #
    # ارسال پیام
    # ------------------------------------------------------------------ #
    def send(self, text: str, keyboard: dict | None = None,
             chat_keypad: dict | None = None, reply_to: str | None = None,
             long: bool = True) -> list[dict]:
        """ارسال پیام؛ در صورت طولانی بودن خودکار تکه‌تکه می‌شود."""
        text = no_emoji(text or "")
        keyboard = no_emoji_deep(keyboard)
        chat_keypad = no_emoji_deep(chat_keypad)
        results = []
        pieces = chunk_text(text) if long else [text]
        for index, piece in enumerate(pieces):
            payload_keyboard = keyboard if (index == len(pieces) - 1) else None
            try:
                results.append(self.client.send_message(
                    chat_id=self.chat_id,
                    text=piece or "—",
                    inline_keypad=payload_keyboard,
                    chat_keypad=chat_keypad if index == 0 else None,
                    chat_keypad_type="New" if chat_keypad else None,
                    reply_to_message_id=reply_to if index == 0 else None,
                ))
            except RubikaError as exc:
                self.log_error("send", exc)
                break
        return results

    def reply(self, text: str, keyboard: dict | None = None) -> list[dict]:
        return self.send(text, keyboard, reply_to=self.message_id or None)

    def edit(self, text: str, keyboard: dict | None = None) -> bool:
        """ویرایش پیام فعلی (برای پاسخ به کلیک روی دکمه‌ها)."""
        text = no_emoji(text or "")
        keyboard = no_emoji_deep(keyboard)
        if not self.message_id:
            self.send(text, keyboard)
            return False
        try:
            self.client.edit_message_text(self.chat_id, self.message_id, text, keyboard)
            return True
        except RubikaError:
            self.send(text, keyboard)
            return False

    def answer(self, text: str, keyboard: dict | None = None) -> None:
        """پاسخ به کلیک: اگر امکان ویرایش نبود، پیام جدید می‌فرستد."""
        if not self.edit(text, keyboard):
            pass

    def delete(self, message_id: str | None = None) -> bool:
        try:
            self.client.delete_message(self.chat_id, message_id or self.message_id)
            return True
        except RubikaError:
            return False

    # ------------------------------------------------------------------ #
    # وضعیت گفتگو
    # ------------------------------------------------------------------ #
    def set_state(self, state: str, data: dict | None = None) -> None:
        self.db.set_state(self.sender_id, state, data)

    def get_state(self) -> tuple[str, dict]:
        return self.db.get_state(self.sender_id)

    def clear_state(self) -> None:
        self.db.clear_state(self.sender_id)

    def push_nav(self, route: str) -> None:
        self.db.push_nav(self.sender_id, route)

    def pop_nav(self) -> str:
        return self.db.pop_nav(self.sender_id)

    # ------------------------------------------------------------------ #
    # آمار و محدودیت‌ها
    # ------------------------------------------------------------------ #
    def track(self, key: str) -> None:
        self.db.bump_usage(key)

    def allow(self, key: str, limit_key: str | None = None) -> bool:
        """بررسی سهمیه‌ی روزانه؛ کاربران VIP نامحدود هستند."""
        limit_key = limit_key or key
        limit = config.FREE_LIMITS.get(limit_key, 0)
        if self.is_vip or limit <= 0:
            return True
        used = self.db.daily_count(self.sender_id, limit_key)
        return used < limit

    def consume(self, key: str, limit_key: str | None = None) -> bool:
        """ثبت مصرف؛ اگر سهمیه تمام شده باشد ‎False‎ برمی‌گرداند."""
        limit_key = limit_key or key
        if not self.allow(key, limit_key):
            return False
        self.db.bump_daily(self.sender_id, limit_key)
        self.db.bump_usage(key)
        return True

    def limit_message(self, limit_key: str) -> str:
        limit = config.FREE_LIMITS.get(limit_key, 0)
        from ..handlers.vip import upgrade_keyboard   # واردات محلی برای جلوگیری از دورِ import
        return (
            "🚧 سهمیه‌ی امروزت تموم شد!\n"
            f"{'─' * 18}\n"
            f"سقف استفاده‌ی رایگان از این بخش: {limit} بار در روز\n"
            "با عضویت ویژه، این محدودیت کلاً برداشته می‌شه ♾"
        ), upgrade_keyboard()

    # ------------------------------------------------------------------ #
    # خطاها
    # ------------------------------------------------------------------ #
    def log_error(self, where: str, exc: BaseException) -> None:
        self.db.log("ERROR", where, f"{type(exc).__name__}: {exc}")

    def log_info(self, where: str, message: str) -> None:
        self.db.log("INFO", where, message)
