"""بخش دانلودر: یوتیوب، اینستاگرام، تیک‌تاک، روبینو و پینترست."""
from __future__ import annotations

from pathlib import Path

from .. import config
from ..core.context import Context
from ..core.keyboards import btn, kb, main_menu
from ..core.router import route, state
from ..core.utils import SEPARATOR, en_to_fa, format_size, is_url
from ..services import media
from .common import enter, go, guarded, header, section_closed, tip

# kind → (عنوان، راهنما، نوع خروجی)
KINDS = {
    "ytv": ("▶️ یوتیوب (ویدیو)", "لینک ویدیوی یوتیوب رو بفرست 🎬", "video"),
    "yta": ("🎵 یوتیوب (صدا)", "لینک آهنگ یا ویدیو رو بفرست 🎧", "audio"),
    "ig": ("📸 اینستاگرام", "لینک پست، ریلز یا استوری رو بفرست 📸", "generic"),
    "tt": ("🎵 تیک‌تاک", "لینک ویدیوی تیک‌تاک رو بفرست 🕺", "generic"),
    "rubino": ("💠 روبینو", "لینک پست اینستاگرام رو بفرست 💠", "generic"),
    "pin": ("📌 پینترست", "لینک پین یا ویدیو رو بفرست 📌", "generic"),
}

DOMAIN_HINTS = (
    ("youtu", "ytv"), ("instagram.com", "ig"), ("tiktok.com", "tt"),
    ("pinterest.com", "pin"), ("pin.it", "pin"), ("rubino", "rubino"),
)


def detect_kind(url: str) -> str | None:
    lowered = url.lower()
    for needle, kind in DOMAIN_HINTS:
        if needle in lowered:
            return kind
    return None


# --------------------------------------------------------------------------- #
# منو
# --------------------------------------------------------------------------- #
@route("menu:dl")
@guarded("dl.menu")
def dl_menu(ctx: Context) -> None:
    if section_closed(ctx, "downloader"):
        return
    enter(ctx, "menu:dl")
    keyboard = (
        kb()
        .row(btn(KINDS["ytv"][0], "dl:ytv"), btn(KINDS["yta"][0], "dl:yta"))
        .row(btn(KINDS["ig"][0], "dl:ig"), btn(KINDS["tt"][0], "dl:tt"))
        .row(btn(KINDS["rubino"][0], "dl:rubino"), btn(KINDS["pin"][0], "dl:pin"))
        .row(btn("🎚 کیفیت ویدیو", "dl:quality"))
        .nav()
    )
    ctx.answer(
        header("📥 بخش دانلودر",
               "لینک بده، فایلش رو تحویل بگیر 📦\n"
               f"{SEPARATOR}\n"
               + tip("سایت‌های پشتیبانی‌شده: یوتیوب، اینستاگرام، تیک‌تاک، پینترست و صدها سایت دیگر")),
        keyboard.build(),
    )


def user_height(ctx: Context) -> int:
    saved = ctx.db.get_setting(f"height:{ctx.sender_id}", "")
    if saved in ("360", "480", "720", "1080"):
        return int(saved)
    return 1080 if ctx.is_vip else 720


@route("dl:quality")
@guarded("dl.quality")
def dl_quality(ctx: Context) -> None:
    enter(ctx, "dl:quality")
    current = str(user_height(ctx))
    options = [("📱 360p", "360"), ("📺 480p", "480"), ("💻 720p", "720"),
               ("🖥 1080p", "1080")]
    keyboard = kb()
    keyboard.grid([(f"{'✅ ' if q == current else ''}{label}", f"dl:q:{q}")
                   for label, q in options], per_row=2)
    keyboard.nav()
    ctx.answer(
        header("🎚 کیفیت ویدیو",
               f"کیفیت فعلی: {current}p\n{SEPARATOR}\n"
               + ("💎 کیفیت ۱۰۸۰ مخصوص اعضای ویژه است." if not ctx.is_vip
                  else "💎 اشتراک ویژه داری؛ ۱۰۸۰ هم آزاد است.")),
        keyboard.build(),
    )


@route("dl:q", prefix=True)
@guarded("dl.set_quality")
def dl_set_quality(ctx: Context) -> None:
    value = (ctx.arg or "720").strip()
    if value == "1080" and not ctx.is_vip:
        ctx.answer("🔒 کیفیت 1080p مخصوص اعضای ویژه است 💎",
                   kb().row(btn("💎 دیدن پلن‌ها", "menu:vip"),
                            btn("🔙 بازگشت", "nav:back")).build())
        return
    if value not in ("360", "480", "720", "1080"):
        value = "720"
    ctx.db.set_setting(f"height:{ctx.sender_id}", value)
    ctx.answer(f"✅ کیفیت روی {value}p تنظیم شد 🎬")
    go(ctx, "menu:dl")


# --------------------------------------------------------------------------- #
# جریان دانلود
# --------------------------------------------------------------------------- #
@route("dl", prefix=True)
@guarded("dl.pick")
def dl_pick(ctx: Context) -> None:
    kind = (ctx.arg or "").strip()
    if kind not in KINDS:
        kind = "ytv"
    if not media.available():
        ctx.answer(
            "🚧 بخش دانلود روی این سرور فعال نیست.\n"
            f"{SEPARATOR}\n"
            "نیاز به نصب ابزار yt-dlp است.\n"
            "اگر صاحب ربات هستی، README را بخوان 🛠",
            kb().row(btn("🏠 منوی اصلی", "nav:home")).build(),
        )
        return
    enter(ctx, f"dl:{kind}")
    title, guide, _ = KINDS[kind]
    ctx.set_state("await_dl", {"kind": kind})
    ctx.answer(
        header(f"{title} — دانلود",
               f"{guide}\n{SEPARATOR}\n"
               + tip("لینک باید با http شروع شود.")),
        kb().row(btn("❌ انصراف", "nav:back")).build(),
    )


@state("await_dl")
@guarded("dl.do")
def do_download(ctx: Context) -> None:
    url = (ctx.text or "").strip()
    if url in ("❌ انصراف", "/cancel", "لغو"):
        ctx.clear_state()
        go(ctx, "menu:dl")
        return
    if not is_url(url):
        ctx.send("🔗 این یک لینک معتبر نیست!\n"
                 "لینک باید این شکلی باشه: https://...\n"
                 f"{SEPARATOR}\n"
                 "یه بار دیگه بفرست یا انصراف بده 🙏")
        return
    if not ctx.consume("download"):
        from .vip import upgrade_keyboard
        message, keyboard = ctx.limit_message("download")
        ctx.send(message, keyboard)
        return

    _, data = ctx.get_state()
    kind = data.get("kind") or detect_kind(url) or "ytv"
    ctx.clear_state()
    title, _, mode = KINDS[kind]
    ctx.send(f"⏳ {title}: در حال دریافت فایل…")

    try:
        if mode == "video":
            path = media.download_video(url, max_height=user_height(ctx))
            file_type = "Video"
        elif mode == "audio":
            path = media.download_audio(url, bitrate="192")
            file_type = "Music"
        else:
            path = media.download_generic(url)
            file_type = "Video"
    except Exception as exc:
        ctx.send(
            "😕 نتونستم این لینک رو دانلود کنم.\n"
            f"{SEPARATOR}\n"
            "ممکنه لینک خصوصی، حذف‌شده یا از سایتی باشد که پشتیبانی نمی‌شود.\n"
            "یک لینک دیگر امتحان کن 🙏",
            kb().row(btn("🔄 تلاش دوباره", f"dl:{kind}"),
                     btn("🏠 منوی اصلی", "nav:home")).build(),
        )
        ctx.log_error("dl.do", exc)
        return

    size = path.stat().st_size
    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    if size > limit:
        media.cleanup(path)
        ctx.send(
            f"📦 حجم فایل ({format_size(size)}) بیش از حد مجاز است.\n"
            f"{SEPARATOR}\n"
            "لینک کوتاه‌تر یا کیفیت پایین‌تر را امتحان کن.",
            kb().row(btn("🎚 تغییر کیفیت", "dl:quality"),
                     btn("🏠 منوی اصلی", "nav:home")).build(),
        )
        return

    try:
        file_id = ctx.client.upload_path(path, file_type)
        ctx.send(f"📤 در حال ارسال ({format_size(size)})…")
        ctx.client.send_file(
            ctx.chat_id, file_id,
            caption=f"✅ دانلود شد\n{SEPARATOR}\n📦 حجم: {format_size(size)}\n✨ آسترا",
            file_type=file_type,
            inline_keypad=kb().row(btn("🔄 دانلود دیگر", "menu:dl"),
                                   btn("🏠 منوی اصلی", "nav:home")).build(),
        )
    finally:
        media.cleanup(path)
