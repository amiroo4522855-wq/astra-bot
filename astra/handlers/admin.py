"""پنل ادمین: آمار، مدیریت اشتراک‌ها، ارسال همگانی، لاگ و روشن/خاموش کردن بخش‌ها."""
from __future__ import annotations

import time

from .. import config
from ..core.context import Context
from ..core.keyboards import btn, kb, main_menu
from ..core.router import route, state
from ..core.utils import SEPARATOR, en_to_fa, jalali_date, short_id, truncate
from .common import enter, fail, go, guarded, header

PAGE_SIZE = 8


def guard_admin(ctx: Context) -> bool:
    if ctx.is_admin:
        return True
    ctx.answer("🚫 این بخش فقط برای ادمین ربات است.",
               kb().row(btn("🏠 منوی اصلی", "nav:home")).build())
    return False


def _uptime() -> str:
    from .start import START_TIME
    seconds = int(time.time() - START_TIME)
    hours, remainder = divmod(seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{en_to_fa(hours)} ساعت و {en_to_fa(minutes)} دقیقه"


# --------------------------------------------------------------------------- #
# پنل اصلی
# --------------------------------------------------------------------------- #
@route("admin:panel")
@guarded("admin.panel")
def admin_panel(ctx: Context) -> None:
    if not guard_admin(ctx):
        return
    enter(ctx, "admin:panel")
    keyboard = (
        kb()
        .row(btn("📊 آمار کلی", "admin:stats"), btn("💎 اشتراک‌ها", "admin:subs"))
        .row(btn("📣 ارسال همگانی", "admin:broadcast"), btn("🧾 رسیدهای در انتظار", "admin:payments"))
        .row(btn("🐛 لاگ خطاها", "admin:logs"), btn("🔌 بخش‌های ربات", "admin:toggles"))
        .row(btn("🔍 جستجوی کاربر", "admin:find"))
        .row(btn("🏠 منوی اصلی", "nav:home"))
        .build()
    )
    ctx.answer(
        header("👑 پنل مدیریت آسترا",
               f"▫️ زمان روشن بودن: {_uptime()}\n"
               f"▫️ نسخه: {config.BOT_VERSION}\n"
               f"{SEPARATOR}\n"
               "یک بخش را انتخاب کن 👇"),
        keyboard,
    )


# --------------------------------------------------------------------------- #
# آمار
# --------------------------------------------------------------------------- #
@route("admin:stats")
@guarded("admin.stats")
def admin_stats(ctx: Context) -> None:
    if not guard_admin(ctx):
        return
    enter(ctx, "admin:stats")
    usage = ctx.db.usage_stats(limit=10)
    lines = [
        header("📊 آمار ربات",
               f"▫️ کل کاربران: {en_to_fa(ctx.db.count_users())}\n"
               f"▫️ فعال در ۷ روز: {en_to_fa(ctx.db.active_users(7))}\n"
               f"▫️ فعال در ۳۰ روز: {en_to_fa(ctx.db.active_users(30))}\n"
               f"▫️ اعضای ویژه: {en_to_fa(ctx.db.count_vip())}"),
        SEPARATOR,
        "🔥 پرمصرف‌ترین بخش‌ها:",
    ]
    if usage:
        for key, count in usage:
            label = key.replace("cb:", "").replace("cmd:", "")
            lines.append(f"▫️ {label}: {en_to_fa(count)}")
    else:
        lines.append("هنوز آماری ثبت نشده 🌱")

    pending = len(ctx.db.pending_payments(limit=50))
    if pending:
        lines.append(SEPARATOR)
        lines.append(f"🧾 رسیدهای در انتظار: {en_to_fa(pending)}")

    ctx.answer("\n".join(lines),
               kb().row(btn("🔄 بروزرسانی", "admin:stats"), btn("👑 پنل", "admin:panel"))
                    .row(btn("🏠 منوی اصلی", "nav:home")).build())


# --------------------------------------------------------------------------- #
# ارسال همگانی
# --------------------------------------------------------------------------- #
@route("admin:broadcast")
@guarded("admin.broadcast")
def admin_broadcast(ctx: Context) -> None:
    if not guard_admin(ctx):
        return
    enter(ctx, "admin:broadcast")
    ctx.set_state("await_broadcast")
    ctx.answer(
        header("📣 ارسال همگانی",
               "پیامی که می‌خوای برای همه‌ی کاربران بره رو بنویس ✍️\n"
               f"{SEPARATOR}\n"
               "پشتیبانی: متن، ایموجی و لینک\n"
               "برای لغو بنویس: «لغو»"),
        kb().row(btn("❌ لغو", "admin:panel")).build(),
    )


@state("await_broadcast")
@guarded("admin.broadcast_do")
def admin_broadcast_send(ctx: Context) -> None:
    if not guard_admin(ctx):
        return
    text = (ctx.text or "").strip()
    if text in ("لغو", "❌ لغو", "/cancel"):
        ctx.clear_state()
        go(ctx, "admin:panel")
        return
    if len(text) < 2:
        ctx.send("✍️ متن پیام خیلی کوتاه است.")
        return
    ctx.clear_state()
    users = ctx.db.all_user_ids()
    sent = failed = 0
    ctx.send(f"📤 در حال ارسال به {en_to_fa(len(users))} کاربر…")
    for user_id in users:
        try:
            ctx.client.send_message(user_id, text)
            sent += 1
        except Exception:
            failed += 1
    ctx.send(
        f"✅ ارسال همگانی تمام شد\n{SEPARATOR}\n"
        f"▫️ ارسال موفق: {en_to_fa(sent)}\n"
        f"▫️ ناموفق: {en_to_fa(failed)}",
        kb().row(btn("👑 پنل", "admin:panel"), btn("🏠 منوی اصلی", "nav:home")).build(),
    )


# --------------------------------------------------------------------------- #
# مدیریت اشتراک‌ها و رسیدها
# --------------------------------------------------------------------------- #
@route("admin:subs")
@guarded("admin.subs")
def admin_subs(ctx: Context) -> None:
    if not guard_admin(ctx):
        return
    enter(ctx, "admin:subs")
    vips = ctx.db.vip_users()[:PAGE_SIZE]
    if not vips:
        ctx.answer("💎 هنوز عضو ویژه‌ای نداریم.",
                   kb().row(btn("👑 پنل", "admin:panel")).build())
        return
    lines = [header("💎 اعضای ویژه", f"تعداد کل: {en_to_fa(ctx.db.count_vip())}")]
    for user in vips:
        lines.append(f"▫️ {short_id(user['user_id'])} · "
                     f"{jalali_date(int(user['vip_until']), with_weekday=False)}")
    ctx.answer("\n".join(lines),
               kb().row(btn("🧾 رسیدها", "admin:payments"), btn("👑 پنل", "admin:panel"))
                    .row(btn("🏠 منوی اصلی", "nav:home")).build())


@route("admin:payments")
@guarded("admin.payments")
def admin_payments(ctx: Context) -> None:
    if not guard_admin(ctx):
        return
    enter(ctx, "admin:payments")
    payments = ctx.db.pending_payments(limit=PAGE_SIZE)
    if not payments:
        ctx.answer("🧾 رسید در انتظاری وجود ندارد ✅",
                   kb().row(btn("👑 پنل", "admin:panel")).build())
        return
    for payment in payments:
        plan = config.VIP_PLANS.get(payment["plan"], config.VIP_PLANS["1"])
        ctx.send(
            f"🧾 رسید #{en_to_fa(payment['id'])}\n{SEPARATOR}\n"
            f"▫️ کاربر: {short_id(payment['user_id'])}\n"
            f"▫️ پلن: {plan['label']} · {plan['price']}\n"
            f"▫️ زمان: {jalali_date(int(payment['created_at']), with_weekday=False)}\n"
            f"▫️ پیگیری: {truncate(payment.get('receipt') or '—', 60)}\n"
            f"{SEPARATOR}\n"
            f"شناسه کامل: {payment['user_id']}",
            kb().row(btn("✅ تأیید", f"admin:pay:{payment['id']}:ok"),
                     btn("❌ رد", f"admin:pay:{payment['id']}:no")).build(),
        )


@route("admin:pay", prefix=True)
@guarded("admin.pay")
def admin_pay_decide(ctx: Context) -> None:
    if not guard_admin(ctx):
        return
    try:
        payment_id_str, action = (ctx.arg or "").split(":", 1)
        payment_id = int(payment_id_str)
    except (ValueError, AttributeError):
        ctx.answer("⚠️ شناسه نامعتبر است.")
        return
    payment = ctx.db.get_payment(payment_id)
    if not payment:
        ctx.answer("⚠️ این رسید پیدا نشد.")
        return
    if action == "ok":
        plan = config.VIP_PLANS.get(payment["plan"], config.VIP_PLANS["1"])
        until = ctx.db.grant_vip(payment["user_id"], plan["days"])
        ctx.db.set_payment(payment_id, "approved")
        ctx.answer(f"✅ تأیید شد.\nاشتراک تا {jalali_date(until, with_weekday=False)} فعال است 💎")
        try:
            ctx.client.send_message(
                payment["user_id"],
                "🎉 رسیدت تأیید شد!\n"
                f"{SEPARATOR}\n"
                f"اشتراک ویژه تا {jalali_date(until, with_weekday=False)} فعال است 💎\n"
                "بدون محدودیت لذت ببر ♾",
                kb().row(btn("👤 پروفایل من", "vip:profile")).build(),
            )
        except Exception as exc:
            ctx.log_error("admin.notify_user", exc)
    else:
        ctx.db.set_payment(payment_id, "rejected")
        ctx.answer("❌ رد شد.")
        try:
            ctx.client.send_message(
                payment["user_id"],
                "😕 رسید پرداخت تأیید نشد.\n"
                f"{SEPARATOR}\n"
                "اگر مبلغ واریز شده، از بخش پشتیبانی پیام بده تا بررسی کنیم 💬",
            )
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# لاگ خطاها
# --------------------------------------------------------------------------- #
@route("admin:logs")
@guarded("admin.logs")
def admin_logs(ctx: Context) -> None:
    if not guard_admin(ctx):
        return
    enter(ctx, "admin:logs")
    level = (ctx.arg or "ERROR").strip()
    logs = ctx.db.recent_logs(level=None if level == "ALL" else level, limit=PAGE_SIZE)
    if not logs:
        ctx.answer(
            ("🎉 هیچ خطایی ثبت نشده!" if level == "ERROR" else "📭 لاگی وجود ندارد."),
            kb().row(btn("📋 همه لاگ‌ها", "admin:logs:ALL"),
                     btn("👑 پنل", "admin:panel")).build(),
        )
        return
    lines = [header("🐛 لاگ‌های اخیر", f"نوع: {level}")]
    for log in logs:
        lines.append(f"▫️ [{log['level']}] {log['where_']} — {truncate(log['message'], 70)}")
        lines.append(f"   🕓 {jalali_date(int(log['ts'] or 0), with_weekday=False)}")
    ctx.answer("\n".join(lines),
               kb().row(btn("⚠️ فقط خطاها", "admin:logs:ERROR"),
                        btn("📋 همه", "admin:logs:ALL"))
                    .row(btn("👑 پنل", "admin:panel"), btn("🏠 منوی اصلی", "nav:home"))
                    .build())


# --------------------------------------------------------------------------- #
# روشن/خاموش کردن بخش‌ها
# --------------------------------------------------------------------------- #
@route("admin:toggles")
@guarded("admin.toggles")
def admin_toggles(ctx: Context) -> None:
    if not guard_admin(ctx):
        return
    enter(ctx, "admin:toggles")
    keyboard = kb()
    for section, label in config.SECTION_LABELS.items():
        enabled = ctx.db.section_enabled(section)
        keyboard.row(btn(f"{'✅' if enabled else '⭕️'} {label}", f"admin:toggle:{section}"))
    keyboard.row(btn("👑 پنل", "admin:panel"), btn("🏠 منوی اصلی", "nav:home"))
    ctx.answer(header("🔌 وضعیت بخش‌ها",
                      "برای روشن/خاموش کردن هر بخش روی آن بزن 👇"), keyboard.build())


@route("admin:toggle", prefix=True)
@guarded("admin.toggle")
def admin_toggle(ctx: Context) -> None:
    if not guard_admin(ctx):
        return
    section = (ctx.arg or "").strip()
    if section not in config.SECTION_LABELS:
        ctx.answer("⚠️ بخش نامعتبر است.")
        return
    new_state = not ctx.db.section_enabled(section)
    ctx.db.set_section(section, new_state)
    ctx.answer(f"{'✅ روشن شد' if new_state else '⭕️ خاموش شد'}: "
               f"{config.SECTION_LABELS[section]}")
    admin_toggles(ctx)


# --------------------------------------------------------------------------- #
# جستجوی کاربر
# --------------------------------------------------------------------------- #
@route("admin:find")
@guarded("admin.find")
def admin_find(ctx: Context) -> None:
    if not guard_admin(ctx):
        return
    enter(ctx, "admin:find")
    ctx.set_state("await_find_user")
    ctx.answer(
        header("🔍 جستجوی کاربر",
               "شناسه کامل کاربر در روبیکا را بفرست (مثل ‎u0ABC...‎) 🔎"),
        kb().row(btn("❌ لغو", "admin:panel")).build(),
    )


@state("await_find_user")
@guarded("admin.find_do")
def admin_find_do(ctx: Context) -> None:
    if not guard_admin(ctx):
        return
    user_id = (ctx.text or "").strip()
    if user_id in ("لغو", "❌ لغو", "/cancel"):
        ctx.clear_state()
        go(ctx, "admin:panel")
        return
    ctx.clear_state()
    user = ctx.db.get_user(user_id)
    if not user:
        ctx.send("🤔 کاربری با این شناسه پیدا نشد.",
                 kb().row(btn("🔍 جستجوی دیگر", "admin:find"),
                          btn("👑 پنل", "admin:panel")).build())
        return
    ctx.send(
        f"👤 کاربر {short_id(user_id)}\n{SEPARATOR}\n"
        f"▫️ نام: {user.get('first_name') or '—'}\n"
        f"▫️ شناسه کامل: {user_id}\n"
        f"▫️ عضویت: {jalali_date(int(user.get('joined_at') or 0), with_weekday=False)}\n"
        f"▫️ اشتراک: {'💎 تا ' + jalali_date(int(user['vip_until']), with_weekday=False) if user['vip_until'] > time.time() else '🆓 رایگان'}\n"
        f"▫️ تعداد پیام: {en_to_fa(user.get('msg_count') or 0)}\n"
        f"▫️ پلی‌لیست: {en_to_fa(ctx.db.playlist_count(user_id))}",
        kb().row(btn("💎 ۳۰ روز", f"admin:grant:{user_id}:30"),
                 btn("💎 ۹۰ روز", f"admin:grant:{user_id}:90"))
             .row(btn("🚫 لغو اشتراک", f"admin:grant:{user_id}:0"))
             .row(btn("👑 پنل", "admin:panel")).build(),
    )


@route("admin:grant", prefix=True)
@guarded("admin.grant")
def admin_grant(ctx: Context) -> None:
    if not guard_admin(ctx):
        return
    parts = (ctx.arg or "").split(":")
    if len(parts) < 2:
        ctx.answer("⚠️ داده ناقص است.")
        return
    user_id = parts[0]
    try:
        days = int(parts[1])
    except ValueError:
        ctx.answer("⚠️ تعداد روز نامعتبر است.")
        return
    if days <= 0:
        ctx.db.revoke_vip(user_id)
        ctx.answer("🚫 اشتراک غیرفعال شد.")
        return
    until = ctx.db.grant_vip(user_id, days)
    ctx.answer(f"💎 اشتراک {en_to_fa(days)} روزه اعطا شد (تا "
               f"{jalali_date(until, with_weekday=False)})")
    try:
        ctx.client.send_message(
            user_id,
            f"🎉 اشتراک ویژه‌ی آسترا برای {en_to_fa(days)} روز برایت فعال شد 💎\n"
            f"▫️ انقضا: {jalali_date(until, with_weekday=False)}",
        )
    except Exception:
        pass
