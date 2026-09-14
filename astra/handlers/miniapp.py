"""مینی‌اپ (Telegram Web App) آسترا.

دو مسیر دارد:
    ۱. کاربر دکمه‌ی «مینی‌اپ» را می‌زند → ربات یک دکمه‌ی WebApp می‌فرستد
    ۲. کاربر داخل مینی‌اپ کاری انجام می‌دهد → اپ با ‎WebApp.sendData‎ یک JSON
       می‌فرستد و تلگرام آن را به‌صورت ‎message.web_app_data‎ تحویل می‌دهد؛
       اینجا همان JSON را می‌خوانیم و به handler مربوطه وصل می‌کنیم.

ابزارهای سبک (فونت، ماشین‌حساب، تبدیل واحد، ساعت، آب‌وهوا، ارز، سرگرمی)
داخل خود اپ اجرا می‌شوند و کارهای سنگین (هوش مصنوعی، دانلود، موزیک، QR،
ویس، OCR) از همین مسیر به ربات می‌آیند و نتیجه در چت فرستاده می‌شود.
"""
from __future__ import annotations

import json

from .. import config
from ..core.context import Context
from ..core.keyboards import btn, kb, main_menu, web_app_btn
from ..core.router import command, route
from ..core.utils import SEPARATOR, en_to_fa, truncate
from .common import go, guarded, header, tip


def is_telegram(ctx: Context) -> bool:
    return getattr(ctx.client, "platform", "rubika") == "telegram"


# --------------------------------------------------------------------------- #
# باز کردن اپ
# --------------------------------------------------------------------------- #
@route("app:open")
@command("/app", "/miniapp", "/مینی_اپ", "/اپلیکیشن")
@guarded("app.open")
def open_app(ctx: Context) -> None:
    """نمایش دکمه‌ی بازکننده‌ی مینی‌اپ (یا لینک، اگر تلگرام نباشد)."""
    if not config.APP_URL:
        ctx.answer("✨ مینی‌اپ هنوز تنظیم نشده است.")
        return

    if not is_telegram(ctx):
        ctx.answer(
            header("✨ مینی‌اپ آسترا",
                   "این قابلیت مخصوص تلگرام است.\n"
                   f"{SEPARATOR}\n"
                   "آدرس اپ روی وب:\n"
                   f"{config.APP_URL}"),
            kb().row(btn("🏠 منوی اصلی", "nav:home")).build(),
        )
        return

    ctx.answer(
        header("✨ مینی‌اپ آسترا",
               "یک رابط گرافیکی سریع برای ابزارها 📱\n"
               f"{SEPARATOR}\n"
               "▫️ آب‌وهوا، ارز، کریپتو (آنی)\n"
               "▫️ فونت‌ساز، ماشین‌حساب، تبدیل واحد، ساعت\n"
               "▫️ جوک، شعر، فال و چالش روزانه\n"
               "▫️ و بقیه‌ی ابزارها در چتِ ربات 🤖\n"
               f"{SEPARATOR}\n"
               + tip("روی دکمه‌ی زیر بزن تا باز شود 👇")),
        kb().row(web_app_btn("🚀 باز کردن مینی‌اپ", config.APP_URL))
             .row(btn("🏠 منوی اصلی", "nav:home")).build(),
    )


# --------------------------------------------------------------------------- #
# دریافت داده از اپ
# --------------------------------------------------------------------------- #
def on_web_app_data(ctx: Context) -> None:
    """پردازش ‎web_app_data‎ ارسال‌شده از مینی‌اپ."""
    try:
        data = json.loads(ctx.update.web_app_data or "{}")
    except json.JSONDecodeError:
        data = {}
    action = str(data.get("action") or "").strip()
    if not action:
        ctx.send("⚠️ داده‌ی نامعتبر از مینی‌اپ دریافت شد.")
        return
    ctx.track(f"app:{action}")
    handler = ACTIONS.get(action)
    if handler is None:
        ctx.send(
            f"🤔 بخش «{action}» هنوز در چت پشتیبانی نمی‌شود.\n"
            f"{SEPARATOR}\n"
            "از منوی اصلی ادامه بده 👇",
            main_menu(),
        )
        return
    handler(ctx, data)


# --------------------------------------------------------------------------- #
# عملیات‌ها
# --------------------------------------------------------------------------- #
def _weather(ctx: Context, data: dict) -> None:
    from .practical import show_weather
    show_weather(ctx, str(data.get("city") or data.get("text") or "تهران"))


def _market(ctx: Context, data: dict) -> None:
    from .practical import _report
    ctx.send("⏳ دارم نرخ‌ها رو می‌گیرم…")
    _report(ctx, "currency")


def _gold(ctx: Context, data: dict) -> None:
    from .practical import _report
    ctx.send("⏳ دارم نرخ طلا و سکه رو می‌گیرم…")
    _report(ctx, "gold")


def _crypto(ctx: Context, data: dict) -> None:
    from .practical import _report
    ctx.send("⏳ دارم قیمت ارزهای دیجیتال رو می‌گیرم…")
    _report(ctx, "crypto")


def _ai_chat(ctx: Context, data: dict) -> None:
    from ..services import ai
    text = str(data.get("text") or "").strip()
    if len(text) < 2:
        ctx.send("✍️ سوالی نوشته نشده!")
        return
    if not ctx.consume("ai_chat"):
        from .vip import upgrade_keyboard
        message, keyboard = ctx.limit_message("ai_chat")
        ctx.send(message, keyboard)
        return
    ctx.send("🤔 دارم فکر می‌کنم…")
    try:
        answer = ai.ask(text)
    except Exception as exc:
        from .common import fail
        fail(ctx, "app.ai_chat", exc,
             "🤖 سرویس هوش مصنوعی در دسترس نیست.\n"
             "اگر صاحب ربات هستی، کلید API را در تنظیمات بگذار.")
        return
    ctx.send(f"💬 {truncate(text, 60)}\n{SEPARATOR}\n{answer}",
             kb().row(btn("🤖 بخش هوش مصنوعی", "menu:ai"),
                      btn("🏠 منوی اصلی", "nav:home")).build())


def _ai_image(ctx: Context, data: dict) -> None:
    from ..services import ai
    prompt = str(data.get("prompt") or data.get("text") or "").strip()
    if len(prompt) < 3:
        ctx.send("✍️ یک توصیف کوتاه بنویس 🙏")
        return
    if not ctx.consume("ai_image"):
        from .vip import upgrade_keyboard
        message, keyboard = ctx.limit_message("ai_image")
        ctx.send(message, keyboard)
        return
    ctx.send("🎨 دارم تصویرت رو می‌سازم…")
    try:
        content = ai.image_bytes(prompt)
    except Exception as exc:
        from .common import fail
        fail(ctx, "app.ai_image", exc, "⚠️ ساخت تصویر در این لحظه ممکن نیست 🙏")
        return
    file_id = ctx.client.upload_bytes(content, "astra-ai.png", "Image")
    ctx.client.send_file(ctx.chat_id, file_id,
                         caption=f"🖼 {truncate(prompt, 70)}\n✨ آسترا",
                         file_type="Image",
                         inline_keypad=kb().row(btn("🎨 عکس بعدی", "ai:image"),
                                                btn("🏠 منوی اصلی", "nav:home")).build())


def _music(ctx: Context, data: dict) -> None:
    """جستجوی آهنگ با کیفیت و نوع خروجی انتخاب‌شده در مینی‌اپ."""
    from .music import do_music_search

    quality = str(data.get("quality") or "").strip()
    if quality in ("128", "192", "320"):
        if quality == "320" and not ctx.is_vip:
            quality = "192"            # ۳۲۰ فقط برای کاربران ویژه
        ctx.db.set_setting(f"quality:{ctx.sender_id}", quality)
    kind = str(data.get("kind") or "").strip()
    if kind in ("audio", "video"):
        ctx.db.set_setting(f"music_kind:{ctx.sender_id}", kind)

    ctx.update.text = str(data.get("query") or data.get("text") or "")
    do_music_search(ctx)


def _download(ctx: Context, data: dict) -> None:
    from .downloader import KINDS, detect_kind, do_download
    url = str(data.get("url") or data.get("text") or "").strip()
    kind = str(data.get("kind") or "").strip()
    if kind not in KINDS:
        kind = detect_kind(url) or "ytv"
    ctx.db.set_state(ctx.sender_id, "await_dl", {"kind": kind})
    ctx.update.text = url
    do_download(ctx)


def _qr(ctx: Context, data: dict) -> None:
    from .tools import qr_do
    ctx.update.text = str(data.get("text") or data.get("url") or "")
    qr_do(ctx)


def _tts(ctx: Context, data: dict) -> None:
    from .music import do_tts
    ctx.update.text = str(data.get("text") or "")
    do_tts(ctx)


def _ocr(ctx: Context, data: dict) -> None:
    ctx.set_state("await_ocr")
    ctx.send(
        header("🔍 استخراج متن از عکس",
               "حالا عکست رو همین‌جا بفرست تا متنش رو برات بنویسم 📷\n"
               f"{SEPARATOR}\n"
               + tip("عکس باید واضح باشد.")),
        kb().row(btn("❌ انصراف", "nav:back")).build(),
    )


def _radio(ctx: Context, data: dict) -> None:
    from .music import music_radio
    music_radio(ctx)


def _sticker(ctx: Context, data: dict) -> None:
    from .fun import sticker_menu
    sticker_menu(ctx)


def _playlist(ctx: Context, data: dict) -> None:
    from .music import music_playlist
    music_playlist(ctx)


def _group(ctx: Context, data: dict) -> None:
    from .group import group_menu
    group_menu(ctx)


def _vip(ctx: Context, data: dict) -> None:
    from .vip import vip_menu
    vip_menu(ctx)


def _support(ctx: Context, data: dict) -> None:
    from .help import help_support
    help_support(ctx)


def _joke(ctx: Context, data: dict) -> None:
    from .fun import joke
    joke(ctx)


def _profile(ctx: Context, data: dict) -> None:
    from .vip import vip_profile
    vip_profile(ctx)


ACTIONS = {
    "weather": _weather,
    "market": _market,
    "gold": _gold,
    "crypto": _crypto,
    "ai_chat": _ai_chat,
    "ai": _ai_chat,
    "ai_image": _ai_image,
    "image": _ai_image,
    "music": _music,
    "download": _download,
    "qr": _qr,
    "tts": _tts,
    "ocr": _ocr,
    "radio": _radio,
    "sticker": _sticker,
    "playlist": _playlist,
    "group": _group,
    "vip": _vip,
    "support": _support,
    "joke": _joke,
    "profile": _profile,
}
