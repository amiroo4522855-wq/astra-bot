"""سیستم عضویت ویژه: پلن‌ها، پروفایل، خرید و مدیریت اشتراک."""
from __future__ import annotations

import time

from .. import config
from ..core.context import Context
from ..core.keyboards import btn, kb, main_menu
from ..core.router import command, route, state
from ..core.utils import SEPARATOR, en_to_fa, jalali_date, short_id
from .common import enter, fail, go, guarded, header, tip


def upgrade_keyboard() -> dict:
    """کیبوردِ تشویقی که در پیام‌های محدودیت استفاده می‌شود."""
    return (
        kb()
        .row(btn("💎 دیدن پلن‌ها", "menu:vip"), btn("👤 پروفایل من", "vip:profile"))
        .row(btn("🏠 منوی اصلی", "nav:home"))
        .build()
    )


# --------------------------------------------------------------------------- #
# منو
# --------------------------------------------------------------------------- #
@route("menu:vip")
@guarded("vip.menu")
def vip_menu(ctx: Context) -> None:
    if ctx.db.section_enabled("vip") is False:
        ctx.answer("🚧 این بخش موقتاً غیرفعال است.")
        return
    enter(ctx, "menu:vip")
    lines = [header("💎 عضویت ویژه آسترا",
                    "با اشتراک ویژه، آسترا رو بدون محدودیت داشته باش ♾"),
             SEPARATOR]
    for plan_id, plan in config.VIP_PLANS.items():
        lines.append(f"{plan['emoji']} {plan['label']} — {plan['price']}")
    lines.append(SEPARATOR)
    lines.append("🎁 امکانات ویژه:")
    lines += [f"▫️ {perk}" for perk in config.VIP_PERKS]
    lines.append(SEPARATOR)
    if ctx.is_vip:
        lines.append(f"✅ اشتراک فعال داری: {ctx.vip_remaining} باقی‌مانده")
    else:
        lines.append("🆓 در حال حاضر روی حساب رایگان هستی.")

    keyboard = kb()
    keyboard.grid([(f"{config.VIP_PLANS[p]['emoji']} خرید {config.VIP_PLANS[p]['label']}",
                    f"vip:buy:{p}") for p in config.VIP_PLANS], per_row=3)
    keyboard.row(btn("👤 پروفایل من", "vip:profile"))
    keyboard.nav()
    ctx.answer("\n".join(lines), keyboard.build())


# --------------------------------------------------------------------------- #
# پروفایل
# --------------------------------------------------------------------------- #
@route("vip:profile")
@guarded("vip.profile")
def vip_profile(ctx: Context) -> None:
    enter(ctx, "vip:profile")
    user = ctx.db.get_user(ctx.sender_id) or {}
    joined = int(user.get("joined_at") or time.time())
    expiry = ctx.vip_until
    used_today = {key: ctx.db.daily_count(ctx.sender_id, key)
                  for key in config.FREE_LIMITS}
    usage_lines = []
    for key, limit in config.FREE_LIMITS.items():
        if limit <= 0:
            continue
        used = used_today.get(key, 0)
        usage_lines.append(f"▫️ {key}: {en_to_fa(used)} از {en_to_fa(limit)}")

    lines = [
        header("👤 پروفایل من", f"▫️ شناسه کوتاه: {short_id(ctx.sender_id)}"),
        f"▫️ نوع حساب: {'💎 عضو ویژه' if ctx.is_vip else '🆓 رایگان'}",
    ]
    if ctx.is_vip:
        lines.append(f"▫️ انقضا: {jalali_date(expiry, with_weekday=False)}")
        lines.append(f"▫️ باقی‌مانده: {ctx.vip_remaining}")
    lines.append(f"▫️ تاریخ عضویت: {jalali_date(joined, with_weekday=False)}")
    lines.append(f"▫️ آهنگ‌های پلی‌لیست: {en_to_fa(ctx.db.playlist_count(ctx.sender_id))}")
    if usage_lines:
        lines.append(SEPARATOR)
        lines.append("📊 مصرف امروز:")
        lines += usage_lines
    if not ctx.is_vip:
        lines.append(SEPARATOR)
        lines.append(tip("با عضویت ویژه، محدودیت‌ها حذف می‌شود ♾"))

    keyboard = kb()
    if ctx.is_vip:
        keyboard.row(btn("➕ تمدید اشتراک", "menu:vip"))
    else:
        keyboard.row(btn("💎 خرید اشتراک", "menu:vip"))
    keyboard.nav()
    ctx.answer("\n".join(lines), keyboard.build())


# --------------------------------------------------------------------------- #
# خرید
# --------------------------------------------------------------------------- #
@route("vip:buy", prefix=True)
@guarded("vip.buy")
def vip_buy(ctx: Context) -> None:
    plan_id = (ctx.arg or "1").strip()
    plan = config.VIP_PLANS.get(plan_id)
    if not plan:
        ctx.answer("⚠️ پلن نامعتبر است.")
        return
    enter(ctx, f"vip:buy:{plan_id}")
    payment_id = ctx.db.add_payment(ctx.sender_id, plan_id, plan["price"])
    ctx.set_state("await_receipt", {"plan": plan_id, "payment_id": payment_id})

    lines = [
        header(f"{plan['emoji']} خرید اشتراک {plan['label']}",
               f"▫️ مبلغ: {plan['price']}\n"
               f"▫️ مدت: {en_to_fa(plan['days'])} روز"),
        SEPARATOR,
        "💳 پرداخت:",
        f"شماره کارت: {config.CARD_NUMBER}",
        f"{config.CARD_OWNER}",
        SEPARATOR,
        "بعد از واریز، عکس رسید یا شماره پیگیری را همین‌جا بفرست 📸",
        "ادمین تأیید می‌کند و اشتراکت فعال می‌شود ✅",
    ]
    ctx.answer("\n".join(lines),
               kb().row(btn("❌ انصراف", "nav:back")).build())


@state("await_receipt")
@guarded("vip.receipt")
def vip_receipt(ctx: Context) -> None:
    text = (ctx.text or "رسید تصویری").strip()
    if text in ("❌ انصراف", "/cancel"):
        ctx.clear_state()
        go(ctx, "menu:vip")
        return
    _, data = ctx.get_state()
    payment_id = data.get("payment_id", 0)
    plan_id = data.get("plan", "1")
    receipt = text[:300]
    if ctx.update.file_id:
        receipt = f"[تصویر] {receipt}" if text == "رسید تصویری" else text
    ctx.db.set_payment(payment_id, "pending", receipt)
    ctx.clear_state()

    plan = config.VIP_PLANS.get(plan_id, config.VIP_PLANS["1"])
    ctx.send(
        "✅ رسید شما ثبت شد!\n"
        f"{SEPARATOR}\n"
        f"▫️ پلن: {plan['label']}\n"
        f"▫️ مبلغ: {plan['price']}\n"
        "▫️ وضعیت: در انتظار تأیید ⏳\n"
        f"{SEPARATOR}\n"
        "به‌محض تأیید ادمین، اشتراکت فعال می‌شه و بهت اطلاع می‌دم 💎",
        kb().row(btn("👤 پروفایل من", "vip:profile"),
                 btn("🏠 منوی اصلی", "nav:home")).build(),
    )

    # اطلاع به ادمین‌ها
    from .. import config as cfg
    for admin_id in cfg.ADMIN_IDS:
        try:
            ctx.client.send_message(
                admin_id,
                f"🧾 رسید جدید\n{SEPARATOR}\n"
                f"▫️ کاربر: {short_id(ctx.sender_id)}\n"
                f"▫️ پلن: {plan['label']} ({plan['price']})\n"
                f"▫️ کد پیگیری: {receipt[:80]}\n"
                f"▫️ شناسه کاربر: {ctx.sender_id}",
                kb().row(btn("✅ تأیید", f"admin:pay:{payment_id}:ok"),
                         btn("❌ رد", f"admin:pay:{payment_id}:no")).build(),
            )
        except Exception as exc:
            ctx.log_error("vip.notify_admin", exc)


# --------------------------------------------------------------------------- #
# دستور ادمین برای اعطای اشتراک
# --------------------------------------------------------------------------- #
@command("/grant")
@guarded("vip.grant")
def grant_command(ctx: Context) -> None:
    if not ctx.is_admin:
        return
    parts = (ctx.arg or "").split()
    if len(parts) < 2:
        ctx.send("فرمت: /grant <شناسه کاربر> <تعداد روز>\nمثال: /grant u0ABC123 90")
        return
    user_id, days = parts[0], parts[1]
    try:
        days = int(days)
    except ValueError:
        ctx.send("تعداد روز باید عدد باشد.")
        return
    until = ctx.db.grant_vip(user_id, days)
    ctx.send(f"💎 اشتراک {en_to_fa(days)} روزه به {short_id(user_id)} داده شد.\n"
             f"▫️ انقضا: {jalali_date(until, with_weekday=False)}")
    try:
        ctx.client.send_message(user_id,
                                f"🎉 تبریک! اشتراک ویژه‌ی آسترا برای {en_to_fa(days)} روز فعال شد 💎\n"
                                f"▫️ انقضا: {jalali_date(until, with_weekday=False)}\n"
                                "حالا بدون محدودیت از همه بخش‌ها استفاده کن ♾")
    except Exception:
        pass


@command("/revoke")
@guarded("vip.revoke")
def revoke_command(ctx: Context) -> None:
    if not ctx.is_admin:
        return
    user_id = (ctx.arg or "").strip().split()
    if not user_id:
        ctx.send("فرمت: /revoke <شناسه کاربر>")
        return
    ctx.db.revoke_vip(user_id[0])
    ctx.send(f"🚫 اشتراک {short_id(user_id[0])} غیرفعال شد.")
