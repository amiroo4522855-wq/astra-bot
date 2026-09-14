"""مدیریت پست‌های کانال.

اگر ربات را در یک کانالِ قیمت (مثل کانال‌های نرخ ارز و طلا) ادمین کنید،
هر پست آن کانال به‌طور خودکار خوانده می‌شود و قیمت‌ها استخراج و کش می‌گردد؛
بعداً در بخش «بازار» به‌عنوان منبع پشتیبان استفاده می‌شود.
"""
from __future__ import annotations

from ..core.context import Context
from ..services import currency


def handle_channel_post(ctx: Context) -> None:
    """ذخیره‌ی قیمت‌های موجود در پست کانال (بدون پاسخ‌دهی)."""
    text = ctx.text or ""
    if not text:
        return
    try:
        count = currency.save_channel_prices(ctx.db, text)
    except Exception as exc:                      # هرگز نباید باعث خطای ربات شود
        ctx.db.log("ERROR", "channel.prices", str(exc))
        return
    if count:
        ctx.track("channel:prices")
        ctx.db.log("INFO", "channel.prices", f"{count} قیمت از کانال ذخیره شد")
