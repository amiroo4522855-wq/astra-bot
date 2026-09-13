"""مدیریت گروه: خوش‌آمدگویی، ضد لینک، ضد اسپم، اخطار/بن، قفل و آمار.

این بخش هم در گروه و هم در پی‌وی کار می‌کند؛
در پی‌وی فقط راهنما نشان می‌دهد (تنظیمات باید داخل گروه انجام شود).
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from ..core.context import Context
from ..core.keyboards import btn, kb, main_menu
from ..core.router import command, pre, route, state
from ..core.utils import SEPARATOR, en_to_fa, jalali_date, short_id
from .common import enter, fail, go, guarded, header, section_closed, tip

# ضد اسپم: تعداد پیام در پنجره‌ی زمانی
SPAM_WINDOW = 6          # ثانیه
SPAM_MAX = 5             # تعداد پیام مجاز
_SPAM_TRACKER: dict[tuple[str, str], deque] = defaultdict(deque)

# نگاشت پیام → فرستنده (برای تشخیص ریپلای در دستورات ادمین)
_SENDERS: dict[tuple[str, str], str] = {}
_SENDER_ORDER: deque = deque(maxlen=2000)

# کش ادمین‌های گروه
_ADMIN_CACHE: dict[str, tuple[float, set[str]]] = {}
ADMIN_CACHE_TTL = 600  # ثانیه


# --------------------------------------------------------------------------- #
# ابزارها
# --------------------------------------------------------------------------- #
def remember_sender(chat_id: str, message_id: str, sender_id: str) -> None:
    if not message_id or not sender_id:
        return
    key = (chat_id, message_id)
    _SENDERS[key] = sender_id
    _SENDER_ORDER.append(key)
    while len(_SENDER_ORDER) > 2000:
        old = _SENDER_ORDER.popleft()
        _SENDERS.pop(old, None)


def sender_of(chat_id: str, message_id: str) -> str:
    return _SENDERS.get((chat_id, message_id), "")


def group_admins(ctx: Context, group_id: str) -> set[str]:
    """دریافت ادمین‌های گروه با کش؛ در صورت عدم دسترسی فقط ادمین‌های ربات."""
    now = time.time()
    cached = _ADMIN_CACHE.get(group_id)
    if cached and now - cached[0] < ADMIN_CACHE_TTL:
        return cached[1]
    admins = {str(a) for a in __import__("..config", fromlist=["x"]).ADMIN_IDS} \
        if False else set()
    from .. import config
    admins = {str(a) for a in config.ADMIN_IDS}
    try:
        raw = ctx.client.get_chat_administrators(group_id)
        for item in raw or []:
            member = (item.get("member") or item) if isinstance(item, dict) else {}
            identifier = str(member.get("user_id") or member.get("member_guid") or "")
            if identifier:
                admins.add(identifier)
    except Exception:
        pass
    _ADMIN_CACHE[group_id] = (now, admins)
    return admins


def is_group_admin(ctx: Context) -> bool:
    if ctx.is_admin:
        return True
    if not ctx.is_group:
        return False
    return ctx.sender_id in group_admins(ctx, ctx.chat_id)


def _settings_text(group: dict) -> str:
    def mark(value: bool) -> str:
        return "✅ روشن" if value else "⭕️ خاموش"
    return (
        f"▫️ پیام خوش‌آمد: {'تنظیم شده ✅' if group.get('welcome_text') else 'ندارد ⭕️'}\n"
        f"▫️ ضد لینک: {mark(bool(group.get('anti_link')))}\n"
        f"▫️ ضد اسپم: {mark(bool(group.get('anti_spam')))}\n"
        f"▫️ حذف فوروارد: {mark(bool(group.get('del_forward')))}\n"
        f"▫️ قفل گروه: {mark(bool(group.get('locked')))}\n"
        f"▫️ حداکثر اخطار: {en_to_fa(group.get('max_warn') or 3)}"
    )


# --------------------------------------------------------------------------- #
# پیش‌پردازش: فیلترهای گروه
# --------------------------------------------------------------------------- #
@pre
def group_moderation(ctx: Context) -> None:
    """فیلترهای خودکار گروه قبل از پردازش پیام."""
    if not ctx.is_group:
        return
    update = ctx.update
    if update.text.startswith("/"):
        return
    if update.button_id:
        return

    remember_sender(ctx.chat_id, update.message_id, ctx.sender_id)
    ctx.db.ensure_group(ctx.chat_id)
    ctx.db.bump_group_stat(ctx.chat_id, ctx.sender_id)

    group = ctx.db.get_group(ctx.chat_id) or {}
    admin = is_group_admin(ctx)

    # قفل گروه
    if group.get("locked") and not admin:
        if ctx.delete():
            return
    # حذف فوروارد
    if group.get("del_forward") and update.is_forwarded and not admin:
        ctx.delete()
        return
    # ضد لینک
    if group.get("anti_link") and not admin:
        text = update.text.lower()
        if any(token in text for token in ("http://", "https://", "t.me/", "rubika.ir/",
                                           "@", ".com", ".ir")):
            if ctx.delete():
                warns = ctx.db.add_warn(ctx.chat_id, ctx.sender_id, "ارسال لینک")
                ctx.send(f"🚫 لینک مجاز نیست!\n{SEPARATOR}\n"
                         f"⚠️ اخطار {en_to_fa(warns)} از {en_to_fa(group.get('max_warn') or 3)}")
                _escalate(ctx, warns, group)
            return
    # ضد اسپم
    if group.get("anti_spam") and not admin:
        key = (ctx.chat_id, ctx.sender_id)
        bucket = _SPAM_TRACKER[key]
        now = time.time()
        bucket.append(now)
        while bucket and now - bucket[0] > SPAM_WINDOW:
            bucket.popleft()
        if len(bucket) > SPAM_MAX:
            bucket.clear()
            warns = ctx.db.add_warn(ctx.chat_id, ctx.sender_id, "اسپم")
            ctx.delete()
            ctx.send(f"🛑 spam detected! کمی آروم‌تر 🙏\n{SEPARATOR}\n"
                     f"⚠️ اخطار {en_to_fa(warns)} از {en_to_fa(group.get('max_warn') or 3)}")
            _escalate(ctx, warns, group)


def _escalate(ctx: Context, warns: int, group: dict) -> None:
    """وقتی اخطارها پر شد، کاربر را اخراج می‌کند (در صورت دسترسی)."""
    limit = int(group.get("max_warn") or 3)
    if warns < limit:
        return
    ctx.db.reset_warn(ctx.chat_id, ctx.sender_id)
    try:
        ctx.client.ban_member(ctx.chat_id, ctx.sender_id)
        ctx.send("⛔️ این کاربر به دلیل دریافت اخطارهای متعدد حذف شد.")
    except Exception:
        ctx.send("⛔️ اخطارهای این کاربر پر شد.\n"
                 "برای حذف خودکار، ربات باید دسترسی ادمین داشته باشد.")


@pre
def remember_message(ctx: Context) -> None:
    """ذخیره‌ی فرستنده‌ی پیام برای ریپلای‌کردن ادمین‌ها."""
    if ctx.is_group and ctx.update.message_id:
        remember_sender(ctx.chat_id, ctx.update.message_id, ctx.sender_id)


# --------------------------------------------------------------------------- #
# منوی مدیریت گروه
# --------------------------------------------------------------------------- #
@route("menu:group")
@guarded("group.menu")
def group_menu(ctx: Context) -> None:
    if section_closed(ctx, "group"):
        return
    enter(ctx, "menu:group")

    if not ctx.is_group:
        ctx.answer(
            header("⚙️ مدیریت گروه",
                   "برای مدیریت گروه:\n"
                   f"{SEPARATOR}\n"
                   "۱. ربات را به گروه اضافه کن\n"
                   "۲. ربات را ادمین کن (حذف پیام و بن)\n"
                   "۳. داخل گروه دستور /admin را بزن 👮‍♂️\n"
                   f"{SEPARATOR}\n"
                   + tip("در ادامه می‌توانی خوش‌آمدگویی، ضد لینک، ضد اسپم و… را تنظیم کنی.")),
            kb().row(btn("🏠 منوی اصلی", "nav:home")).build(),
        )
        return

    ctx.db.ensure_group(ctx.chat_id)
    if not is_group_admin(ctx):
        ctx.answer("🔒 فقط ادمین‌های گروه می‌توانند تنظیمات را تغییر دهند.",
                   kb().row(btn("🏠 منوی اصلی", "nav:home")).build())
        return

    group = ctx.db.get_group(ctx.chat_id) or {}
    keyboard = (
        kb()
        .row(btn("🤝 پیام خوش‌آمد", "group:welcome"), btn("🚫 ضد لینک", "group:toggle:anti_link"))
        .row(btn("🛡 ضد اسپم", "group:toggle:anti_spam"), btn("🧹 حذف فوروارد", "group:toggle:del_forward"))
        .row(btn("🔒 قفل گروه", "group:toggle:locked"), btn("⚠️ سقف اخطار", "group:maxwarn"))
        .row(btn("📊 آمار گروه", "group:stats"))
        .nav()
    )
    ctx.answer(
        header("⚙️ مدیریت گروه", _settings_text(group) + "\n" + SEPARATOR +
               "\nبرای تغییر هر مورد روی دکمه‌اش بزن 👇"),
        keyboard.build(),
    )


@route("group:toggle", prefix=True)
@guarded("group.toggle")
def group_toggle(ctx: Context) -> None:
    if not ctx.is_group or not is_group_admin(ctx):
        ctx.answer("🔒 این تنظیم فقط برای ادمین‌های گروه است.")
        return
    field = (ctx.arg or "").strip()
    if field not in ("anti_link", "anti_spam", "del_forward", "locked"):
        ctx.answer("⚠️ تنظیم نامعتبر است.")
        return
    group = ctx.db.get_group(ctx.chat_id) or {}
    new_value = 0 if group.get(field) else 1
    ctx.db.set_group(ctx.chat_id, **{field: new_value})
    labels = {"anti_link": "ضد لینک", "anti_spam": "ضد اسپم",
              "del_forward": "حذف فوروارد", "locked": "قفل گروه"}
    ctx.answer(f"{'✅ روشن شد' if new_value else '⭕️ خاموش شد'} — {labels[field]}")
    group_menu(ctx)


@route("group:maxwarn")
@guarded("group.maxwarn")
def group_maxwarn(ctx: Context) -> None:
    if not ctx.is_group or not is_group_admin(ctx):
        ctx.answer("🔒 فقط ادمین‌های گروه.")
        return
    enter(ctx, "group:maxwarn")
    keyboard = kb()
    keyboard.grid([(f"{en_to_fa(n)} اخطار", f"group:setwarn:{n}") for n in (2, 3, 5, 10)], per_row=2)
    keyboard.nav()
    ctx.answer(header("⚠️ سقف اخطار",
                      "بعد از چند اخطار کاربر حذف شود؟ 👇"), keyboard.build())


@route("group:setwarn", prefix=True)
@guarded("group.setwarn")
def group_setwarn(ctx: Context) -> None:
    try:
        value = int(ctx.arg or "3")
    except ValueError:
        value = 3
    ctx.db.set_group(ctx.chat_id, max_warn=value)
    ctx.answer(f"✅ سقف اخطار روی {en_to_fa(value)} تنظیم شد.")
    group_menu(ctx)


# --------------------------------------------------------------------------- #
# خوش‌آمدگویی
# --------------------------------------------------------------------------- #
@route("group:welcome")
@guarded("group.welcome")
def group_welcome(ctx: Context) -> None:
    if not ctx.is_group or not is_group_admin(ctx):
        ctx.answer("🔒 فقط ادمین‌های گروه.")
        return
    enter(ctx, "group:welcome")
    group = ctx.db.get_group(ctx.chat_id) or {}
    current = group.get("welcome_text") or ""
    ctx.answer(
        header("🤝 پیام خوش‌آمد",
               (f"متن فعلی:\n{current}\n{SEPARATOR}\n" if current else
                "هنوز پیامی تنظیم نشده 🌱\n" + SEPARATOR + "\n") +
               "می‌توانی متن دلخواهت را بنویسی.\n"
               "متغیرها: {name} نام کاربر · {group} نام گروه"),
        kb().row(btn("✍️ تنظیم متن", "group:welcomeset"), btn("🧹 حذف", "group:welcomeclear"))
             .nav().build(),
    )


@route("group:welcomeset")
@guarded("group.welcome_set")
def group_welcome_set(ctx: Context) -> None:
    if not is_group_admin(ctx):
        return
    enter(ctx, "group:welcomeset")
    ctx.set_state("await_welcome_text")
    ctx.answer(
        header("✍️ متن خوش‌آمدگویی",
               "متن خوش‌آمد رو بفرست 🎉\n"
               f"{SEPARATOR}\n"
               + tip("مثال: سلام {name} عزیز به {group} خوش اومدی 🎊")),
        kb().row(btn("❌ انصراف", "nav:back")).build(),
    )


@state("await_welcome_text")
@guarded("group.welcome_save")
def group_welcome_save(ctx: Context) -> None:
    text = (ctx.text or "").strip()
    if text in ("❌ انصراف", "/cancel"):
        ctx.clear_state()
        go(ctx, "group:welcome")
        return
    ctx.db.set_group(ctx.chat_id, welcome_text=text[:500])
    ctx.clear_state()
    ctx.send(
        f"✅ پیام خوش‌آمد ذخیره شد.\n{SEPARATOR}\nنمونه:\n{text.replace('{name}', 'علی').replace('{group}', 'گروه').replace('{group}', 'گروه')}",
        kb().row(btn("⚙️ مدیریت گروه", "menu:group"), btn("🏠 منوی اصلی", "nav:home")).build(),
    )


@route("group:welcomeclear")
@guarded("group.welcome_clear")
def group_welcome_clear(ctx: Context) -> None:
    ctx.db.set_group(ctx.chat_id, welcome_text="")
    ctx.answer("🧹 پیام خوش‌آمد حذف شد.")
    group_menu(ctx)


# --------------------------------------------------------------------------- #
# آمار
# --------------------------------------------------------------------------- #
@route("group:stats")
@guarded("group.stats")
def group_stats(ctx: Context) -> None:
    if not ctx.is_group:
        ctx.answer("📊 این بخش داخل گروه معنا دارد 🙂")
        return
    total = ctx.db.group_members_count(ctx.chat_id)
    top = ctx.db.group_top(ctx.chat_id, limit=5)
    lines = [
        header("📊 آمار گروه",
               f"▫️ تعداد کاربران فعال ثبت‌شده: {en_to_fa(total)}"),
        SEPARATOR,
        "🏆 فعال‌ترین‌ها:",
    ]
    for index, row in enumerate(top, start=1):
        lines.append(f"{en_to_fa(index)}. {short_id(row['user_id'])} · {en_to_fa(row['messages'])} پیام")
    if not top:
        lines.append("هنوز آماری ثبت نشده 🌱")
    ctx.answer("\n".join(lines),
               kb().row(btn("⚙️ مدیریت گروه", "menu:group"),
                        btn("🏠 منوی اصلی", "nav:home")).build())


# --------------------------------------------------------------------------- #
# دستورات ادمین
# --------------------------------------------------------------------------- #
def _target_from(ctx: Context) -> str:
    """تشخیص کاربر هدف از ریپلای یا آرگومنت دستور."""
    if ctx.arg:
        return ctx.arg.strip().split()[0]
    raw = ctx.update.raw or {}
    update = raw.get("update", raw) or {}
    message = update.get("new_message") or update.get("message") or {}
    reply_id = str(message.get("reply_to_message_id") or "")
    if reply_id:
        return sender_of(ctx.chat_id, reply_id)
    return ""


@command("/warn", "/اخطار")
@guarded("group.warn")
def warn_command(ctx: Context) -> None:
    if not ctx.is_group or not is_group_admin(ctx):
        ctx.send("🔒 فقط ادمین‌های گروه.")
        return
    target = _target_from(ctx)
    if not target:
        ctx.send("⚠️ روی پیام کاربر ریپلای کن و /warn بفرست، یا /warn <شناسه> را بنویس.")
        return
    group = ctx.db.get_group(ctx.chat_id) or {}
    count = ctx.db.add_warn(ctx.chat_id, target, "دستور ادمین")
    ctx.send(f"⚠️ اخطار ثبت شد\n{SEPARATOR}\n"
             f"▫️ کاربر: {short_id(target)}\n"
             f"▫️ تعداد: {en_to_fa(count)} از {en_to_fa(group.get('max_warn') or 3)}")
    _escalate(ctx, count, group)


@command("/unwarn", "/حذف_اخطار")
@guarded("group.unwarn")
def unwarn_command(ctx: Context) -> None:
    if not ctx.is_group or not is_group_admin(ctx):
        ctx.send("🔒 فقط ادمین‌های گروه.")
        return
    target = _target_from(ctx)
    if not target:
        ctx.send("⚠️ روی پیام کاربر ریپلای کن یا شناسه بده.")
        return
    ctx.db.reset_warn(ctx.chat_id, target)
    ctx.send("✅ اخطارهای کاربر پاک شد.")


@command("/ban", "/بن")
@guarded("group.ban")
def ban_command(ctx: Context) -> None:
    if not ctx.is_group or not is_group_admin(ctx):
        ctx.send("🔒 فقط ادمین‌های گروه.")
        return
    target = _target_from(ctx)
    if not target:
        ctx.send("⚠️ روی پیام کاربر ریپلای کن یا /ban <شناسه> بنویس.")
        return
    try:
        ctx.client.ban_member(ctx.chat_id, target)
        ctx.send(f"⛔️ کاربر {short_id(target)} از گروه حذف شد.")
    except Exception as exc:
        fail(ctx, "group.ban", exc,
             "⚠️ نتوانستم کاربر را حذف کنم.\n"
             "ربات باید دسترسی «حذف کاربر» داشته باشد.")


@command("/unban")
@guarded("group.unban")
def unban_command(ctx: Context) -> None:
    if not ctx.is_group or not is_group_admin(ctx):
        return
    target = _target_from(ctx)
    if not target:
        ctx.send("⚠️ شناسه کاربر را بنویس: /unban <شناسه>")
        return
    try:
        ctx.client.unban_member(ctx.chat_id, target)
        ctx.send("✅ کاربر آزاد شد.")
    except Exception:
        ctx.send("⚠️ امکان آزادسازی وجود ندارد.")


# --------------------------------------------------------------------------- #
# رویدادهای سیستمی
# --------------------------------------------------------------------------- #
def on_system_event(ctx: Context) -> None:
    """ورود/خروج ربات یا عضو جدید در گروه."""
    event = (ctx.update.text or "").lower()
    if "added" in event:
        ctx.db.ensure_group(ctx.chat_id)
        group = ctx.db.get_group(ctx.chat_id) or {}
        welcome = (group.get("welcome_text") or "").replace("{name}", "دوست عزیز") \
                                                    .replace("{group}", "گروه")
        if welcome:
            ctx.send(f"🎉 {welcome}")
    if "removed" in event:
        ctx.db.set_group(ctx.chat_id, locked=0)
