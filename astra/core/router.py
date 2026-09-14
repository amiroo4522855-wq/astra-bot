"""سیستم مسیریابی (Router) ربات آسترا.

سه نوع مسیر داریم:
    ۱. کلیک روی دکمه    →  route("music:search")
    ۲. دستور            →  command("/start")
    ۳. متن آزاد/وضعیت   →  state("await_city") و text(predicate)

هیچ مسیری نباید بن‌بست باشد؛ در انتها یک fallback همیشه راهنمایی می‌دهد.
"""
from __future__ import annotations

import time
import traceback
from typing import Callable, Iterable

from .. import config
from .context import Context, Update
from .keyboards import home_keyboard, main_menu

# نوع‌های handler
Handler = Callable[[Context], None]

CALLBACK_ROUTES: dict[str, Handler] = {}
CALLBACK_PREFIXES: dict[str, Handler] = {}
COMMAND_ROUTES: dict[str, Handler] = {}
STATE_ROUTES: dict[str, Handler] = {}
TEXT_HANDLERS: list[tuple[Callable[[Context], bool], Handler]] = []
PRE_HANDLERS: list[Handler] = []


# --------------------------------------------------------------------------- #
# ثبت مسیرها
# --------------------------------------------------------------------------- #
def route(callback: str | Iterable[str], prefix: bool = False) -> Callable[[Handler], Handler]:
    """ثبت handler برای شناسه‌ی دکمه (callback)."""
    callbacks = [callback] if isinstance(callback, str) else list(callback)

    def decorator(func: Handler) -> Handler:
        for cb in callbacks:
            if prefix or cb.endswith(":"):
                CALLBACK_PREFIXES[cb.rstrip(":")] = func
            else:
                CALLBACK_ROUTES[cb] = func
        return func
    return decorator


def command(*commands: str) -> Callable[[Handler], Handler]:
    def decorator(func: Handler) -> Handler:
        for cmd in commands:
            COMMAND_ROUTES[cmd.lower()] = func
        return func
    return decorator


def state(*names: str) -> Callable[[Handler], Handler]:
    """ثبت handler برای وضعیت گفتگو (انتظار ورودی از کاربر)."""

    def decorator(func: Handler) -> Handler:
        for name in names:
            STATE_ROUTES[name] = func
        return func
    return decorator


def text(predicate: Callable[[Context], bool]) -> Callable[[Handler], Handler]:
    """ثبت handler برای متن آزاد (مثل «آب و هوا تهران»)."""
    def decorator(func: Handler) -> Handler:
        TEXT_HANDLERS.append((predicate, func))
        return func
    return decorator


def pre(func: Handler) -> Handler:
    """Handlerهایی که قبل از مسیریابی اجرا می‌شوند (مثل فیلترهای گروه)."""
    PRE_HANDLERS.append(func)
    return func


# --------------------------------------------------------------------------- #
# دیسپچ
# --------------------------------------------------------------------------- #
def split_callback(button_id: str) -> tuple[str, str]:
    """جدا کردن شناسه‌ی مسیر از آرگومان: ‎vip:buy:3‎ → ‎(vip:buy, 3)‎"""
    parts = (button_id or "").split(":")
    if len(parts) >= 3:
        return ":".join(parts[:2]), parts[2]
    return (button_id or ""), ""


def find_callback_route(button_id: str) -> tuple[Handler | None, str, str]:
    if button_id in CALLBACK_ROUTES:
        return CALLBACK_ROUTES[button_id], button_id, ""
    head, arg = split_callback(button_id)
    if head in CALLBACK_ROUTES:
        return CALLBACK_ROUTES[head], head, arg
    if head in CALLBACK_PREFIXES:
        return CALLBACK_PREFIXES[head], head, arg
    # جستجوی پیشوندی (مثل ‎vip:buy:6‎)
    parts = (button_id or "").split(":")
    for size in range(len(parts) - 1, 0, -1):
        prefix = ":".join(parts[:size])
        if prefix in CALLBACK_PREFIXES:
            return CALLBACK_PREFIXES[prefix], prefix, ":".join(parts[size:])
    return None, button_id, ""


def handle(ctx: Context) -> None:
    """اجرای کامل یک آپدیت با مدیریت خطا."""
    started = time.perf_counter()
    try:
        # --- پیش‌پردازش (مدیریت گروه، ضد اسپم و...) ---
        for func in PRE_HANDLERS:
            try:
                func(ctx)
                if ctx.update.kind == "__consumed__":
                    return
            except Exception as exc:                      # هر خطای اینجا نباید ربات را متوقف کند
                ctx.log_error(f"pre:{func.__name__}", exc)

        # --- ثبت کاربر ---
        if ctx.sender_id:
            ctx.db.touch_user(ctx.sender_id, ctx.update.first_name,
                              ctx.update.username, ctx.chat_type)

        # --- حالت تعمیر و نگهداری ---
        if config.MAINTENANCE_MODE and not ctx.is_admin:
            ctx.send(config.MAINTENANCE_TEXT)
            return

        # --- مسیریابی ---
        dispatch(ctx)

    except Exception as exc:                              # آخرین خط دفاعی
        ctx.log_error("dispatch", exc)
        traceback.print_exc()
        try:
            ctx.send(
                "😵‍💫 اوه! یه خطای پیش‌بینی‌نشده رخ داد.\n"
                "───────────────\n"
                "خطا ثبت شد و خیلی زود برطرف می‌شه.\n"
                "لطفاً دوباره امتحان کن یا از منوی اصلی ادامه بده 👇",
                main_menu(),
            )
        except Exception:
            pass
    finally:
        elapsed = (time.perf_counter() - started) * 1000
        if elapsed > 1500:                                # فقط درخواست‌های کند ثبت شوند
            ctx.db.log("SLOW", "dispatch", f"{elapsed:.0f} ms · {ctx.update.button_id or ctx.text[:40]}")


def dispatch(ctx: Context) -> None:
    """تعیین handler مناسب بر اساس نوع آپدیت."""
    update: Update = ctx.update

    # ۱) کلیک روی دکمه
    if update.kind == "callback" and update.button_id:
        handler, route_name, arg = find_callback_route(update.button_id)
        if handler:
            ctx.arg = arg
            ctx.track(f"cb:{route_name}")
            handler(ctx)
            return
        ctx.answer("🤔 این دکمه‌ی قدیمی دیگه کار نمی‌کنه!\nیک بار منو رو باز کن 👇", main_menu())
        return

    # ۲) رویدادهای سیستمی گروه
    if update.kind == "system":
        from ..handlers import group as group_handlers
        group_handlers.on_system_event(ctx)
        return

    # ۳) دستور
    if ctx.text.startswith("/"):
        parts = ctx.text.split()
        name = parts[0].split("@")[0].lower()
        handler = COMMAND_ROUTES.get(name)
        if handler:
            ctx.arg = " ".join(parts[1:])
            ctx.track(f"cmd:{name}")
            handler(ctx)
            return
        if ctx.is_private:
            ctx.send(
                "🤖 این دستور رو نمی‌شناسم!\n"
                "───────────────\n"
                "از منوی زیر انتخاب کن یا /help رو بزن 👇",
                main_menu(),
            )
        return

    # ۳.۵) داده‌ی ارسالی از مینی‌اپ (Telegram Web App)
    if update.web_app_data:
        from ..handlers.miniapp import on_web_app_data
        on_web_app_data(ctx)
        return

    # ۴) وضعیت فعال گفتگو (مثل انتظار برای نام شهر)
    current_state, data = ctx.get_state()
    if current_state:
        handler = STATE_ROUTES.get(current_state.split(":")[0]) or STATE_ROUTES.get(current_state)
        if handler:
            ctx.arg = current_state.split(":", 1)[1] if ":" in current_state else ""
            handler(ctx)
            return
        ctx.clear_state()                                  # وضعیت ناشناس پاک می‌شود

    # ۵) عکس/فایل (مثل OCR)
    if update.file_id and update.file_type.lower() in ("image", "photo"):
        from ..handlers import tools as tools_handlers
        if tools_handlers.handle_photo(ctx):
            return

    # ۶) متن آزاد و تشخیص نیت کاربر
    for predicate, handler in TEXT_HANDLERS:
        try:
            if predicate(ctx):
                handler(ctx)
                return
        except Exception as exc:
            ctx.log_error(f"text:{handler.__name__}", exc)

    # ۷) fallback
    from ..handlers.fallback import unknown
    unknown(ctx)
