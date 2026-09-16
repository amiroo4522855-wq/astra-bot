"""ساخت کیبوردهای شیشه‌ای (Inline) و کیبورد پایین صفحه (Chat Keypad).

قانون طراحی آسترا:
    • هر ردیف حداکثر ۲ یا ۳ دکمه (مرتب و خوانا)
    • ردیف آخر همیشه شامل «بازگشت» و «منوی اصلی» است
    • شناسه‌ی دکمه‌ها کوتاه و معنادار (مثل ‎music:search‎)
"""
from __future__ import annotations

from typing import Iterable, Sequence

from ..config import BOT_NAME

# --------------------------------------------------------------------------- #
# ابزارهای پایه
# --------------------------------------------------------------------------- #
def btn(text: str, callback: str) -> dict:
    """یک دکمه‌ی ساده‌ی شیشه‌ای."""
    return {"id": callback, "type": "Simple", "button_text": text}


def url_btn(text: str, url: str) -> dict:
    return {"id": url[:64], "type": "Link", "button_text": text, "link_url": url}


def web_app_btn(text: str, url: str, callback: str = "app:open") -> dict:
    return {"id": callback, "type": "WebApp", "button_text": text, "url": url}


class InlineKeyboard:
    """سازنده‌ی کیبورد شیشه‌ای با چیدمان خودکار."""

    def __init__(self) -> None:
        self.rows: list[list[dict]] = []

    def row(self, *buttons: dict) -> "InlineKeyboard":
        buttons = [b for b in buttons if b]
        if buttons:
            self.rows.append(list(buttons))
        return self

    def add(self, text: str, callback: str) -> "InlineKeyboard":
        return self.row(btn(text, callback))

    def grid(self, items: Sequence[tuple[str, str]], per_row: int = 2) -> "InlineKeyboard":
        """چیدن خودکار دکمه‌ها در ستون‌های ۲ یا ۳ تایی."""
        per_row = max(1, min(3, per_row))
        row: list[dict] = []
        for text, callback in items:
            row.append(btn(text, callback))
            if len(row) == per_row:
                self.rows.append(row)
                row = []
        if row:
            self.rows.append(row)
        return self

    def extend(self, items: Iterable[tuple[str, str]], per_row: int = 2) -> "InlineKeyboard":
        return self.grid(list(items), per_row)

    def nav(self, back: str | None = "nav:back", home: bool = True) -> "InlineKeyboard":
        """ردیف ناوبری استاندارد انتهای هر منو."""
        row: list[dict] = []
        if home:
            row.append(btn("🏠 منوی اصلی", "nav:home"))
        if back:
            row.append(btn("🔙 بازگشت", back))
        if row:
            self.rows.append(row)
        return self

    def build(self) -> dict:
        return {"rows": [{"buttons": row} for row in self.rows]}


# میان‌بر برای ساخت سریع
def kb() -> InlineKeyboard:
    return InlineKeyboard()


def chat_keypad(rows: Sequence[Sequence[tuple[str, str]]], resize: bool = True,
                on_time: bool = False) -> dict:
    """ساخت کیبورد ثابتِ پایین صفحه (برای دسترسی سریع در گروه و پی‌وی)."""
    return {
        "rows": [{"buttons": [btn(t, c) for t, c in row]} for row in rows],
        "resize_keyboard": resize,
        "on_time_keyboard": on_time,
    }


# --------------------------------------------------------------------------- #
# کیبوردهای آماده
# --------------------------------------------------------------------------- #
def main_menu() -> dict:
    """منوی اصلی ربات — ۹ بخش، چیدمان سه‌ستونه و مرتب."""
    return (
        kb()
        .row(btn("🎵 موزیک", "menu:music"), btn("🤖 هوش مصنوعی", "menu:ai"))
        .row(btn("📥 دانلودر", "menu:dl"), btn("🛠 ابزارها", "menu:tools"))
        .row(btn("🌤 کاربردی", "menu:practical"), btn("🎮 سرگرمی", "menu:fun"))
        .row(btn("⚙️ مدیریت گروه", "menu:group"), btn("💎 عضویت ویژه", "menu:vip"))
        .row(btn("🍲 آشپزی", "menu:food"), btn("ℹ️ راهنما و پشتیبانی", "menu:help"))
        .row(btn("✨ مینی‌اپ آسترا", "app:open"))
        .build()
    )


def home_keyboard() -> dict:
    """کیبورد ثابت پایین صفحه برای دسترسی سریع."""
    return chat_keypad([
        [("🏠 منوی اصلی", "nav:home"), ("👤 پروفایل من", "vip:profile")],
        [("ℹ️ راهنما", "menu:help"), ("💎 خرید اشتراک", "menu:vip")],
    ])


def back_only(home: bool = True) -> dict:
    return kb().nav().build()


def yes_no(yes_cb: str, no_cb: str, yes_text: str = "✅ بله",
           no_text: str = "❌ خیر") -> dict:
    return kb().row(btn(yes_text, yes_cb), btn(no_text, no_cb)).build()


# --------------------------------------------------------------------------- #
# نکته: در روبیکا شناسه دکمه محدودیت طول دارد؛ برای داده‌های پویا
# از قالب «section:action:arg» استفاده می‌شود و طول آن کوتاه نگه داشته می‌شود.
# --------------------------------------------------------------------------- #
def dyn(prefix: str, value: str) -> str:
    """ساخت شناسه‌ی دکمه‌ی پویا."""
    return f"{prefix}:{value}"


def dyn_row(prefix: str, pairs: Sequence[tuple[str, str]],
            per_row: int = 2) -> InlineKeyboard:
    keyboard = kb()
    keyboard.grid([(text, f"{prefix}:{value}") for text, value in pairs], per_row)
    return keyboard


BOT_SIGNATURE = f"• {BOT_NAME} •"
