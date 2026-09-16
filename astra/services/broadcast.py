"""ارسالِ پیامِ همگانیِ «یک‌باره» به همه‌ی کاربران.

روش کار: فایلی به نام state/broadcast.json در مخزن گذاشته می‌شود.
با بالا آمدنِ ربات، پیام برای همه‌ی کاربرانِ شناخته‌شده فرستاده می‌شود،
فایل حذف و شناسه‌ی پیام در پایگاه‌داده ثبت می‌گردد تا هرگز تکرار نشود.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PENDING = ROOT / "state" / "broadcast.json"
STATE_DIR = ROOT / "state"

SETTING_KEY = "last_broadcast_id"


def pending() -> dict | None:
    """خواندنِ پیامِ در انتظار (در صورت وجود)."""
    try:
        if not PENDING.exists():
            return None
        data = json.loads(PENDING.read_text(encoding="utf-8"))
        return data if data.get("text") else None
    except (OSError, json.JSONDecodeError):
        return None


def _already_sent(db, marker: str) -> bool:
    try:
        return str(db.get_setting(SETTING_KEY) or "") == marker
    except Exception:
        return False


def _mark_sent(db, marker: str) -> None:
    try:
        db.set_setting(SETTING_KEY, marker)
    except Exception:
        pass


def clear() -> None:
    """حذفِ فایلِ در انتظار."""
    try:
        PENDING.unlink()
    except OSError:
        pass


def recipients(db) -> list[str]:
    """شناسه‌ی گفتگوهای خصوصیِ کاربران."""
    try:
        ids = db.all_user_ids()
    except Exception:
        return []
    out = []
    for chat in ids or []:
        chat = str(chat or "").strip()
        if chat and not chat.startswith("-"):          # فقط گفتگوی خصوصی
            out.append(chat)
    return out


def split_markdown(text: str) -> tuple[str, list]:
    """تبدیلِ **متنِ پررنگ** به متنِ ساده + موجودیتِ تلگرام.

    این روش از parse_mode امن‌تر است چون با کاراکترهای خاص خطا نمی‌دهد.
    """
    import re
    def u16(chunk: str) -> int:
        """اندازه بر اساسِ واحدِ UTF-16 (موردِ نیازِ تلگرام)."""
        return len(chunk.encode("utf-16-le")) // 2

    entities, out, pos = [], "", 0
    for part in re.split(r"(\*\*[^*]+\*\*)", text):
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            inner = part[2:-2]
            entities.append({"type": "bold", "offset": pos, "length": u16(inner)})
            out += inner
            pos += u16(inner)
        else:
            out += part
            pos += u16(part)
    return out, entities


def run(db, client, log=print) -> int:
    """ارسالِ پیامِ در انتظار. تعداد ارسال‌های موفق را برمی‌گرداند."""
    data = pending()
    if not data:
        return 0
    marker = str(data.get("id") or data.get("text", "")[:40])
    if _already_sent(db, marker):
        log("▫️ پیام همگانی قبلاً ارسال شده؛ رد می‌شود.")
        clear()
        return 0

    text = str(data.get("text") or "").strip()
    keyboard = data.get("keyboard")
    if not text:
        clear()
        return 0

    chats = recipients(db)
    log(f"📢 ارسالِ پیام همگانی برای {len(chats)} کاربر…")
    sent = 0
    for chat in chats:
        try:
            plain, entities = split_markdown(text)
            try:
                client.send_message(chat_id=chat, text=plain, inline_keypad=keyboard,
                                    entities=entities)
            except TypeError:                 # کلاینت‌های دیگر (روبیکا) موجودیت ندارند
                client.send_message(chat_id=chat, text=text, inline_keypad=keyboard)
            sent += 1
            time.sleep(0.04)                 # رعایتِ محدودیتِ تلگرام (~۳۰ پیام/ثانیه)
        except Exception:
            continue                          # بلاک کرده یا گفتگو نامعتبر است
    _mark_sent(db, marker)
    clear()
    log(f"✅ پیام همگانی برای {sent} کاربر ارسال شد.")
    return sent
