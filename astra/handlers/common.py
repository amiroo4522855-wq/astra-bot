"""ابزارهای مشترک بین همه‌ی handlerها: سربرگ‌ها، خطاها و ناوبری."""
from __future__ import annotations

from typing import Callable

from .. import config
from ..core.context import Context
from ..core.keyboards import InlineKeyboard, btn, main_menu
from ..core.router import find_callback_route
from ..core.utils import SEPARATOR, en_to_fa
from ..services.http import ServiceError

# پیام‌های خطای کاربرپسند برای خطاهای شناخته‌شده
ERROR_HINTS = (
    ("کلید هوش مصنوعی تنظیم نشده", "🤖 این بخش نیاز به کلید API دارد.\n"
                                    "ادمین ربات باید کلید را در تنظیمات قرار دهد."),
    ("yt-dlp نصب نیست", "📥 برای دانلود باید ابزار yt-dlp روی سرور نصب باشد.\n"
                        "راهنمای نصب در README پروژه است."),
    ("کتابخانه", "📦 یکی از کتابخانه‌های مورد نیاز نصب نیست.\n"
                 "راهنمای نصب در README پروژه است."),
    ("شهر پیدا نشد", "🏙 این شهر رو پیدا نکردم!\n"
                     "مثال: آب و هوا تهران"),
    ("زمان", "⏳ پردازش طول کشید؛ لطفاً دوباره امتحان کن."),
)


def enter(ctx: Context, route_id: str) -> None:
    """ثبت مسیر فعلی برای عملکرد دکمه‌ی بازگشت."""
    ctx.push_nav(route_id)


def go(ctx: Context, route_id: str, arg: str = "") -> None:
    """رفتن مستقیم به یک مسیر (مثل دکمه‌ی بازگشت)."""
    handler, _, _ = find_callback_route(route_id)
    if handler:
        ctx.arg = arg
        handler(ctx)
    else:
        ctx.send("🤔 مسیر مورد نظر پیدا نشد، برمی‌گردیم به خونه 👇", main_menu())


def header(title: str, subtitle: str = "") -> str:
    """سربرگ یکپارچه‌ی بخش‌ها."""
    text = f"{title}\n{SEPARATOR}"
    if subtitle:
        text += f"\n{subtitle}"
    return text


def section_closed(ctx: Context, section: str) -> bool:
    """اگر بخش خاموش است پیام می‌دهد و ‎True‎ برمی‌گرداند."""
    if ctx.db.section_enabled(section):
        return False
    label = config.SECTION_LABELS.get(section, section)
    ctx.answer(
        f"🚧 بخش {label} موقتاً غیرفعال است.\n"
        f"{SEPARATOR}\n"
        "به‌زودی برمی‌گرده! تا اون موقع از بقیه‌ی بخش‌ها استفاده کن 👇",
        main_menu(),
    )
    return True


def fail(ctx: Context, where: str, exc: BaseException, hint: str = "") -> None:
    """نمایش خطای دوستانه و ثبت آن در لاگ."""
    ctx.log_error(where, exc)
    message = str(exc) or "خطای ناشناخته"
    custom = hint
    if not custom:
        for needle, text in ERROR_HINTS:
            if needle in message:
                custom = text
                break
    body = custom or f"⚠️ مشکلی پیش اومد.\n{SEPARATOR}\n{message[:120]}"
    ctx.send(f"{body}\n{SEPARATOR}\nاگر ادامه داشت، از بخش پشتیبانی پیام بده 💬",
             main_menu())


def guarded(where: str, hint: str = "") -> Callable:
    """دکوراتور: مدیریت خطای handlerها بدون تکرار try/except."""
    def decorator(func: Callable) -> Callable:
        def wrapper(ctx: Context, *args, **kwargs):
            try:
                return func(ctx, *args, **kwargs)
            except Exception as exc:                       # هر خطایی → پیام کاربرپسند
                fail(ctx, where, exc, hint)
        wrapper.__name__ = getattr(func, "__name__", where)
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator


def premium_badge(ctx: Context) -> str:
    """نشان اشتراک ویژه در سربرگ پیام‌ها."""
    return "💎" if ctx.is_vip else "🆓"


def vip_line(ctx: Context) -> str:
    if ctx.is_vip:
        return f"💎 اشتراک ویژه · {ctx.vip_remaining} باقی‌مانده"
    return "🆓 حساب رایگان"


def back_row(home: bool = True) -> InlineKeyboard:
    from ..core.keyboards import kb
    return kb().nav()


def tip(text: str) -> str:
    return f"💡 {text}"


def cancel_keyboard(cancel_to: str = "nav:home") -> dict:
    from ..core.keyboards import kb
    return kb().row(btn("❌ انصراف", cancel_to)).build()
