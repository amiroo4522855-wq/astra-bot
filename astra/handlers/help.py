"""راهنما، درباره‌ی ربات و پشتیبانی."""
from __future__ import annotations

from .. import config
from ..core.context import Context
from ..core.keyboards import btn, kb, main_menu
from ..core.router import route, state
from ..core.utils import SEPARATOR, en_to_fa
from .common import enter, go, guarded, header, tip

GUIDE = [
    ("🎵 موزیک", "جستجو و دانلود آهنگ، پلی‌لیست، رادیو و تبدیل متن به ویس"),
    ("🤖 هوش مصنوعی", "چت، ساخت عکس، خلاصه‌سازی و ترجمه"),
    ("📥 دانلودر", "یوتیوب، اینستاگرام، تیک‌تاک، روبینو و پینترست"),
    ("🛠 ابزارها", "فونت‌ساز، QR، کوتاه‌کننده، OCR، ماشین‌حساب، ساعت"),
    ("🌤 کاربردی", "آب‌وهوا، ارز، طلا و سکه، ارز دیجیتال"),
    ("🎮 سرگرمی", "جوک، شعر، فال حافظ، بازی و چالش روزانه"),
    ("⚙️ مدیریت گروه", "خوش‌آمدگویی، ضد لینک، ضد اسپم، اخطار و آمار"),
    ("💎 عضویت ویژه", "حذف محدودیت‌ها و امکانات بیشتر"),
]

COMMANDS = [
    ("/start", "شروع و نمایش منوی اصلی"),
    ("/help", "راهنمای استفاده"),
    ("/id", "نمایش شناسه‌ی شما"),
    ("/vip", "وضعیت و خرید اشتراک"),
    ("/dooz", "❌⭕️ بازی دوز (۴ سطح + دونفره)"),
    ("/anon", "🕵️ چت ناشناس و ساخت لینک"),
    ("/stop · /block · /reveal", "بستن، بلاک و افشای هویت در چت ناشناس"),
    ("/admin", "پنل مدیریت (فقط ادمین)"),
    ("/warn · /ban · /unwarn", "مدیریت کاربران گروه"),
    ("/grant <شناسه> <روز>", "اعطای اشتراک (ادمین)"),
]


# --------------------------------------------------------------------------- #
# منو
# --------------------------------------------------------------------------- #
@route("menu:help")
@guarded("help.menu")
def help_menu(ctx: Context) -> None:
    enter(ctx, "menu:help")
    keyboard = (
        kb()
        .row(btn("📖 راهنمای بخش‌ها", "help:guide"), btn("📋 دستورات", "help:commands"))
        .row(btn("💬 پشتیبانی", "help:support"), btn("🤖 درباره آسترا", "help:about"))
        .nav()
    )
    ctx.answer(
        header("ℹ️ راهنما و پشتیبانی",
               "هر سوالی داری اینجاست؛ اگر نبود، پشتیبانی جواب می‌ده 💬\n"
               f"{SEPARATOR}\n"
               + tip("می‌توانی مستقیم بنویسی: «آب و هوا تهران» یا «قیمت دلار»")),
        keyboard.build(),
    )


@route("help:guide")
@guarded("help.guide")
def help_guide(ctx: Context) -> None:
    enter(ctx, "help:guide")
    lines = [header("📖 راهنمای بخش‌ها", "هر بخش چه کاری انجام می‌دهد؟"), SEPARATOR]
    lines += [f"{emoji_title}\n    {desc}" for emoji_title, desc in GUIDE]
    lines.append(SEPARATOR)
    lines.append(tip("روی هر بخش در منوی اصلی بزن و شروع کن ✨"))
    ctx.answer("\n".join(lines),
               kb().row(btn("ℹ️ راهنما", "menu:help"), btn("🏠 منوی اصلی", "nav:home")).build())


@route("help:commands")
@guarded("help.commands")
def help_commands(ctx: Context) -> None:
    enter(ctx, "help:commands")
    lines = [header("📋 دستورات ربات", "این‌ها را می‌توانی تایپ کنی 👇"), SEPARATOR]
    lines += [f"▫️ {cmd} — {desc}" for cmd, desc in COMMANDS]
    lines.append(SEPARATOR)
    lines.append(tip("بیشتر کارها با دکمه‌ها هم انجام می‌شود 😉"))
    ctx.answer("\n".join(lines),
               kb().row(btn("ℹ️ راهنما", "menu:help"), btn("🏠 منوی اصلی", "nav:home")).build())


@route("help:about")
@guarded("help.about")
def help_about(ctx: Context) -> None:
    enter(ctx, "help:about")
    ctx.answer(
        header(f"🤖 درباره {config.BOT_NAME}",
               f"▫️ نسخه: {config.BOT_VERSION}\n"
               f"▫️ نام کاربری: @{config.BOT_USERNAME}\n"
               f"▫️ شعار: {config.BOT_TAGLINE}\n"
               f"{SEPARATOR}\n"
               "آسترا یک دستیار چندکاره است:\n"
               "موزیک، هوش مصنوعی، دانلودر، ابزارهای روزمره،\n"
               "سرگرمی و مدیریت گروه — یک‌جا ✨\n"
               f"{SEPARATOR}\n"
               "ساخته‌شده با ❤️ و پایتون"),
        kb().row(btn("💬 پشتیبانی", "help:support"), btn("💎 عضویت ویژه", "menu:vip"))
             .row(btn("🏠 منوی اصلی", "nav:home")).build(),
    )


@route("help:support")
@guarded("help.support")
def help_support(ctx: Context) -> None:
    enter(ctx, "help:support")
    ctx.set_state("await_support")
    ctx.answer(
        header("💬 پشتیبانی",
               "پیامت رو بنویس؛ مستقیم به ادمین می‌رسه 📨\n"
               f"{SEPARATOR}\n"
               "هرچه دقیق‌تر بنویسی، سریع‌تر جواب می‌گیری 🙏\n"
               "برای لغو بنویس: «لغو»"),
        kb().row(btn("❌ لغو", "menu:help")).build(),
    )


@state("await_support")
@guarded("help.support_send")
def support_send(ctx: Context) -> None:
    text = (ctx.text or "").strip()
    if text in ("لغو", "❌ لغو", "/cancel"):
        ctx.clear_state()
        go(ctx, "menu:help")
        return
    if len(text) < 3:
        ctx.send("✍️ پیامت خیلی کوتاه است؛ کمی توضیح بده 🙏")
        return
    ctx.clear_state()
    delivered = False
    for admin_id in config.ADMIN_IDS:
        try:
            ctx.client.send_message(
                admin_id,
                f"📨 پیام پشتیبانی جدید\n{SEPARATOR}\n"
                f"▫️ از: {ctx.sender_id}\n"
                f"{SEPARATOR}\n{text[:1000]}",
                kb().row(btn("↩️ پاسخ", f"admin:reply:{ctx.sender_id}")).build(),
            )
            delivered = True
        except Exception as exc:
            ctx.log_error("support.send", exc)
    tail = ("به‌زودی پاسخ می‌گیریم 💬" if delivered
            else "⚠️ ادمین فعلاً آنلاین نیست؛ کمی بعد دوباره امتحان کن.")
    ctx.send(
        f"✅ پیامت به پشتیبانی ارسال شد.\n"
        f"{SEPARATOR}\n"
        f"{tail}",
        kb().row(btn("ℹ️ راهنما", "menu:help"), btn("🏠 منوی اصلی", "nav:home")).build(),
    )


@route("admin:reply", prefix=True)
@guarded("help.admin_reply")
def admin_reply(ctx: Context) -> None:
    """ادمین می‌تواند به پیام پشتیبانی پاسخ بدهد."""
    if not ctx.is_admin:
        return
    target = (ctx.arg or "").strip()
    if not target:
        ctx.answer("⚠️ کاربر مشخص نیست.")
        return
    ctx.set_state("await_admin_reply", {"target": target})
    ctx.answer(
        header("↩️ پاسخ به کاربر",
               "متن پاسخ را بنویس تا برای کاربر ارسال شود ✍️"),
        kb().row(btn("❌ لغو", "admin:panel")).build(),
    )


@state("await_admin_reply")
@guarded("help.admin_reply_send")
def admin_reply_send(ctx: Context) -> None:
    if not ctx.is_admin:
        return
    text = (ctx.text or "").strip()
    if text in ("لغو", "❌ لغو", "/cancel"):
        ctx.clear_state()
        go(ctx, "admin:panel")
        return
    _, data = ctx.get_state()
    target = data.get("target", "")
    ctx.clear_state()
    try:
        ctx.client.send_message(target, f"💬 پاسخ پشتیبانی\n{SEPARATOR}\n{text[:1500]}")
        ctx.send("✅ پاسخ ارسال شد.")
    except Exception as exc:
        ctx.log_error("support.reply", exc)
        ctx.send("⚠️ ارسال پاسخ ناموفق بود.")
