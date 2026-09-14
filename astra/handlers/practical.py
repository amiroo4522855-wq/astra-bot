"""بخش کاربردی: آب‌وهوا، ارز، طلا و سکه، ارز دیجیتال و زمان."""
from __future__ import annotations

from ..core.context import Context
from .. import config
from ..core.keyboards import btn, kb, main_menu
from ..core.router import route, state
from ..core.utils import SEPARATOR, en_to_fa
from ..services import currency, weather
from ..services.clock import now_report
from .common import enter, fail, go, guarded, header, section_closed, tip

POPULAR_CITIES = ["تهران", "مشهد", "اصفهان", "شیراز", "تبریز", "لندن"]


# --------------------------------------------------------------------------- #
# منو
# --------------------------------------------------------------------------- #
@route("menu:practical")
@guarded("practical.menu")
def practical_menu(ctx: Context) -> None:
    if section_closed(ctx, "practical"):
        return
    enter(ctx, "menu:practical")
    keyboard = (
        kb()
        .row(btn("🌤 آب و هوا", "practical:weather"), btn("💰 نرخ ارز", "practical:currency"))
        .row(btn("🥇 طلا و سکه", "practical:gold"), btn("🪙 ارز دیجیتال", "practical:crypto"))
        .row(btn("🕰 ساعت و تاریخ", "practical:time"))
        .nav()
    )
    ctx.answer(
        header("🌤 بخش کاربردی",
               "خبرهای لحظه‌ای هوا و بازار، همیشه در دسترس 📊\n"
               f"{SEPARATOR}\n"
               + tip("می‌توانی بنویسی: «آب و هوا شیراز» یا «قیمت دلار»")),
        keyboard.build(),
    )


# --------------------------------------------------------------------------- #
# آب و هوا
# --------------------------------------------------------------------------- #
@route("practical:weather")
@guarded("weather.menu")
def weather_menu(ctx: Context) -> None:
    enter(ctx, "practical:weather")
    keyboard = kb()
    keyboard.grid([(city, f"practical:wcity:{city}") for city in POPULAR_CITIES], per_row=3)
    keyboard.row(btn("✍️ وارد کردن شهر", "practical:weatherinput"))
    keyboard.nav()
    ctx.answer(
        header("🌤 آب و هوا",
               "اسم شهر رو انتخاب کن یا بنویس 🏙\n"
               f"{SEPARATOR}\n"
               + tip("مثال: آب و هوا رشت")),
        keyboard.build(),
    )


@route("practical:weatherinput")
@guarded("weather.input")
def weather_input(ctx: Context) -> None:
    enter(ctx, "practical:weatherinput")
    ctx.set_state("await_weather")
    ctx.answer(
        header("🏙 جستجوی شهر",
               "اسم شهر (فارسی یا انگلیسی) رو بنویس 🌍\n"
               f"{SEPARATOR}\n"
               + tip("مثال: تهران / Mashhad / Istanbul")),
        kb().row(btn("❌ انصراف", "nav:back")).build(),
    )


@route("practical:wcity", prefix=True)
@guarded("weather.city")
def weather_city(ctx: Context) -> None:
    city = (ctx.arg or "").strip()
    if not city:
        go(ctx, "practical:weather")
        return
    show_weather(ctx, city)


@state("await_weather")
@guarded("weather.do")
def weather_do(ctx: Context) -> None:
    city = (ctx.text or "").strip()
    if city in ("❌ انصراف", "/cancel"):
        ctx.clear_state()
        go(ctx, "practical:weather")
        return
    show_weather(ctx, city)


def show_weather(ctx: Context, city: str) -> None:
    ctx.clear_state()
    try:
        report = weather.render_full(city)
    except Exception:
        try:
            report = weather.render(city)
        except Exception as exc:
            fail(ctx, "weather", exc,
                 "🏙 این شهر رو پیدا نکردم!\n"
                 "اسم شهر رو دقیق‌تر بنویس (مثال: کرمانشاه) 🙏")
            return
        fail(ctx, "weather", exc,
             "🏙 این شهر رو پیدا نکردم!\n"
             "اسم شهر رو دقیق‌تر بنویس (مثال: تهران) 🙏")
        return
    ctx.send(
        report,
        kb().row(btn("🏙 شهر دیگر", "practical:weatherinput"),
                 btn("🌤 کاربردی", "menu:practical"))
             .row(btn("🏠 منوی اصلی", "nav:home")).build(),
    )


# --------------------------------------------------------------------------- #
# بازار
# --------------------------------------------------------------------------- #
MARKET_DOWN = ("📡 دریافت اطلاعات بازار در این لحظه ممکن نیست.\n"
               "چند دقیقه‌ی دیگر دوباره امتحان کن 🙏")


def _report(ctx: Context, kind: str) -> None:
    rows: list = []
    try:
        rows = currency.fetch_tgju()
        if not rows:
            raise RuntimeError("داده‌ای دریافت نشد")
    except Exception as tgju_error:
        # منبع دوم: کانال قیمتی که ربات در آن ادمین است
        rows = currency.channel_prices(ctx.db)
        if not rows and kind == "crypto":
            try:
                rows = currency.fetch_crypto()
            except Exception as crypto_error:
                if not rows:
                    fail(ctx, "market", crypto_error, MARKET_DOWN)
                    return
        if not rows:
            rows = currency.channel_prices(ctx.db)
        if not rows:
            fail(ctx, "market", tgju_error, MARKET_DOWN)
            return

    if kind == "currency":
        title, keywords = "💰 نرخ ارز", ("💵", "💶", "💷", "🕌", "🇹🇷", "🇨🇳", "🇮🇶", "🇦🇫")
    elif kind == "gold":
        title, keywords = "🥇 طلا و سکه", ("🪙", "🥈", "🥉", "🌸", "✨", "💛", "⚖️", "🌍")
    else:
        title, keywords = "🪙 ارز دیجیتال", ("🟠", "🟣", "🟢", "🟡", "🔴", "⚪️", "🟤", "🟦")

    selected = [row for row in rows if any(row[0].startswith(k) for k in keywords)]
    if kind == "crypto" and not selected:
        selected = rows
    if not selected:
        ctx.send("📊 داده‌ای برای این بخش پیدا نشد.\nکمی بعد دوباره امتحان کن 🙏")
        return

    lines = [f"{title}", SEPARATOR]
    lines += [f"{label} : {value}" for label, value, _ in selected[:12]]

    # قیمت‌های کانالِ متصل (اگر موجود باشد) — با ذکر منبع
    try:
        channel = currency.fetch_channel_web()
    except Exception:
        channel = []
    if channel:
        channel = [row for row in channel
                   if any(row[0].startswith(k) for k in keywords)] or channel
        lines.append(SEPARATOR)
        lines.append(f"📢 بر اساس کانال @{config.PRICE_CHANNEL}:")
        lines += [f"{label} : {value}" for label, value, _ in channel[:8]]
        if currency.channel_stamp():
            lines.append(f"🕓 آخرین به‌روزرسانی کانال: {currency.channel_stamp()[:16]}")

    ctx.send("\n".join(lines),
             kb().row(btn("🔄 بروزرسانی", f"practical:{kind}"),
                      btn("🌤 کاربردی", "menu:practical"))
                  .row(btn("🏠 منوی اصلی", "nav:home")).build())


@route("practical:currency")
@guarded("market.currency")
def market_currency(ctx: Context) -> None:
    enter(ctx, "practical:currency")
    ctx.send("⏳ دارم نرخ‌ها رو می‌گیرم…")
    _report(ctx, "currency")


@route("practical:gold")
@guarded("market.gold")
def market_gold(ctx: Context) -> None:
    enter(ctx, "practical:gold")
    ctx.send("⏳ دارم نرخ طلا و سکه رو می‌گیرم…")
    _report(ctx, "gold")


@route("practical:crypto")
@guarded("market.crypto")
def market_crypto(ctx: Context) -> None:
    enter(ctx, "practical:crypto")
    ctx.send("⏳ دارم قیمت ارزهای دیجیتال رو می‌گیرم…")
    _report(ctx, "crypto")


@route("practical:time")
@guarded("practical.time")
def practical_time(ctx: Context) -> None:
    enter(ctx, "practical:time")
    ctx.answer(
        now_report(),
        kb().row(btn("🕓 ساعت جهانی", "tools:clock"),
                 btn("🏠 منوی اصلی", "nav:home")).build(),
    )
