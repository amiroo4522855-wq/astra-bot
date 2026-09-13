"""ابزارها: تبدیل واحد، ماشین‌حساب، فونت‌ساز، QR، کوتاه‌کننده، OCR و ساعت."""
from __future__ import annotations

import json
from pathlib import Path

from .. import config
from ..core.context import Context
from ..core.keyboards import btn, kb, main_menu
from ..core.router import route, state
from ..core.utils import SEPARATOR, en_to_fa, is_url, truncate
from ..services import calculator, convert, fonts, ocr, qr, shortlink
from ..services.clock import CITIES, city_time, now_report, world_clock
from .common import enter, go, guarded, header, section_closed, tip

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# --------------------------------------------------------------------------- #
# منو
# --------------------------------------------------------------------------- #
@route("menu:tools")
@guarded("tools.menu")
def tools_menu(ctx: Context) -> None:
    if section_closed(ctx, "tools"):
        return
    enter(ctx, "menu:tools")
    keyboard = (
        kb()
        .row(btn("🔤 فونت‌ساز", "tools:font"), btn("🧮 ماشین‌حساب", "tools:calc"))
        .row(btn("🔄 تبدیل واحد", "tools:convert"), btn("📱 ساخت QR", "tools:qr"))
        .row(btn("🔗 کوتاه‌کننده لینک", "tools:short"), btn("🔍 متن از عکس (OCR)", "tools:ocr"))
        .row(btn("🕓 ساعت جهانی", "tools:clock"))
        .nav()
    )
    ctx.answer(
        header("🛠 جعبه‌ابزار آسترا",
               "هر ابزاری که لازم داری، اینجاست 🧰\n"
               f"{SEPARATOR}\n"
               + tip("همه‌ی ابزارها رایگان‌اند؛ فقط بعضی‌ها سهمیه‌ی روزانه دارند.")),
        keyboard.build(),
    )


# --------------------------------------------------------------------------- #
# فونت‌ساز
# --------------------------------------------------------------------------- #
@route("tools:font")
@guarded("tools.font")
def font_start(ctx: Context) -> None:
    enter(ctx, "tools:font")
    ctx.set_state("await_font_text")
    ctx.answer(
        header("🔤 فونت‌ساز",
               "متن مورد نظرت رو بنویس تا با فونت‌های مختلف برات درست کنم ✨\n"
               f"{SEPARATOR}\n"
               + tip("فونت‌هایی با ✅ روی متن فارسی هم کار می‌کنند.")),
        kb().row(btn("❌ انصراف", "nav:back")).build(),
    )


@state("await_font_text")
@guarded("tools.font_do")
def font_prepare(ctx: Context) -> None:
    text = (ctx.text or "").strip()
    if text in ("❌ انصراف", "/cancel"):
        ctx.clear_state()
        go(ctx, "menu:tools")
        return
    if not text:
        ctx.send("✍️ یک متن بنویس 🙏")
        return
    if len(text) > 200:
        text = text[:200]
    ctx.set_state("font_pick", {"text": text})
    _show_font_styles(ctx, text)


def _show_font_styles(ctx: Context, text: str) -> None:
    lines = [
        header("🔤 فونت‌ساز", f"متن شما: «{truncate(text, 40)}»"),
        SEPARATOR,
        "چند نمونه‌ی سریع:",
    ]
    for label, sample in fonts.apply_all(text, limit=6):
        lines.append(f"▫️ {label}: {sample}")
    lines.append(SEPARATOR)
    lines.append(tip("برای دیدن همه‌ی سبک‌ها دکمه‌ی زیر رو بزن 👇"))

    keyboard = kb()
    keyboard.row(btn("🎨 انتخاب از ۱۹ سبک", "tools:fontall"),
                 btn("✍️ تغییر متن", "tools:font"))
    keyboard.row(btn("📋 کپی آخرین نمونه", "tools:fontcopy"))
    keyboard.nav()
    ctx.send("\n".join(lines), keyboard.build())


@route("tools:fontall")
@guarded("tools.font_all")
def font_all(ctx: Context) -> None:
    _, data = ctx.get_state()
    text = data.get("text", "")
    if not text:
        go(ctx, "tools:font")
        return
    enter(ctx, "tools:fontall")
    keyboard = kb()
    keyboard.grid(fonts.style_keyboard("tools:fontpick"), per_row=2)
    keyboard.nav()
    ctx.answer(header("🎨 انتخاب سبک", "یکی از سبک‌ها رو انتخاب کن 👇"), keyboard.build())


@route("tools:fontpick", prefix=True)
@guarded("tools.font_pick")
def font_pick(ctx: Context) -> None:
    _, data = ctx.get_state()
    text = data.get("text", "")
    style = (ctx.arg or "bold").strip()
    if not text:
        go(ctx, "tools:font")
        return
    result = fonts.apply(text, style)
    ctx.set_state("font_pick", {"text": text, "last": result, "style": style})
    ctx.answer(
        f"{fonts.STYLES.get(style, ('سبک', '✨'))[1]} خروجی:\n{SEPARATOR}\n{result}",
        kb().row(btn("🎨 سبک دیگر", "tools:fontall"), btn("✍️ متن جدید", "tools:font"))
             .row(btn("🏠 منوی اصلی", "nav:home")).build(),
    )


@route("tools:fontcopy")
@guarded("tools.font_copy")
def font_copy(ctx: Context) -> None:
    _, data = ctx.get_state()
    result = data.get("last") or ""
    ctx.answer(f"📋 برای کپی روی متن زیر بزن و نگه دار:\n{SEPARATOR}\n{result or '—'}")


# --------------------------------------------------------------------------- #
# ماشین‌حساب
# --------------------------------------------------------------------------- #
@route("tools:calc")
@guarded("tools.calc")
def calc_start(ctx: Context) -> None:
    enter(ctx, "tools:calc")
    ctx.set_state("await_calc")
    ctx.answer(
        header("🧮 ماشین‌حساب",
               "عبارت ریاضی‌ات رو بنویس 🧠\n"
               f"{SEPARATOR}\n"
               "مثال‌ها:\n"
               "▫️ ‎(12+8)*3‎\n"
               "▫️ ‎sqrt(144)‎ · ‎2**10‎ · ‎sin(30)‎\n"
               "▫️ ‎15٪ از 200 → ‎15*200/100‎"),
        kb().row(btn("❌ انصراف", "nav:back")).build(),
    )


@state("await_calc")
@guarded("tools.calc_do")
def calc_do(ctx: Context) -> None:
    expression = (ctx.text or "").strip()
    if expression in ("❌ انصراف", "/cancel"):
        ctx.clear_state()
        go(ctx, "menu:tools")
        return
    try:
        result = calculator.calculate(expression)
    except Exception:
        ctx.send(
            "🤔 این عبارت رو نمی‌فهمم!\n"
            f"{SEPARATOR}\n"
            "فقط اعداد و عملگرهای + - * / ( ) مجازند.\n"
            "مثال: ‎(25*4)/2‎",
            kb().row(btn("🔄 تلاش دوباره", "tools:calc"),
                     btn("🏠 منوی اصلی", "nav:home")).build(),
        )
        return
    ctx.clear_state()
    ctx.send(
        f"🧮 نتیجه\n{SEPARATOR}\n"
        f"📥 {en_to_fa(expression)}\n"
        f"📤 {calculator.format_result(result)} ✅",
        kb().row(btn("🧮 محاسبه‌ی بعدی", "tools:calc"),
                 btn("🏠 منوی اصلی", "nav:home")).build(),
    )


# --------------------------------------------------------------------------- #
# تبدیل واحد
# --------------------------------------------------------------------------- #
@route("tools:convert")
@guarded("tools.convert")
def convert_start(ctx: Context) -> None:
    enter(ctx, "tools:convert")
    ctx.set_state("await_convert")
    categories = [("📏 طول", "length"), ("⚖️ وزن", "mass"), ("🌡 دما", "temperature"),
                  ("⏱ زمان", "time"), ("💾 داده", "data"), ("🗺 مساحت", "area")]
    keyboard = kb()
    keyboard.grid([(label, f"tools:convcat:{key}") for label, key in categories], per_row=2)
    keyboard.nav()
    ctx.answer(
        header("🔄 تبدیل واحد",
               "فرمت: «مقدار واحد به واحد»\n"
               f"{SEPARATOR}\n"
               "مثال‌ها:\n"
               "▫️ ‎10 کیلومتر به متر‎\n"
               "▫️ ‎100 فارنهایت به سانتی‌گراد‎\n"
               "▫️ ‎2 ساعت به دقیقه‎\n"
               f"{SEPARATOR}\n"
               + tip("می‌توانی مستقیم بنویسی یا از دسته‌ها شروع کنی 👇")),
        keyboard.build(),
    )


@route("tools:convcat", prefix=True)
@guarded("tools.convert_cat")
def convert_category(ctx: Context) -> None:
    category = (ctx.arg or "length").strip()
    examples = {
        "length": "10 کیلومتر به متر", "mass": "5 کیلوگرم به گرم",
        "temperature": "100 فارنهایت به سانتی‌گراد", "time": "2 ساعت به دقیقه",
        "data": "2 گیگابایت به مگابایت", "area": "3 هکتار به متر مربع",
        "speed": "90 کیلومتر بر ساعت به متر بر ثانیه", "volume": "2 لیتر به میلی‌لیتر",
    }
    ctx.set_state("await_convert", {"category": category})
    ctx.answer(
        f"🔄 {convert.CATEGORY_LABELS.get(category, category)}\n{SEPARATOR}\n"
        f"مثال: «{examples.get(category, '10 کیلومتر به متر')}»\n"
        "حالا عبارت خودت رو بنویس ✍️",
        kb().row(btn("❌ انصراف", "nav:back")).build(),
    )


@state("await_convert")
@guarded("tools.convert_do")
def convert_do(ctx: Context) -> None:
    text = (ctx.text or "").strip()
    if text in ("❌ انصراف", "/cancel"):
        ctx.clear_state()
        go(ctx, "menu:tools")
        return
    try:
        result = convert.convert_text(text)
    except Exception:
        ctx.send(
            "🤔 فرمت رو درست نفهمیدم!\n"
            f"{SEPARATOR}\n"
            "این شکلی بنویس:\n"
            "▫️ ‎10 کیلومتر به متر‎\n"
            "▫️ ‎5 کیلو به گرم‎",
            kb().row(btn("🔄 تلاش دوباره", "tools:convert"),
                     btn("🏠 منوی اصلی", "nav:home")).build(),
        )
        return
    ctx.clear_state()
    ctx.send(result, kb().row(btn("🔄 تبدیل دیگر", "tools:convert"),
                              btn("🏠 منوی اصلی", "nav:home")).build())


# --------------------------------------------------------------------------- #
# کوتاه‌کننده لینک
# --------------------------------------------------------------------------- #
@route("tools:short")
@guarded("tools.short")
def short_start(ctx: Context) -> None:
    enter(ctx, "tools:short")
    ctx.set_state("await_shortlink")
    ctx.answer(
        header("🔗 کوتاه‌کننده لینک",
               "لینک طولانی‌ات رو بفرست تا کوتاهش کنم ✂️\n"
               f"{SEPARATOR}\n"
               + tip("اگر https نداشته باشد، خودم اضافه می‌کنم.")),
        kb().row(btn("❌ انصراف", "nav:back")).build(),
    )


@state("await_shortlink")
@guarded("tools.short_do")
def short_do(ctx: Context) -> None:
    url = (ctx.text or "").strip()
    if url in ("❌ انصراف", "/cancel"):
        ctx.clear_state()
        go(ctx, "menu:tools")
        return
    if "http" not in url:
        url = "https://" + url
    try:
        short = shortlink.shorten(url)
    except Exception as exc:
        from .common import fail
        fail(ctx, "tools.short", exc, "⚠️ نتونستم لینک رو کوتاه کنم. لینک رو چک کن و دوباره بفرست 🙏")
        return
    ctx.clear_state()
    ctx.send(
        f"🔗 لینک کوتاه شما\n{SEPARATOR}\n{short}\n{SEPARATOR}\n"
        f"📥 لینک اصلی: {truncate(url, 60)}",
        kb().row(btn("🔗 لینک دیگر", "tools:short"),
                 btn("🏠 منوی اصلی", "nav:home")).build(),
    )


# --------------------------------------------------------------------------- #
# QR Code
# --------------------------------------------------------------------------- #
@route("tools:qr")
@guarded("tools.qr")
def qr_start(ctx: Context) -> None:
    enter(ctx, "tools:qr")
    ctx.set_state("await_qr")
    ctx.answer(
        header("📱 ساخت QR Code",
               "متن یا لینکی که می‌خوای به QR تبدیل بشه رو بفرست 📲\n"
               f"{SEPARATOR}\n"
               + tip("مثال: https://rubika.ir یا شماره کارت بانکی")),
        kb().row(btn("❌ انصراف", "nav:back")).build(),
    )


@state("await_qr")
@guarded("tools.qr_do")
def qr_do(ctx: Context) -> None:
    data = (ctx.text or "").strip()
    if data in ("❌ انصراف", "/cancel"):
        ctx.clear_state()
        go(ctx, "menu:tools")
        return
    if not data:
        ctx.send("✍️ یک متن یا لینک بفرست 🙏")
        return
    if not ctx.consume("qr"):
        from .vip import upgrade_keyboard
        message, keyboard = ctx.limit_message("qr")
        ctx.send(message, keyboard)
        return
    ctx.clear_state()
    ctx.send("📱 دارم QR می‌سازم…")
    image = qr.make_png_bytes(data)
    file_id = ctx.client.upload_bytes(image, "astra-qr.png", "Image")
    ctx.client.send_file(
        ctx.chat_id, file_id,
        caption=f"📱 QR Code آماده شد ✅\n{SEPARATOR}\n{truncate(data, 60)}",
        file_type="Image",
        inline_keypad=kb().row(btn("📱 QR دیگر", "tools:qr"),
                               btn("🏠 منوی اصلی", "nav:home")).build(),
    )


# --------------------------------------------------------------------------- #
# OCR
# --------------------------------------------------------------------------- #
@route("tools:ocr")
@guarded("tools.ocr")
def ocr_start(ctx: Context) -> None:
    enter(ctx, "tools:ocr")
    ctx.set_state("await_ocr")
    ctx.answer(
        header("🔍 استخراج متن از عکس (OCR)",
               "عکسی که متن دارد رو بفرست تا متنش رو برات بنویسم 📷\n"
               f"{SEPARATOR}\n"
               + tip("عکس باید واضح و نوشته‌ها خوانا باشند.")),
        kb().row(btn("❌ انصراف", "nav:back")).build(),
    )


def handle_photo(ctx: Context) -> bool:
    """اگر کاربر عکس فرستاد و OCR فعال است، متن آن را استخراج می‌کند."""
    state_name, _ = ctx.get_state()
    if state_name and state_name != "await_ocr":
        return False
    if not ctx.update.file_id:
        return False
    if not ctx.consume("ocr"):
        from .vip import upgrade_keyboard
        message, keyboard = ctx.limit_message("ocr")
        ctx.send(message, keyboard)
        return True
    ctx.clear_state()
    ctx.send("🔍 دارم متن عکس رو می‌خونم…")
    try:
        download_url = ctx.client.get_file(ctx.update.file_id)
        from ..services.http import get_bytes
        content = get_bytes(download_url, timeout=40)
        text = ocr.extract_text(content)
    except Exception as exc:
        from .common import fail
        fail(ctx, "tools.ocr", exc,
             "⚠️ نتونستم متن عکس رو بخونم.\nعکس واضح‌تری بفرست 🙏")
        return True
    ctx.send(
        f"📷 متن استخراج‌شده\n{SEPARATOR}\n{text[:3000]}",
        kb().row(btn("🌐 ترجمه‌اش کن", "ai:translate"),
                 btn("📄 خلاصه‌اش کن", "ai:summary"))
             .row(btn("🔍 عکس دیگر", "tools:ocr"), btn("🏠 منوی اصلی", "nav:home"))
             .build(),
    )
    return True


# --------------------------------------------------------------------------- #
# ساعت جهانی
# --------------------------------------------------------------------------- #
@route("tools:clock")
@guarded("tools.clock")
def clock_menu(ctx: Context) -> None:
    enter(ctx, "tools:clock")
    cities = list(CITIES)[:12]
    keyboard = kb()
    keyboard.grid([(city, f"tools:city:{index}") for index, city in enumerate(cities)], per_row=3)
    keyboard.row(btn("🇮🇷 ساعت ایران", "tools:city:-1"))
    keyboard.nav()
    ctx.answer(header("🕓 ساعت جهانی", world_clock().split("───────────────")[0].strip() +
                      "\nیک شهر انتخاب کن 👇"), keyboard.build())


@route("tools:city", prefix=True)
@guarded("tools.city")
def clock_city(ctx: Context) -> None:
    try:
        index = int(ctx.arg or "-1")
    except ValueError:
        index = -1
    if index < 0:
        ctx.answer(header("🇮🇷 زمان ایران", now_report().split("───────────────")[-1].strip()),
                   kb().row(btn("🌍 شهر دیگر", "tools:clock"),
                            btn("🏠 منوی اصلی", "nav:home")).build())
        return
    cities = list(CITIES)
    city = cities[index] if index < len(cities) else cities[0]
    info = city_time(city)
    ctx.answer(
        f"🕓 ساعت {city}\n{SEPARATOR}\n"
        f"⏰ {info[1]}\n📅 {info[2]}",
        kb().row(btn("🌍 شهر دیگر", "tools:clock"), btn("🏠 منوی اصلی", "nav:home")).build(),
    )
