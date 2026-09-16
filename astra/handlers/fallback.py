"""درک زبان طبیعی: کاربر می‌تواند به‌جای دکمه، متن بنویسد.

مثال‌ها:
    «آب و هوا تهران» → نمایش وضعیت هوا
    «قیمت دلار»      → نرخ لحظه‌ای
    «فونت آسترا»     → فونت‌ساز
    «12*8»           → ماشین‌حساب
    لینک             → پیشنهاد دانلود
"""
from __future__ import annotations

import re

from ..core.context import Context
from ..core.keyboards import btn, kb, main_menu
from ..core.router import text
from ..core.utils import SEPARATOR, clean, extract_url, fa_to_en
from .common import guarded

RE_WEATHER = re.compile(r"(آب\s*و\s*هوا|هوای|دمای|هواشناسی|weather)", re.IGNORECASE)
RE_PRICE = re.compile(r"(قیمت|نرخ|دلار|یورو|پوند|طلا|سکه|ارز|بیت\s*کوین|تتر|crypto)", re.IGNORECASE)
RE_FONT = re.compile(r"^(فونت|font)\b", re.IGNORECASE)
RE_MATH = re.compile(r"^[\d\s\+\-\*\/\(\)\.\^\%×÷]+$")
RE_CONVERT = re.compile(r"(\d)\s+(\S+)\s+(به|to)\s+(\S+)", re.IGNORECASE)
RE_GREET = re.compile(r"^(سلام|درود|hello|hi|های|هلو|salam)\b", re.IGNORECASE)
RE_THANKS = re.compile(r"(مرسی|ممنون|تشکر|thank)", re.IGNORECASE)
RE_MENU = re.compile(r"^(منو|منوی اصلی|بازگشت|برگشت|menu)$", re.IGNORECASE)
RE_VIP = re.compile(r"(اشتراک|ویژه|vip|خرید)", re.IGNORECASE)
RE_CITY_TIME = re.compile(r"(ساعت|تاریخ|ساعت چند)", re.IGNORECASE)
RE_FOOD = re.compile(r"(دستور\s*پخت|طرز\s*تهیه|دستور\s*غذا|چی\s*بپزم|چی\s*درست\s*کنم|"
                     r"آشپزی|رسپی|غذای\s*ایرانی)", re.IGNORECASE)


def _strip_keyword(text: str, pattern: re.Pattern) -> str:
    return clean(pattern.sub("", text, count=1))


# --------------------------------------------------------------------------- #
# آشپزی ایرانی (۱۰۰ غذا)
# --------------------------------------------------------------------------- #
@text(lambda ctx: bool(RE_FOOD.search(ctx.text or "")))
@guarded("nlp.food")
def nlp_food(ctx: Context) -> None:
    from ..services import recipes
    from .food import _build
    from ..core.keyboards import btn as _btn
    query = re.sub(RE_FOOD, " ", ctx.text or "")
    query = re.sub(r"^(برام|برایم|لطفا|لطفاً|امروز|یه|یک)\s+", "", query.strip()).strip(" .؟?")
    suggest_only = bool(re.search(r"(چی\s*بپزم|چی\s*درست\s*کنم|پیشنهاد)", ctx.text or ""))
    item = None if suggest_only else recipes.find(query)
    if item:
        ctx.send(recipes.render(item) + "\n" + SEPARATOR + "\n"
                 + "دستورِ غذای بعدی را بنویسید یا پیشنهادِ شانسی بگیرید 🎲",
                 _build([
                     [_btn("🎲 پیشنهاد دیگر", "food:random"),
                      _btn("🍲 دسته‌ها", "menu:food")],
                     [_btn("🏠 منوی اصلی", "nav:home")]]))
        return
    if suggest_only or not query:
        text = recipes.suggestion_text() or "🍲 دستوری در دسترس نیست 🙏"
        ctx.send(text, _build([
            [_btn("🎲 یکی دیگر", "food:random"), _btn("🍲 دسته‌ها", "menu:food")],
            [_btn("🏠 منوی اصلی", "nav:home")]]))
        return
    ctx.send(
        f"🍲 دستورِ «{query}» را در مجموعه‌ام پیدا نکردم\n{SEPARATOR}\n"
        "من ۱۰۰ غذای اصیل ایرانی را با دستورِ کامل دارم.\n"
        "نامِ غذا را دقیق‌تر بنویسید یا از دسته‌ها انتخاب کنید 👇",
        _build([[_btn("🍲 دسته‌های غذا", "menu:food"),
                 _btn("🎲 پیشنهاد شانسی", "food:random")],
                [_btn("🏠 منوی اصلی", "nav:home")]]))


# --------------------------------------------------------------------------- #
# آب و هوا
# --------------------------------------------------------------------------- #
@text(lambda ctx: bool(RE_WEATHER.search(ctx.text)))
@guarded("nlp.weather")
def nlp_weather(ctx: Context) -> None:
    city = _strip_keyword(ctx.text, RE_WEATHER)
    city = re.sub(r"^(در|شهر)\s+", "", city).strip() or "تهران"
    from .practical import show_weather
    show_weather(ctx, city)


# --------------------------------------------------------------------------- #
# قیمت
# --------------------------------------------------------------------------- #
@text(lambda ctx: bool(RE_PRICE.search(ctx.text)) and not RE_WEATHER.search(ctx.text))
@guarded("nlp.price")
def nlp_price(ctx: Context) -> None:
    from .practical import _report
    lowered = ctx.text.lower()
    if any(word in lowered for word in ("طلا", "سکه", "مثقال")):
        ctx.send("⏳ دارم نرخ طلا و سکه رو می‌گیرم…")
        _report(ctx, "gold")
    elif any(word in lowered for word in ("بیت", "تتر", "اتریوم", "کریپتو", "crypto")):
        ctx.send("⏳ دارم قیمت ارزهای دیجیتال رو می‌گیرم…")
        _report(ctx, "crypto")
    else:
        ctx.send("⏳ دارم نرخ‌ها رو می‌گیرم…")
        _report(ctx, "currency")


# --------------------------------------------------------------------------- #
# فونت
# --------------------------------------------------------------------------- #
@text(lambda ctx: bool(RE_FONT.match(ctx.text)))
@guarded("nlp.font")
def nlp_font(ctx: Context) -> None:
    from .tools import font_prepare
    ctx.update.text = _strip_keyword(ctx.text, RE_FONT)
    font_prepare(ctx)


# --------------------------------------------------------------------------- #
# ماشین‌حساب
# --------------------------------------------------------------------------- #
@text(lambda ctx: len(ctx.text) > 2 and bool(RE_MATH.match(ctx.text)) and
      any(op in ctx.text for op in "+-*/×÷"))
@guarded("nlp.calc")
def nlp_calc(ctx: Context) -> None:
    from ..services import calculator
    try:
        result = calculator.calculate(ctx.text)
    except Exception:
        return
    ctx.send(
        f"🧮 {ctx.text} = {calculator.format_result(result)} ✅",
        kb().row(btn("🧮 ماشین‌حساب", "tools:calc"), btn("🏠 منوی اصلی", "nav:home")).build(),
    )


# --------------------------------------------------------------------------- #
# تبدیل واحد
# --------------------------------------------------------------------------- #
@text(lambda ctx: bool(RE_CONVERT.search(ctx.text)))
@guarded("nlp.convert")
def nlp_convert(ctx: Context) -> None:
    from ..services import convert
    try:
        result = convert.convert_text(ctx.text)
    except Exception:
        return
    ctx.send(result, kb().row(btn("🔄 تبدیل دیگر", "tools:convert"),
                              btn("🏠 منوی اصلی", "nav:home")).build())


# --------------------------------------------------------------------------- #
# لینک
# --------------------------------------------------------------------------- #
@text(lambda ctx: bool(extract_url(ctx.text)) and ctx.is_private)
@guarded("nlp.url")
def nlp_url(ctx: Context) -> None:
    url = extract_url(ctx.text)
    from .downloader import detect_kind
    kind = detect_kind(url) or "ytv"
    ctx.send(
        f"🔗 یک لینک فرستادی!\n{SEPARATOR}\n"
        "می‌خوای چیکارش کنم؟ 👇",
        kb().row(btn("▶️ دانلود ویدیو", f"dl:ytv"), btn("🎵 دانلود صدا", f"dl:yta"))
             .row(btn("📸 اینستاگرام", "dl:ig"), btn("🎵 تیک‌تاک", "dl:tt"))
             .row(btn("🔗 کوتاهش کن", "tools:short"), btn("📱 QR بساز", "tools:qr"))
             .row(btn("🏠 منوی اصلی", "nav:home")).build(),
    )
    ctx.db.set_state(ctx.sender_id, "await_dl", {"kind": kind})


# --------------------------------------------------------------------------- #
# احوال‌پرسی و موارد عمومی
# --------------------------------------------------------------------------- #
@text(lambda ctx: bool(RE_GREET.match(ctx.text)) and ctx.is_private)
@guarded("nlp.greet")
def nlp_greet(ctx: Context) -> None:
    from .start import start
    start(ctx)


@text(lambda ctx: bool(RE_MENU.match(ctx.text)))
@guarded("nlp.menu")
def nlp_menu(ctx: Context) -> None:
    from .start import home
    home(ctx)


@text(lambda ctx: bool(RE_VIP.search(ctx.text)) and ctx.is_private and len(ctx.text) < 30)
@guarded("nlp.vip")
def nlp_vip(ctx: Context) -> None:
    from .vip import vip_menu
    vip_menu(ctx)


@text(lambda ctx: bool(RE_CITY_TIME.search(ctx.text)) and ctx.is_private)
@guarded("nlp.time")
def nlp_time(ctx: Context) -> None:
    from ..services.clock import now_report
    ctx.send(now_report(),
             kb().row(btn("🕓 ساعت جهانی", "tools:clock"),
                      btn("🏠 منوی اصلی", "nav:home")).build())


@text(lambda ctx: bool(RE_THANKS.search(ctx.text)) and ctx.is_private and len(ctx.text) < 30)
@guarded("nlp.thanks")
def nlp_thanks(ctx: Context) -> None:
    ctx.send("خواهش می‌کنم! همیشه در خدمتم 🙌\n"
             "اگر بازم کاری داشتی، منوی اصلی در دسترسه 👇", main_menu())


# --------------------------------------------------------------------------- #
# ناشناخته
# --------------------------------------------------------------------------- #
@guarded("nlp.unknown")
def unknown(ctx: Context) -> None:
    """وقتی هیچ‌کدام از قوانین بالا جواب نداد."""
    if not ctx.is_private:
        return  # در گروه ساکت می‌مانیم تا مزاحمت ایجاد نشود
    ctx.send(
        "🤔 متوجه منظورت نشدم!\n"
        f"{SEPARATOR}\n"
        "چند تا ایده:\n"
        "▫️ «آب و هوا تهران»\n"
        "▫️ «قیمت دلار»\n"
        "▫️ آهنگ یا خواننده‌ی مورد علاقه‌ات رو بنویس\n"
        "▫️ لینک یوتیوب/اینستاگرام رو بفرست\n"
        f"{SEPARATOR}\n"
        "یا از منوی زیر انتخاب کن 👇",
        main_menu(),
    )
