"""شروع، منوی اصلی، ناوبری و دستورات پایه."""
from __future__ import annotations

import time

from .. import config
from ..core.context import Context
from ..core.keyboards import btn, home_keyboard, kb, main_menu
from ..core.router import command, find_callback_route, route
from ..core.utils import SEPARATOR, en_to_fa, jalali_date, short_id
from .common import guarded, header, vip_line

START_TIME = time.time()


def _welcome_text(ctx: Context) -> str:
    name = ctx.update.first_name or "دوست من"
    lines = [
        f"✨ سلام {name} عزیز، به «{config.BOT_NAME}» خوش اومدی!",
        f"{SEPARATOR}",
        "من اینجام که کارهات رو یک‌جا راه بندازم 😎",
        "",
        "🎵 موزیک و رادیو آنلاین",
        "🤖 چت و تصویرساز هوش مصنوعی",
        "📥 دانلود از یوتیوب، اینستا، تیک‌تاک…",
        "🛠 ابزارهای روزمره و 🌤 آب‌وهوا و ارز",
        "🎮 سرگرمی و ⚙️ مدیریت گروه",
        f"{SEPARATOR}",
        vip_line(ctx),
        "───────────────",
        "👇 یکی از بخش‌ها رو انتخاب کن،",
        "یا مستقیم بنویس: «آب و هوا تهران» 🌤",
    ]
    return "\n".join(lines)


def _group_welcome_text(ctx: Context) -> str:
    return (
        f"✨ سلام! {config.BOT_NAME} به گروه شما پیوست 🎉\n"
        f"{SEPARATOR}\n"
        "برای مدیریت گروه: دستور /admin یا دکمه‌ی زیر رو بزن.\n"
        "فقط ادمین‌های گروه می‌تونن تنظیمات رو تغییر بدن 👮‍♂️"
    )


# --------------------------------------------------------------------------- #
# شروع
# --------------------------------------------------------------------------- #
@command("/start", "/شروع", "/begin")
@route("nav:start")
@guarded("start")
def start(ctx: Context) -> None:
    """پیام خوش‌آمدگویی + منوی اصلی."""
    if not ctx.is_private:
        ctx.send(_group_welcome_text(ctx),
                 kb().row(btn("⚙️ تنظیمات گروه", "menu:group")).build())
        return

    # لینک عمیقِ چت ناشناس: ‎/start a<token>‎
    arg = (ctx.arg or "").strip()
    if arg.startswith("a") and len(arg) > 6:
        from .anon import join_request
        join_request(ctx, arg[1:])
        return

    text = _welcome_text(ctx)
    menu = main_menu()
    try:
        chat_row = ctx.db.anon_active_chat(ctx.sender_id)
    except Exception:
        chat_row = None
    if chat_row:
        text += ("\n───────────────\n"
                 "💬 شما در یک «گفتگوی ناشناس» هستید؛ پیام‌هایتان مستقیم می‌رود 🕵️")
        menu["rows"].insert(0, {"buttons": [
            {"id": "anon:status", "type": "Simple", "button_text": "💬 ادامه چت ناشناس"},
            {"id": "anon:stop", "type": "Simple", "button_text": "🚪 بستن چت"}]})
    ctx.send(text, menu, chat_keypad=home_keyboard())


@route("nav:home")
@guarded("home")
def home(ctx: Context) -> None:
    """برگشت به منوی اصلی."""
    ctx.clear_state()
    if not ctx.is_private:
        ctx.answer("🏠 منوی اصلی:", main_menu())
        return
    ctx.send(
        f"🏠 منوی اصلی {config.BOT_NAME}\n{SEPARATOR}\n"
        "هر کاری داری از اینجا شروع کن 👇\n"
        f"───────────────\n{vip_line(ctx)}",
        main_menu(),
        chat_keypad=home_keyboard(),
    )


@route("nav:back")
@guarded("back")
def back(ctx: Context) -> None:
    """دکمه‌ی بازگشت: برمی‌گردد به منوی قبلی در پشته‌ی پیمایش."""
    ctx.clear_state()
    target = ctx.pop_nav()
    if target in ("nav:home", ""):
        home(ctx)
        return
    handler, _, arg = find_callback_route(target)
    if handler:
        ctx.arg = arg
        handler(ctx)
    else:
        home(ctx)


@route("nav:refresh")
@guarded("refresh")
def refresh(ctx: Context) -> None:
    handler, _, arg = find_callback_route(ctx.pop_nav())
    if handler:
        ctx.arg = arg
        handler(ctx)
    else:
        home(ctx)


# --------------------------------------------------------------------------- #
# دستورات کمکی
# --------------------------------------------------------------------------- #
@command("/help", "/راهنما", "/کمک")
@guarded("help_cmd")
def help_command(ctx: Context) -> None:
    from .help import help_menu
    help_menu(ctx)


@command("/id", "/من", "/me")
@guarded("id")
def my_id(ctx: Context) -> None:
    user = ctx.db.get_user(ctx.sender_id) or {}
    joined = user.get("joined_at") or int(time.time())
    ctx.send(
        f"🪪 شناسه‌ی شما در روبیکا\n{SEPARATOR}\n"
        f"▫️ شناسه: {ctx.sender_id}\n"
        f"▫️ کوتاه: {short_id(ctx.sender_id)}\n"
        f"▫️ نوع چت: {'خصوصی' if ctx.is_private else 'گروه'}\n"
        f"▫️ تاریخ عضویت: {jalali_date(joined, with_weekday=False)}\n"
        f"▫️ وضعیت: {vip_line(ctx)}",
        kb().row(btn("👤 پروفایل کامل", "vip:profile"),
                 btn("🏠 منوی اصلی", "nav:home")).build(),
    )


@command("/ping", "/وضعیت")
@guarded("ping")
def ping(ctx: Context) -> None:
    uptime = int(time.time() - START_TIME)
    hours, remainder = divmod(uptime, 3600)
    minutes, seconds = divmod(remainder, 60)
    ctx.send(
        f"🏓 پونگ!\n{SEPARATOR}\n"
        f"▫️ زمان روشن بودن: {en_to_fa(hours)} ساعت و {en_to_fa(minutes)} دقیقه\n"
        f"▫️ نسخه: {config.BOT_VERSION}\n"
        f"▫️ وضعیت: سالم و آماده ✅",
        kb().row(btn("🏠 منوی اصلی", "nav:home")).build(),
    )


@command("/admin", "/panel")
@guarded("admin_cmd")
def admin_command(ctx: Context) -> None:
    from .admin import admin_panel
    admin_panel(ctx)


@command("/vip", "/اشتراک")
@guarded("vip_cmd")
def vip_command(ctx: Context) -> None:
    from .vip import vip_menu
    vip_menu(ctx)
