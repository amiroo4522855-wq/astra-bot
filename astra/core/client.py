"""کلاینت رسمی Bot API روبیکا (نسخه ۳) با مدیریت خطا و تلاشِ مجدد.

ساختار درخواست:
    POST https://botapi.rubika.ir/v3/{token}/{method}

همه‌ی متدها در صورت بروز خطا، یک ‎RubikaError‎ پرتاب می‌کنند تا لایه‌ی
بالاتر بتواند پیام کاربرپسند نشان دهد.
"""
from __future__ import annotations

from .utils import no_emoji, no_emoji_deep

import json
import time
from pathlib import Path
from typing import Any, Iterable

import requests

from .. import config

# انواع فایل قابل قبول در requestSendFile
FILE_TYPES = {
    "image": "Image",
    "photo": "Image",
    "video": "Video",
    "audio": "Audio",
    "voice": "Voice",
    "music": "Music",
    "gif": "Gif",
    "file": "File",
    "document": "File",
}


class RubikaError(Exception):
    """خطای سطح API یا شبکه."""

    def __init__(self, message: str, method: str = "", payload: Any = None) -> None:
        super().__init__(message)
        self.method = method
        self.payload = payload


class RubikaClient:
    """کلاینت سبک، سریع و قابل‌اعتماد برای Bot API روبیکا."""

    platform = "rubika"

    def __init__(self, token: str | None = None, timeout: int | None = None,
                 session: requests.Session | None = None) -> None:
        self.token = token or config.BOT_TOKEN
        self.timeout = timeout or config.REQUEST_TIMEOUT
        self.base = f"{config.API_BASE.rstrip('/')}/{self.token}"
        self.session = session or requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"AstraBot/{config.BOT_VERSION}",
        })
        self._offset: str | None = None

    # ------------------------------------------------------------------ #
    # هسته‌ی ارتباط
    # ------------------------------------------------------------------ #
    def call(self, method: str, payload: dict | None = None,
             files: dict | None = None, retry: int | None = None) -> dict:
        """اجرای یک متد و برگرداندن بخش ‎data‎ پاسخ."""
        if not self.token:
            raise RubikaError("توکن ربات تنظیم نشده است (BOT_TOKEN).", method)

        url = f"{self.base}/{method}"
        attempts = (retry if retry is not None else config.MAX_RETRIES) + 1
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                if files:
                    response = self.session.post(url, data=payload, files=files,
                                                 timeout=self.timeout)
                else:
                    response = self.session.post(url, json=payload or {}, timeout=self.timeout)
                return self._parse(response, method)
            except requests.RequestException as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    time.sleep(0.6 * (attempt + 1))
            except json.JSONDecodeError as exc:
                last_error = exc
                break

        raise RubikaError(f"ارتباط با سرور روبیکا برقرار نشد: {last_error}", method, payload)

    @staticmethod
    def _parse(response: requests.Response, method: str) -> dict:
        try:
            body = response.json()
        except ValueError as exc:
            raise RubikaError(
                f"پاسخ نامعتبر از سرور (کد {response.status_code})", method) from exc

        status = str(body.get("status", body.get("ok", ""))).upper()
        if status in {"OK", "TRUE", "SUCCESS"}:
            return body.get("data", body) or {}

        # تلاش برای پیدا کردن پیام خطا در هر شکلی که باشد
        message = (
            body.get("message")
            or (body.get("data") or {}).get("message")
            or body.get("error")
            or body.get("description")
            or f"کد {response.status_code}"
        )
        raise RubikaError(str(message), method, body)

    # ------------------------------------------------------------------ #
    # متدهای پایه
    # ------------------------------------------------------------------ #
    def get_me(self) -> dict:
        return self.call("getMe")

    def send_message(self, chat_id: str, text: str, inline_keypad: dict | None = None,
                     chat_keypad: dict | None = None, chat_keypad_type: str | None = None,
                     reply_to_message_id: str | None = None,
                     disable_notification: bool = False) -> dict:
        text = no_emoji(text or "")
        inline_keypad = no_emoji_deep(inline_keypad)
        chat_keypad = no_emoji_deep(chat_keypad)
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if inline_keypad:
            payload["inline_keypad"] = inline_keypad
        if chat_keypad:
            payload["chat_keypad"] = chat_keypad
            payload["chat_keypad_type"] = chat_keypad_type or "New"
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
        if disable_notification:
            payload["disable_notification"] = True
        return self.call("sendMessage", payload)

    def edit_message_text(self, chat_id: str, message_id: str, text: str,
                          inline_keypad: dict | None = None) -> dict:
        payload: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "text": text}
        if inline_keypad:
            payload["inline_keypad"] = inline_keypad
        return self.call("editMessageText", payload)

    def delete_message(self, chat_id: str, message_id: str) -> dict:
        return self.call("deleteMessage", {"chat_id": chat_id, "message_id": message_id})

    def get_updates(self, offset_id: str | None = None, limit: int | None = None) -> list[dict]:
        payload = {"limit": limit or config.UPDATE_LIMIT}
        if offset_id:
            payload["offset_id"] = offset_id
        data = self.call("getUpdates", payload)
        updates = data.get("updates") or data.get("updates_list") or []
        return [u for u in updates if u]

    def get_chat(self, chat_id: str) -> dict:
        return self.call("getChat", {"chat_id": chat_id})

    def get_chat_administrators(self, chat_id: str) -> list[dict]:
        try:
            data = self.call("getChatAdministrators", {"chat_id": chat_id})
            return data.get("administrators") or data.get("admins") or []
        except RubikaError:
            return []

    # ------------------------------------------------------------------ #
    # فایل‌ها
    # ------------------------------------------------------------------ #
    def request_upload_url(self, file_type: str = "File") -> str:
        file_type = FILE_TYPES.get(str(file_type).lower(), file_type)
        data = self.call("requestSendFile", {"type": file_type})
        return data.get("upload_url") or ""

    def upload_bytes(self, content: bytes, file_name: str = "file.bin",
                     file_type: str = "File") -> str:
        """آپلود محتوای باینری و دریافت ‎file_id‎."""
        upload_url = self.request_upload_url(file_type)
        if not upload_url:
            raise RubikaError("آدرس آپلود دریافت نشد.", "requestSendFile")
        response = self.session.post(
            upload_url,
            files={"file": (file_name, content)},
            timeout=max(self.timeout, 60),
        )
        try:
            body = response.json()
        except ValueError as exc:
            raise RubikaError("پاسخ آپلود نامعتبر بود.", "upload") from exc
        data = body.get("data", body) or {}
        file_id = data.get("file_id") or body.get("file_id") or ""
        if not file_id:
            raise RubikaError("شناسه فایل دریافت نشد.", "upload", body)
        return file_id

    def upload_path(self, path: str | Path, file_type: str = "File") -> str:
        path = Path(path)
        return self.upload_bytes(path.read_bytes(), path.name, file_type)

    def send_file(self, chat_id: str, file_id: str, caption: str = "",
                  file_type: str | None = None, inline_keypad: dict | None = None,
                  reply_to_message_id: str | None = None) -> dict:
        payload: dict[str, Any] = {"chat_id": chat_id, "file_id": file_id}
        if caption:
            payload["text"] = caption
        if file_type:
            payload["type"] = FILE_TYPES.get(str(file_type).lower(), file_type)
        if inline_keypad:
            payload["inline_keypad"] = inline_keypad
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
        return self.call("sendFile", payload)

    def get_file(self, file_id: str) -> str:
        """دریافت لینک دانلود یک فایل."""
        data = self.call("getFile", {"file_id": file_id})
        return (data.get("download_url") or data.get("url")
                or data.get("file", {}).get("download_url") or "")

    def send_media_bytes(self, chat_id: str, content: bytes, file_name: str,
                         file_type: str = "File", caption: str = "",
                         inline_keypad: dict | None = None) -> dict:
        file_id = self.upload_bytes(content, file_name, file_type)
        return self.send_file(chat_id, file_id, caption, file_type, inline_keypad)

    def send_photo_url(self, chat_id: str, url: str, caption: str = "",
                       inline_keypad: dict | None = None) -> dict:
        """دانلود یک تصویر از اینترنت و ارسال آن داخل روبیکا."""
        response = self.session.get(url, timeout=max(self.timeout, 60))
        response.raise_for_status()
        name = url.split("?")[0].rsplit("/", 1)[-1] or "image.jpg"
        return self.send_media_bytes(chat_id, response.content, name, "Image",
                                     caption, inline_keypad)

    def send_sticker(self, chat_id: str, sticker_id: str) -> dict:
        return self.call("sendSticker", {"chat_id": chat_id, "sticker_id": sticker_id})

    def send_location(self, chat_id: str, latitude: float, longitude: float) -> dict:
        return self.call("sendLocation", {"chat_id": chat_id, "latitude": latitude,
                                          "longitude": longitude})

    def send_poll(self, chat_id: str, question: str, options: Iterable[str]) -> dict:
        return self.call("sendPoll", {"chat_id": chat_id, "question": question,
                                      "options": list(options)})

    # ------------------------------------------------------------------ #
    # مدیریت گروه (در صورت پشتیبانی نشدن، خطا به‌صورت نرم مدیریت می‌شود)
    # ------------------------------------------------------------------ #
    def ban_member(self, chat_id: str, member_id: str) -> dict:
        return self.call("banMember", {"chat_id": chat_id, "member_id": member_id})

    def unban_member(self, chat_id: str, member_id: str) -> dict:
        return self.call("unbanMember", {"chat_id": chat_id, "member_id": member_id})

    def set_commands(self, commands: list[dict]) -> dict:
        return self.call("setCommands", {"commands": commands})

    def update_bot_endpoint(self, url: str, endpoint_type: str = "Update") -> dict:
        return self.call("updateBotEndpoint", {"url": url, "type": endpoint_type})


class DryRunClient(RubikaClient):
    """کلاینت تست: هیچ درخواستی نمی‌فرستد و فقط خروجی‌ها را ثبت می‌کند.

    از این کلاس در ‎simulate.py‎ و تست‌ها استفاده می‌شود تا تمام مسیرهای
    ربات بدون نیاز به اینترنت بررسی شوند.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(token=kwargs.pop("token", "TEST"), **kwargs)
        self.sent: list[dict] = []

    def call(self, method: str, payload: dict | None = None, **_: Any) -> dict:
        record = {"method": method, "payload": payload or {}}
        self.sent.append(record)
        if method == "getMe":
            return {"bot": {"username": config.BOT_USERNAME, "name": config.BOT_NAME}}
        return {"message_id": str(10_000 + len(self.sent))}

    def upload_bytes(self, content: bytes, file_name: str = "file.bin",
                     file_type: str = "File") -> str:  # noqa: D102
        return "TEST_FILE_ID"

    def request_upload_url(self, file_type: str = "File") -> str:  # noqa: D102
        return "https://example.test/upload"
