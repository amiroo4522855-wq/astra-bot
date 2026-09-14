"""آداپتور تلگرام: همان ربات آسترا با همان handlerها، روی تلگرام.

این کلاس دقیقاً همان رابطِ ‎RubikaClient‎ را پیاده می‌کند، بنابراین
هیچ‌کدام از handlerها نیازی به تغییر ندارند؛ فقط پلتفرم عوض می‌شود.

تبدیل‌های کلیدی:
    • کیبورد شیشه‌ای روبیکا  →  inline_keyboard تلگرام
    • کیبورد پایین صفحه       →  ReplyKeyboardMarkup
    • شناسه‌ی دکمه (id)      →  callback_data
    • inline_message         →  callback_query
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import requests

from .. import config
from .client import RubikaClient, RubikaError

TELEGRAM_API = "https://api.telegram.org"

# نگاشت نوع فایلِ آسترا → متد تلگرام
SEND_METHODS = {
    "Image": "sendPhoto", "Photo": "sendPhoto",
    "Video": "sendVideo", "Gif": "sendAnimation",
    "Audio": "sendAudio", "Music": "sendAudio",
    "Voice": "sendVoice", "File": "sendDocument", "Document": "sendDocument",
}
FIELD_NAMES = {
    "sendPhoto": "photo", "sendVideo": "video", "sendAnimation": "animation",
    "sendAudio": "audio", "sendVoice": "voice", "sendDocument": "document",
}


# --------------------------------------------------------------------------- #
# تبدیل کیبوردها
# --------------------------------------------------------------------------- #
def to_inline_keyboard(keypad: dict | None) -> dict | None:
    """‎{rows:[{buttons:[{id,type,button_text}]}]}‎ → ‎inline_keyboard‎ تلگرام."""
    if not keypad:
        return None
    rows: list[list[dict]] = []
    for row in keypad.get("rows") or []:
        tg_row: list[dict] = []
        for button in row.get("buttons") or []:
            text = str(button.get("button_text", "") or "").strip()
            if not text:
                continue
            btype = button.get("type")
            if btype == "WebApp" and button.get("url"):
                tg_row.append({"text": text, "web_app": {"url": button["url"]}})
            elif btype == "Link" and button.get("link_url"):
                tg_row.append({"text": text, "url": button["link_url"]})
            else:
                callback = str(button.get("id", ""))[:64]
                tg_row.append({"text": text, "callback_data": callback})
        if tg_row:
            rows.append(tg_row)
    return {"inline_keyboard": rows} if rows else None


def to_reply_keyboard(keypad: dict | None) -> dict | None:
    """کیبورد ثابت پایین صفحه → ‎ReplyKeyboardMarkup‎."""
    if not keypad:
        return None
    rows: list[list[dict]] = []
    for row in keypad.get("rows") or []:
        tg_row = [{"text": str(b.get("button_text", "")).strip()}
                  for b in (row.get("buttons") or []) if b.get("button_text")]
        if tg_row:
            rows.append(tg_row)
    if not rows:
        return None
    return {
        "keyboard": rows,
        "resize_keyboard": bool(keypad.get("resize_keyboard", True)),
        "one_time_keyboard": bool(keypad.get("on_time_keyboard", False)),
    }


class TelegramClient(RubikaClient):
    """کلاینت تلگرام با همان امضای متدهای روبیکا."""

    platform = "telegram"

    def __init__(self, token: str | None = None, timeout: int | None = None,
                 session: requests.Session | None = None) -> None:
        super().__init__(token=token or config.TELEGRAM_BOT_TOKEN,
                         timeout=timeout, session=session)
        self.base = f"{TELEGRAM_API}/bot{self.token}"

    # ------------------------------------------------------------------ #
    def call(self, method: str, payload: dict | None = None,
             files: dict | None = None, retry: int | None = None) -> dict:
        """اجرای متد تلگرام و برگرداندن ‎result‎."""
        if not self.token:
            raise RubikaError("توکن تلگرام تنظیم نشده است (TELEGRAM_BOT_TOKEN).", method)

        url = f"{self.base}/{method}"
        attempts = (retry if retry is not None else config.MAX_RETRIES) + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                if files:
                    response = self.session.post(url, data=payload, files=files,
                                                 timeout=self.timeout)
                else:
                    response = self.session.post(url, json=payload or {},
                                                 timeout=self.timeout)
                body = response.json()
                if body.get("ok"):
                    return body.get("result") or {}
                raise RubikaError(body.get("description") or f"کد {response.status_code}",
                                  method, body)
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    continue
        raise RubikaError(f"ارتباط با تلگرام برقرار نشد: {last_error}", method, payload)

    # ------------------------------------------------------------------ #
    # پیام
    # ------------------------------------------------------------------ #
    def send_message(self, chat_id: str, text: str, inline_keypad: dict | None = None,
                     chat_keypad: dict | None = None, chat_keypad_type: str | None = None,
                     reply_to_message_id: str | None = None,
                     disable_notification: bool = False) -> dict:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        markup = to_inline_keyboard(inline_keypad) or to_reply_keyboard(chat_keypad)
        if markup:
            payload["reply_markup"] = markup
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
        if disable_notification:
            payload["disable_notification"] = True
        return self.call("sendMessage", payload)

    def edit_message_text(self, chat_id: str, message_id: str, text: str,
                          inline_keypad: dict | None = None) -> dict:
        payload: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "text": text}
        markup = to_inline_keyboard(inline_keypad)
        if markup:
            payload["reply_markup"] = markup
        return self.call("editMessageText", payload)

    def delete_message(self, chat_id: str, message_id: str) -> dict:
        return self.call("deleteMessage", {"chat_id": chat_id, "message_id": message_id})

    def answer_callback_query(self, query_id: str, text: str = "") -> dict:
        return self.call("answerCallbackQuery",
                         {"callback_query_id": query_id, "text": text} if text
                         else {"callback_query_id": query_id})

    def get_updates(self, offset_id: str | None = None, limit: int | None = None) -> list[dict]:
        payload: dict[str, Any] = {"limit": limit or config.UPDATE_LIMIT, "timeout": 5}
        if offset_id and str(offset_id).isdigit():
            payload["offset"] = int(offset_id)
        return self.call("getUpdates", payload) or []

    def get_me(self) -> dict:
        info = self.call("getMe") or {}
        return {"bot": {"name": info.get("first_name", ""),
                        "username": info.get("username", "")}}

    def get_chat(self, chat_id: str) -> dict:
        return self.call("getChat", {"chat_id": chat_id})

    def get_chat_administrators(self, chat_id: str) -> list[dict]:
        try:
            result = self.call("getChatAdministrators", {"chat_id": chat_id}) or []
            return [{"member": {"user_id": str(m.get("user", {}).get("id", ""))}}
                    for m in result]
        except RubikaError:
            return []

    # ------------------------------------------------------------------ #
    # فایل‌ها
    # ------------------------------------------------------------------ #
    def upload_bytes(self, content: bytes, file_name: str = "file.bin",
                     file_type: str = "File") -> str:
        """در تلگرام فایل مستقیماً همراه پیام ارسال می‌شود؛
        این متد فقط محتوا را موقت ذخیره و یک شناسه‌ی محلی برمی‌گرداند."""
        temp_dir = Path(config.TEMP_DIR) / "tg"
        temp_dir.mkdir(parents=True, exist_ok=True)
        path = temp_dir / file_name
        path.write_bytes(content)
        return f"local:{path}"

    def upload_path(self, path: str | Path, file_type: str = "File") -> str:
        return f"local:{path}"

    def send_file(self, chat_id: str, file_id: str, caption: str = "",
                  file_type: str | None = None, inline_keypad: dict | None = None,
                  reply_to_message_id: str | None = None) -> dict:
        method = SEND_METHODS.get(str(file_type).title(), "sendDocument")
        field = FIELD_NAMES.get(method, "document")
        payload: dict[str, Any] = {"chat_id": chat_id}
        if caption:
            payload["caption"] = caption[:1024]
        markup = to_inline_keyboard(inline_keypad)
        if markup:
            payload["reply_markup"] = markup
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id

        files = None
        local_path = ""
        if str(file_id).startswith("local:"):
            local_path = str(file_id).split("local:", 1)[1]
            files = {field: (Path(local_path).name, Path(local_path).read_bytes())}
        else:
            payload[field] = file_id

        try:
            return self.call(method, payload, files=files)
        finally:
            if local_path and str(local_path).startswith(str(config.TEMP_DIR)):
                try:
                    Path(local_path).unlink(missing_ok=True)
                except OSError:
                    pass

    def get_file(self, file_id: str) -> str:
        result = self.call("getFile", {"file_id": file_id}) or {}
        path = result.get("file_path") or ""
        return f"{TELEGRAM_API}/file/bot{self.token}/{path}" if path else ""

    def send_sticker(self, chat_id: str, sticker_id: str) -> dict:
        return self.call("sendSticker", {"chat_id": chat_id, "sticker": sticker_id})

    def send_location(self, chat_id: str, latitude: float, longitude: float) -> dict:
        return self.call("sendLocation", {"chat_id": chat_id, "latitude": latitude,
                                          "longitude": longitude})

    def send_poll(self, chat_id: str, question: str, options: Iterable[str]) -> dict:
        return self.call("sendPoll", {"chat_id": chat_id, "question": question,
                                      "options": list(options)})

    def set_commands(self, commands: list[dict]) -> dict:
        return self.call("setMyCommands", {"commands": commands})

    def set_menu_button(self, url: str, text: str = "✨ مینی‌اپ") -> dict:
        return self.call("setChatMenuButton", {"menu_button": {
            "type": "web_app", "text": text, "web_app": {"url": url}}})

    def update_bot_endpoint(self, url: str, endpoint_type: str = "Update") -> dict:
        return self.call("setWebhook", {"url": url})

    def ban_member(self, chat_id: str, member_id: str) -> dict:
        return self.call("banChatMember", {"chat_id": chat_id, "user_id": member_id})

    def unban_member(self, chat_id: str, member_id: str) -> dict:
        return self.call("unbanChatMember", {"chat_id": chat_id, "user_id": member_id,
                                             "only_if_banned": True})

    def request_upload_url(self, file_type: str = "File") -> str:      # تلگرام ندارد
        return ""

    def send_photo_url(self, chat_id: str, url: str, caption: str = "",
                       inline_keypad: dict | None = None) -> dict:
        return self.send_file(chat_id, url, caption, "Image", inline_keypad)


def detect_platform(token: str) -> str:
    """تشخیص پلتفرم از روی قالب توکن."""
    if not token:
        return "rubika"
    head, sep, tail = token.partition(":")
    if sep and head.isdigit() and len(tail) >= 30:
        return "telegram"
    return "rubika"
