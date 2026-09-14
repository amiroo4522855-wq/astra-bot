"""چت ناشناسِ آسترا 🕵️

طرز کار:
    ۱. کاربر یک «لینک ناشناس» می‌سازد و برای هر کس می‌فرستد
    ۲. طرف مقابل با باز کردن لینک، مستقیم به صاحب لینک وصل می‌شود
    ۳. پیام‌ها از طریق ربات ردوبدل می‌شود؛ هیچ‌کدام هویت دیگری را نمی‌فهمند
    ۴. هر لحظه می‌توان چت را بست، طرف را بلاک کرد یا لینک را باطل کرد

امنیت:
    • هویت (نام، نام‌کاربری، شناسه) هرگز فاش نمی‌شود مگر با «افشای دوطرفه»
    • پیام‌های فورواردی بازارسال نمی‌شوند (نشت هویت)
    • محدودیت ارسال (ضد اسپم)، ابطال لینک، بلاک و گزارش
    • همه‌ی پیام‌ها فقط از مسیر ربات عبور می‌کنند و ذخیره‌ی محتوایی نداریم
"""
from __future__ import annotations

import time

from .. import config
from ..core.context import Context
from ..core.keyboards import btn, kb, main_menu, url_btn
from ..core.router import command, route, state
from ..core.utils import SEPARATOR, en_to_fa
from .common import enter, guarded, header, tip

LINK_HOURS = 24
MAX_LEN = 2000
FLOOD_WINDOW = 20          # ثانیه
FLOOD_MAX = 25             # پیام
_RATE: dict[str, list[float]] = {}

CLOSE_WORDS = ("🚪 بستن چت", "/stop", "/end", "بستن", "خروج", "پایان")
BLOCK_WORDS = ("🚫 بلاک", "/block")
REVEAL_WORDS = ("🪪 افشای هویت", "/reveal")
REPORT_WORDS = ("🚩 گزارش", "/report")
STATUS_WORDS = ("📊 وضعیت", "/status")
HOME_WORDS = ("🏠 منوی اصلی", "/start", "/home")


# --------------------------------------------------------------------------- #
# ابزارها
# --------------------------------------------------------------------------- #
def invite_url(ctx: Context, token: str) -> str:
    """ساخت لینک دعوتِ عمیق (Deep Link)."""
    username = (ctx.db.get_setting("bot_username", "") or config.BOT_USERNAME or "").lstrip("@")
    base = f"https://t.me/{username}" if username else "https://t.me/"
    return f"{base}?start=a{token}"


def chat_keypad() -> dict:
    """کیبورد ثابتِ پایین صفحه در هنگام چت."""
    from ..core.keyboards import chat_keypad as _chat

    return _chat([
        [("🚪 بستن چت", "🚪 بستن چت"), ("🚫 بلاک", "🚫 بلاک")],
        [("🪪 افشای هویت", "🪪 افشای هویت"), ("🚩 گزارش", "🚩 گزارش")],
        [("📊 وضعیت", "📊 وضعیت"), ("🏠 منوی اصلی", "🏠 منوی اصلی")],
    ])


def _msg_id(result: dict | None) -> str:
    """استخراج شناسه‌ی پیام از پاسخِ تلگرام/روبیکا."""
    if not isinstance(result, dict):
        return ""
    inner = result.get("result") or result.get("data") or result
    if isinstance(inner, dict):
        for key in ("message_id", "id"):
            if inner.get(key):
                return str(inner[key])
    return ""


def _flood(user_id: str) -> bool:
    now = time.time()
    stamps = [t for t in _RATE.get(user_id, []) if now - t < FLOOD_WINDOW]
    stamps.append(now)
    _RATE[user_id] = stamps
    return len(stamps) > FLOOD_MAX


def _blocked(ctx: Context, a: str, b: str) -> bool:
    """آیا بین این دو نفر بلاکی (از هر طرف) وجود دارد؟"""
    return (ctx.db.anon_is_blocked(str(a), str(b))
            or ctx.db.anon_is_blocked(str(b), str(a)))


def _partner(chat_row: dict, user_id: str) -> str:
    return str(chat_row["user_b"]) if str(chat_row["user_a"]) == str(user_id) \
        else str(chat_row["user_a"])


def _identity(ctx: Context, user_id: str) -> str:
    """نمایش هویت (فقط وقتی دو طرف موافقت کرده باشند)."""
    user = ctx.db.get_user(str(user_id)) or {}
    name = (user.get("first_name") or "").strip()
    username = (user.get("username") or "").strip()
    if not name and not username:
        return f"👤 کاربر #{str(user_id)[-6:]}"
    if not name:
        return f"👤 @{username}"
    return f"👤 {name}" + (f" (@{username})" if username else "")


def _finish(ctx: Context, chat_row: dict, reason: str, notify_both: bool = True) -> None:
    """بستن چت و آگاه‌سازی دو طرف."""
    ctx.db.anon_close_chat(int(chat_row["id"]))
    partner = _partner(chat_row, ctx.sender_id)
    ctx.db.set_state(str(ctx.sender_id), "", {})
    ctx.db.set_state(partner, "", {})
    ctx.send(f"{reason}", main_menu())
    if notify_both:
        try:
            ctx.client.send_message(partner,
                                    f"🚪 چت ناشناس بسته شد\\n{SEPARATOR}\\n"
                                    "طرف مقابل از گفتگو خارج شد.\\n"
                                    "هر وقت خواستی می‌توانی یک لینک تازه بسازی 🔗",
                                    inline_keypad=kb()
                                    .row(btn("🔗 لینک تازه", "anon:new"))
                                    .row(btn("🏠 منوی اصلی", "nav:home")).build())
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# منوی اصلی چت ناشناس
# --------------------------------------------------------------------------- #
@route(("menu:anon", "fun:anon"))
@command("/anon", "/ناشناس", "/chat")
@guarded("anon.menu")
def anon_menu(ctx: Context) -> None:
    enter(ctx, "menu:anon")
    if not ctx.is_private:
        ctx.answer("🕵️ چت ناشناس فقط در گفتگوی خصوصی با ربات کار می‌کند.\n"
                   "بیا پی‌وی 👇",
                   kb().row(btn("🏠 منوی اصلی", "nav:home")).build())
        return

    chat_row = ctx.db.anon_active_chat(ctx.sender_id)
    if chat_row:
        active_chat_panel(ctx, chat_row)
        return

    counts = ctx.db.anon_count()
    ctx.answer(
        header("🕵️ چت ناشناس",
               "یک لینک می‌سازی، برای هر کس می‌فرستی،\n"
               "و هر دو طرف «بدون افشای هویت» چت می‌کنید 🔒\n"
               f"{SEPARATOR}\n"
               "▪️ هیچ‌کس شماره، نام یا آیدی تو را نمی‌بیند\n"
               "▪️ هر لحظه می‌توانی چت را ببندی یا طرف را بلاک کنی\n"
               "▪️ افشای هویت فقط با «رضایت هر دو نفر» ممکن است\n"
               f"{SEPARATOR}\n"
               f"🌐 اکنون: {en_to_fa(counts['open'])} گفتگوی فعال"),
        kb().row(btn("🔗 ساخت لینک ناشناس", "anon:new"),
                 btn("📋 لینک‌های من", "anon:links"))
             .row(btn("🚫 لیست بلاک", "anon:blocks"),
                  btn("🛡 امنیت و راهنما", "anon:help"))
             .row(btn("🎮 سرگرمی", "menu:fun"), btn("🏠 منوی اصلی", "nav:home"))
             .build(),
    )


def active_chat_panel(ctx: Context, chat_row: dict) -> None:
    """پنلِ گفتگوی فعال (برای /start و منو)."""
    started = int(chat_row.get("started") or 0)
    minutes = max(1, int((time.time() - started) / 60)) if started else 1
    ctx.answer(
        header("💬 چت ناشناس فعال",
               "شما در حال گفتگو با یک نفر به‌صورت ناشناس هستید 🕵️\n"
               f"{SEPARATOR}\n"
               f"⏱ شروع گفتگو: {en_to_fa(minutes)} دقیقه پیش\n"
               "🔒 هویت شما نزد طرف مقابل مخفی است\n"
               f"{SEPARATOR}\n"
               + tip("برای پاسخ دادن، روی پیام او «ریپلای» بزن ↩️")),
        kb().row(btn("🚪 بستن چت", "anon:stop"), btn("🚫 بلاک طرف مقابل", "anon:block"))
             .row(btn("🪪 افشای هویت", "anon:reveal"), btn("🚩 گزارش", "anon:report"))
             .row(btn("📊 وضعیت", "anon:status"), btn("🏠 منوی اصلی", "nav:home"))
             .build(),
    )


# --------------------------------------------------------------------------- #
# ساخت و مدیریت لینک
# --------------------------------------------------------------------------- #
@route("anon:new")
@guarded("anon.new")
def anon_new(ctx: Context) -> None:
    if not ctx.is_private:
        ctx.answer("🔗 ساخت لینک فقط در گفتگوی خصوصی ممکن است 🙏",
                   kb().row(btn("🏠 منوی اصلی", "nav:home")).build())
        return
    if ctx.db.anon_active_chat(ctx.sender_id):
        ctx.answer("💬 شما هم‌اکنون در یک گفتگو هستید؛\n"
                   "برای لینک جدید، اول چت فعلی را ببند 🚪",
                   kb().row(btn("🚪 بستن چت", "anon:stop"),
                            btn("📊 وضعیت", "anon:status"))
                        .row(btn("🏠 منوی اصلی", "nav:home")).build())
        return

    token = ctx.db.anon_create_link(ctx.sender_id, hours=LINK_HOURS)
    link = invite_url(ctx, token)
    share = ("https://t.me/share/url?url=" + link.replace(":", "%3A").replace("/", "%2F")
             + "&text=" + "بیا+ناشناس+چت+کنیم+🕵️")
    ctx.send(
        header("🔗 لینک چت ناشناس شما",
               f"‎{link}‎\n"
               f"{SEPARATOR}\n"
               f"⏳ اعتبار: {en_to_fa(LINK_HOURS)} ساعت\n"
               "🔒 با باز کردن این لینک، فرد مستقیماً با شما وصل می‌شود\n"
               "و هیچ‌کدام هویت هم را نخواهید فهمید.\n"
               f"{SEPARATOR}\n"
               + tip("هر وقت خواستی می‌توانی این لینک را باطل کنی.")),
        kb().row(url_btn("📤 ارسال لینک", share),
                 btn("🚫 ابطال لینک", f"anon:revoke:{token}"))
             .row(btn("🔄 لینک جدید", "anon:new"), btn("📋 لینک‌های من", "anon:links"))
             .row(btn("🕵️ چت ناشناس", "menu:anon"), btn("🏠 منوی اصلی", "nav:home"))
             .build(),
    )


@route("anon:revoke", prefix=True)
@guarded("anon.revoke")
def anon_revoke(ctx: Context) -> None:
    token = (ctx.arg or "").strip()
    link = ctx.db.anon_link(token)
    if not link or str(link["owner"]) != str(ctx.sender_id):
        ctx.answer("🤔 این لینک پیدا نشد یا مال شما نیست.",
                   kb().row(btn("🕵️ چت ناشناس", "menu:anon")).build())
        return
    ctx.db.anon_set_status(token, "banned")
    chat_row = ctx.db.anon_active_chat(ctx.sender_id)
    if chat_row and str(chat_row["token"]) == str(token):
        _finish(ctx, chat_row, "🚫 لینک باطل و گفتگو بسته شد.")
        return
    ctx.answer(
        header("🚫 لینک باطل شد",
               "این لینک دیگر کار نمی‌کند و هیچ‌کس نمی‌تواند با آن وصل شود 🔒\n"
               f"{SEPARATOR}\n"
               + tip("هر وقت خواستی یک لینک تازه بساز.")),
        kb().row(btn("🔗 لینک جدید", "anon:new"), btn("📋 لینک‌های من", "anon:links"))
             .row(btn("🕵️ چت ناشناس", "menu:anon"), btn("🏠 منوی اصلی", "nav:home"))
             .build(),
    )


@route("anon:links")
@guarded("anon.links")
def anon_links(ctx: Context) -> None:
    links = ctx.db.anon_owner_links(ctx.sender_id, limit=8)
    if not links:
        ctx.answer("📋 هنوز لینکی نساخته‌ای.\n اولین لینک را بساز 👇",
                   kb().row(btn("🔗 ساخت لینک", "anon:new"))
                        .row(btn("🕵️ چت ناشناس", "menu:anon"),
                             btn("🏠 منوی اصلی", "nav:home")).build())
        return

    labels = {"active": "🟢 فعال", "used": "🔵 استفاده‌شده", "banned": "🔴 باطل‌شده"}
    keyboard = kb()
    for link in links:
        status = labels.get(link["status"], link["status"])
        age = max(1, int((time.time() - int(link["created"] or 0)) / 3600))
        keyboard.row(btn(f"{status} · {en_to_fa(age)} ساعت پیش", f"anon:revoke:{link['token']}"))
    keyboard.row(btn("🔗 لینک جدید", "anon:new"))
    keyboard.row(btn("🕵️ چت ناشناس", "menu:anon"), btn("🏠 منوی اصلی", "nav:home"))
    ctx.answer(
        header("📋 لینک‌های شما",
               "روی هر لینک بزنی «باطل» می‌شود 🚫\n"
               f"{SEPARATOR}\n"
               + tip("لینک‌ها بعد از ۲۴ ساعت خودبه‌خود منقضی می‌شوند.")),
        keyboard.build(),
    )


# --------------------------------------------------------------------------- #
# پیوستن با لینک
# --------------------------------------------------------------------------- #
def join_request(ctx: Context, token: str) -> None:
    """نمایش تأییدیه برای کسی که لینک را باز کرده است."""
    link = ctx.db.anon_link(token)
    if not link:
        ctx.send("🤔 این لینک معتبر نیست یا منقضی شده.\n"
                 "از صاحب لینک بخواه یک لینک تازه بفرستد 🔗",
                 kb().row(btn("🏠 منوی اصلی", "nav:home")).build())
        return
    if link["status"] == "banned":
        ctx.send("🚫 این لینک توسط صاحبش باطل شده است.",
                 kb().row(btn("🏠 منوی اصلی", "nav:home")).build())
        return
    if int(link["expires"] or 0) < time.time():
        ctx.db.anon_set_status(token, "expired")
        ctx.send("⌛️ این لینک منقضی شده است.\n"
                 "یک لینک تازه بخواه 🔗",
                 kb().row(btn("🏠 منوی اصلی", "nav:home")).build())
        return
    if str(link["owner"]) == str(ctx.sender_id):
        ctx.send("🙃 این لینکِ خودته!\n"
                 "آن را برای کسی بفرست تا با تو ناشناس چت کند 🕵️",
                 kb().row(url_btn("📤 ارسال لینک", invite_url(ctx, token)))
                      .row(btn("🔗 لینک جدید", "anon:new"),
                           btn("🏠 منوی اصلی", "nav:home")).build())
        return
    if (_blocked(ctx, str(link["owner"]), str(ctx.sender_id))):
        ctx.send("⛔️ امکان برقراری گفتگو با این شخص وجود ندارد.",
                 kb().row(btn("🏠 منوی اصلی", "nav:home")).build())
        return

    ctx.send(
        header("🕵️ دعوت به چت ناشناس",
               "یک نفر برایت لینک ناشناس فرستاده 🤫\n"
               f"{SEPARATOR}\n"
               "▪️ اگر وصل شوی، می‌توانید ناشناس چت کنید\n"
               "▪️ هویت هیچ‌کدام فاش نمی‌شود\n"
               "▪️ هر لحظه می‌توانی چت را ببندی یا طرف را بلاک کنی\n"
               f"{SEPARATOR}\n"
               + tip("فقط در صورتی وصل شو که این شخص را می‌شناسی.")),
        kb().row(btn("✅ وصل شو", f"anon:join:{token}"), btn("❌ انصراف", "nav:home"))
             .build(),
    )


@route("anon:join", prefix=True)
@guarded("anon.join")
def anon_join(ctx: Context) -> None:
    token = (ctx.arg or "").strip()
    link = ctx.db.anon_link(token)
    if not link or link["status"] not in ("active", "used"):
        ctx.answer("⌛️ این لینک دیگر قابل استفاده نیست.",
                   kb().row(btn("🏠 منوی اصلی", "nav:home")).build())
        return
    if int(link["expires"] or 0) < time.time():
        ctx.answer("⌛️ این لینک منقضی شده است.",
                   kb().row(btn("🏠 منوی اصلی", "nav:home")).build())
        return
    owner = str(link["owner"])
    guest = str(ctx.sender_id)
    if owner == guest or _blocked(ctx, owner, guest):
        ctx.answer("⛔️ امکان برقراری گفتگو وجود ندارد.",
                   kb().row(btn("🏠 منوی اصلی", "nav:home")).build())
        return

    # بستن گفتگوهای قبلیِ هر دو نفر (هر نفر فقط یک گفتگوی فعال)
    for user_id in (owner, guest):
        old = ctx.db.anon_active_chat(user_id)
        if old:
            ctx.db.anon_close_chat(int(old["id"]))
            other = _partner(old, user_id)
            ctx.db.set_state(other, "", {})
            try:
                ctx.client.send_message(
                    other, "🚪 گفتگوی قبلی به‌دلیل شروع گفتگوی جدید بسته شد.",
                    inline_keypad=kb().row(btn("🏠 منوی اصلی", "nav:home")).build())
            except Exception:
                pass

    ctx.db.anon_use_link(token, guest)
    chat_id = ctx.db.anon_open_chat(token, owner, guest)
    ctx.db.set_state(owner, "anon_talk", {"chat": chat_id})
    ctx.db.set_state(guest, "anon_talk", {"chat": chat_id})

    panel = kb().row(btn("🚪 بستن چت", "anon:stop"), btn("🚫 بلاک", "anon:block")) \
                .row(btn("🪪 افشای هویت", "anon:reveal"), btn("🚩 گزارش", "anon:report")) \
                .row(btn("🏠 منوی اصلی", "nav:home")).build()

    ctx.answer(
        header("✅ وصل شدی!",
               "از این لحظه پیام‌هایت مستقیم به طرف مقابل می‌رسد 🕵️\n"
               f"{SEPARATOR}\n"
               "▪️ برای پاسخ دادن، روی پیام او «ریپلای» بزن ↩️\n"
               "▪️ با دکمه‌های پایین می‌توانی چت را ببندی 🚪\n"
               f"{SEPARATOR}\n"
               + tip("هویت تو کاملاً مخفی است 🔒")),
        panel,
    )
    try:
        ctx.client.send_message(
            owner,
            header("🔔 یک نفر وصل شد!",
                   "یکی از لینک‌های شما استفاده شد و حالا می‌توانید ناشناس چت کنید 🕵️\n"
                   f"{SEPARATOR}\n"
                   "▪️ پیام‌هایت مستقیم به او می‌رسد\n"
                   "▪️ برای پاسخ دادن روی پیامش ریپلای بزن ↩️\n"
                   "▪️ دکمه‌های پایین برای مدیریت گفتگوست"),
            inline_keypad=panel,
            chat_keypad=chat_keypad(),
        )
    except Exception:
        pass
    try:
        ctx.client.send_message(guest, "💬 آماده‌ایم! هر چه خواستی بنویس 👇",
                                chat_keypad=chat_keypad())
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# گفتگو (رد و بدل پیام)
# --------------------------------------------------------------------------- #
@state("anon_talk")
@guarded("anon.talk")
def anon_talk(ctx: Context) -> None:
    _, data = ctx.get_state()
    chat_row = ctx.db.anon_chat(int(data.get("chat", 0) or 0))
    if not chat_row or chat_row["status"] != "open":
        ctx.clear_state()
        ctx.send("🚪 این گفتگو دیگر فعال نیست.\n"
                 "می‌توانی یک لینک تازه بسازی 🔗",
                 kb().row(btn("🔗 لینک ناشناس", "anon:new"))
                      .row(btn("🏠 منوی اصلی", "nav:home")).build())
        return

    text = (ctx.text or "").strip()
    partner = _partner(chat_row, ctx.sender_id)

    # --- دستورات درونِ گفتگو ---
    if text in CLOSE_WORDS:
        _finish(ctx, chat_row, "🚪 چت ناشناس بسته شد.\n"
                               f"{SEPARATOR}\n"
                               "هر وقت خواستی یک لینک تازه بساز 🔗",
                notify_both=True)
        return
    if text in BLOCK_WORDS:
        ctx.db.anon_block(str(ctx.sender_id), partner)
        _finish(ctx, chat_row, "🚫 طرف مقابل بلاک شد و گفتگو بسته شد.\n"
                               f"{SEPARATOR}\n"
                               "دیگر پیامی از او دریافت نخواهی کرد 🔒")
        return
    if text in REVEAL_WORDS:
        reveal(ctx, chat_row)
        return
    if text in REPORT_WORDS:
        report(ctx, chat_row)
        return
    if text in STATUS_WORDS:
        status(ctx, chat_row)
        return
    if text in HOME_WORDS:
        active_chat_panel(ctx, chat_row)
        return
    if text.startswith("/"):
        ctx.send("💬 شما در یک گفتگوی ناشناس هستید.\n"
                 "برای خروج «🚪 بستن چت» را بزن، یا پیامت را بفرست ✍️",
                 kb().row(btn("🚪 بستن چت", "anon:stop"),
                          btn("📊 وضعیت", "anon:status")).build())
        return

    # --- ارسال پیام ---
    if _flood(str(ctx.sender_id)):
        ctx.send("⏳ کمی آهسته‌تر! برای امنیتِ همه، سرعت ارسال محدود است 🛡")
        return
    if len(text) > MAX_LEN or (ctx.update.file_id and not text):
        pass
    if len(text) > MAX_LEN:
        ctx.send(f"📏 پیام خیلی طولانی است (حداکثر {en_to_fa(MAX_LEN)} کاراکتر).")
        return

    update = ctx.update
    target = ""
    if update.reply_to:
        target = ctx.db.anon_reply_target(ctx.chat_id, update.reply_to)
        if not target:
            target = update.reply_to

    sent_id = ""
    try:
        if update.file_id:
            if update.media_kind == "sticker":
                result = ctx.client.send_sticker(partner, update.file_id)
            else:
                file_type = "Image" if update.media_kind == "photo" else "File"
                result = ctx.client.send_file(partner, update.file_id, caption=text[:900],
                                              file_type=file_type,
                                              reply_to_message_id=target or None)
        else:
            if not text:
                ctx.send("✍️ پیام خالی است؛ بنویس یا یک عکس/استیکر بفرست 🙂")
                return
            if update.is_forwarded and not text:
                ctx.send("🔒 پیام‌های فورواردی ارسال نمی‌شوند (حفظ ناشناس بودن).")
                return
            result = ctx.client.send_message(partner, text,
                                             reply_to_message_id=target or None)
        sent_id = _msg_id(result)
    except Exception as exc:                       # طرف مقابل ربات را بلاک کرده؟
        ctx.log_error("anon.relay", exc)
        ctx.send("📭 پیام تحویل نشد؛ احتمالاً طرف مقابل ربات را متوقف کرده است.\n"
                 "می‌توانی گفتگو را ببندی و لینک تازه‌ای بسازی 🔗",
                 kb().row(btn("🚪 بستن چت", "anon:stop"), btn("🔗 لینک تازه", "anon:new"))
                      .build())
        return

    ctx.db.anon_touch_chat(int(chat_row["id"]))
    if sent_id and update.message_id:
        ctx.db.anon_map_msg(partner, sent_id, str(update.message_id))


def status(ctx: Context, chat_row: dict) -> None:
    """وضعیت گفتگو."""
    started = int(chat_row.get("started") or 0)
    minutes = max(1, int((time.time() - started) / 60)) if started else 1
    revealed_a = bool(chat_row.get("reveal_a"))
    revealed_b = bool(chat_row.get("reveal_b"))
    mine = revealed_a if str(chat_row["user_a"]) == str(ctx.sender_id) else revealed_b
    theirs = revealed_b if str(chat_row["user_a"]) == str(ctx.sender_id) else revealed_a
    ctx.send(
        header("📊 وضعیت گفتگو",
               f"▫️ وضعیت: {'🟢 فعال' if chat_row['status'] == 'open' else '🔴 بسته'}\n"
               f"▫️ مدت گفتگو: {en_to_fa(minutes)} دقیقه\n"
               f"▫️ درخواست افشا — شما: {'✅' if mine else '➖'} · طرف مقابل: {'✅' if theirs else '➖'}\n"
               f"{SEPARATOR}\n"
               + tip("اگر هر دو «افشای هویت» را بزنید، هویتِ هم را می‌بینید.")),
        kb().row(btn("🪪 افشای هویت", "anon:reveal"), btn("🚪 بستن چت", "anon:stop"))
             .row(btn("🏠 منوی اصلی", "nav:home")).build(),
    )


def reveal(ctx: Context, chat_row: dict) -> None:
    """افشای هویت فقط با رضایت هر دو طرف."""
    ctx.db.anon_set_reveal(int(chat_row["id"]), str(ctx.sender_id))
    chat_row = ctx.db.anon_chat(int(chat_row["id"])) or chat_row
    partner = _partner(chat_row, ctx.sender_id)
    if chat_row.get("reveal_a") and chat_row.get("reveal_b"):
        ctx.send(
            header("🪪 افشای هویت",
                   "هر دو طرف موافقت کردید؛ هویت‌ها:\n"
                   f"{SEPARATOR}\n"
                   f"▫️ شما: {_identity(ctx, ctx.sender_id)}\n"
                   f"▫️ طرف مقابل: {_identity(ctx, partner)}\n"
                   f"{SEPARATOR}\n"
                   + tip("گفتگو همچنان ادامه دارد 💬")),
            kb().row(btn("🚪 بستن چت", "anon:stop"), btn("📊 وضعیت", "anon:status"))
                 .row(btn("🏠 منوی اصلی", "nav:home")).build(),
        )
        try:
            ctx.client.send_message(
                partner,
                header("🪪 افشای هویت",
                       "هر دو طرف موافقت کردید؛ هویت‌ها:\n"
                       f"{SEPARATOR}\n"
                       f"▫️ شما: {_identity(ctx, partner)}\n"
                       f"▫️ طرف مقابل: {_identity(ctx, ctx.sender_id)}"),
                inline_keypad=kb().row(btn("🚪 بستن چت", "anon:stop")).build(),
            )
        except Exception:
            pass
        return

    ctx.send("🪪 درخواست افشای هویت ثبت شد.\n"
             "اگر طرف مقابل هم بزند، هویت‌ها آشکار می‌شود 🤝",
             kb().row(btn("📊 وضعیت", "anon:status"), btn("🚪 بستن چت", "anon:stop")).build())
    try:
        ctx.client.send_message(
            partner,
            "🪪 طرف مقابل می‌خواهد هویتش را نشان دهد.\n"
            "اگر تو هم «افشای هویت» را بزنی، نام و نام‌کاربریِ هم را می‌بینید 🤝",
            inline_keypad=kb().row(btn("🪪 من هم می‌خواهم", "anon:reveal"),
                                   btn("🚪 بستن چت", "anon:stop")).build(),
        )
    except Exception:
        pass


def report(ctx: Context, chat_row: dict) -> None:
    """گزارشِ گفتگو به ادمین‌ها (بدون افشای هویتِ گزارش‌دهنده)."""
    partner = _partner(chat_row, ctx.sender_id)
    ctx.db.log("REPORT", "anon", f"chat={chat_row['id']} reporter={ctx.sender_id}")
    for admin in config.ADMIN_IDS:
        try:
            ctx.client.send_message(
                str(admin),
                f"🚩 گزارش چت ناشناس\n{SEPARATOR}\n"
                f"▫️ گفتگو: #{chat_row['id']}\n"
                f"▫️ گزارش‌دهنده: {ctx.sender_id}\n"
                f"▫️ طرف مقابل: {partner}\n"
                f"{SEPARATOR}\n"
                "در صورت نیاز می‌توانید کاربر را مسدود کنید.",
            )
        except Exception:
            pass
    ctx.send("🚩 گزارش ثبت شد و به مدیران رسید.\n"
             "ایمنیِ شما برای ما مهم است 🛡",
             kb().row(btn("🚫 بلاک و بستن", "anon:block"), btn("🚪 فقط بستن", "anon:stop"))
                  .row(btn("🏠 منوی اصلی", "nav:home")).build())


# --------------------------------------------------------------------------- #
# دکمه‌های مدیریت گفتگو
# --------------------------------------------------------------------------- #
@route("anon:stop")
@command("/stop", "/end", "/خروج")
@guarded("anon.stop")
def anon_stop(ctx: Context) -> None:
    chat_row = ctx.db.anon_active_chat(ctx.sender_id)
    if not chat_row:
        ctx.answer("💬 گفتگوی فعالی نداری.\nیک لینک تازه بساز 🔗",
                   kb().row(btn("🔗 ساخت لینک", "anon:new"),
                            btn("🕵️ چت ناشناس", "menu:anon"))
                        .row(btn("🏠 منوی اصلی", "nav:home")).build())
        return
    _finish(ctx, chat_row, "🚪 چت ناشناس بسته شد.\n"
                           f"{SEPARATOR}\n"
                           "هر وقت خواستی یک لینک تازه بساز 🔗")


@route("anon:block")
@command("/block")
@guarded("anon.block")
def anon_block(ctx: Context) -> None:
    chat_row = ctx.db.anon_active_chat(ctx.sender_id)
    if not chat_row:
        ctx.answer("💬 گفتگوی فعالی نداری که طرفش را بلاک کنی.",
                   kb().row(btn("🕵️ چت ناشناس", "menu:anon"),
                            btn("🏠 منوی اصلی", "nav:home")).build())
        return
    partner = _partner(chat_row, ctx.sender_id)
    ctx.db.anon_block(str(ctx.sender_id), partner)
    _finish(ctx, chat_row, "🚫 طرف مقابل بلاک شد و گفتگو بسته شد 🔒\n"
                           f"{SEPARATOR}\n"
                           "او دیگر نمی‌تواند از لینک‌های شما استفاده کند.")


@route("anon:reveal")
@command("/reveal")
@guarded("anon.reveal")
def anon_reveal(ctx: Context) -> None:
    chat_row = ctx.db.anon_active_chat(ctx.sender_id)
    if not chat_row:
        ctx.answer("💬 گفتگوی فعالی نداری.",
                   kb().row(btn("🕵️ چت ناشناس", "menu:anon"),
                            btn("🏠 منوی اصلی", "nav:home")).build())
        return
    reveal(ctx, chat_row)


@route("anon:report")
@command("/report")
@guarded("anon.report")
def anon_report(ctx: Context) -> None:
    chat_row = ctx.db.anon_active_chat(ctx.sender_id)
    if not chat_row:
        ctx.answer("💬 گفتگوی فعالی برای گزارش نداری.",
                   kb().row(btn("🕵️ چت ناشناس", "menu:anon"),
                            btn("🏠 منوی اصلی", "nav:home")).build())
        return
    report(ctx, chat_row)


@route("anon:status")
@command("/status")
@guarded("anon.status")
def anon_status(ctx: Context) -> None:
    chat_row = ctx.db.anon_active_chat(ctx.sender_id)
    if not chat_row:
        ctx.answer("💬 گفتگوی فعالی نداری.\nیک لینک تازه بساز 🔗",
                   kb().row(btn("🔗 ساخت لینک", "anon:new"),
                            btn("🕵️ چت ناشناس", "menu:anon"))
                        .row(btn("🏠 منوی اصلی", "nav:home")).build())
        return
    status(ctx, chat_row)


@route("anon:blocks")
@guarded("anon.blocks")
def anon_blocks(ctx: Context) -> None:
    rows = ctx.db._query_all(
        "SELECT blocked_id FROM anon_blocks WHERE user_id = ? ORDER BY created DESC LIMIT 20",
        (str(ctx.sender_id),))
    if not rows:
        ctx.answer("🚫 لیست بلاک شما خالی است ✅\n"
                   "هیچ‌کس را بلاک نکرده‌ای.",
                   kb().row(btn("🕵️ چت ناشناس", "menu:anon"),
                            btn("🏠 منوی اصلی", "nav:home")).build())
        return
    keyboard = kb()
    for row in rows:
        keyboard.row(btn(f"🔓 آزاد کردن {row['blocked_id'][-6:]}",
                         f"anon:unblock:{row['blocked_id']}"))
    keyboard.row(btn("🕵️ چت ناشناس", "menu:anon"), btn("🏠 منوی اصلی", "nav:home"))
    ctx.answer(header("🚫 لیست بلاک",
                      "این افراد نمی‌توانند با لینک شما وصل شوند 🔒\n"
                      f"{SEPARATOR}\n"
                      + tip("برای آزاد کردن، روی هر کدام بزن.")),
               keyboard.build())


@route("anon:unblock", prefix=True)
@guarded("anon.unblock")
def anon_unblock(ctx: Context) -> None:
    target = (ctx.arg or "").strip()
    if target:
        ctx.db.anon_unblock(str(ctx.sender_id), target)
    ctx.answer("🔓 کاربر از لیست بلاک خارج شد ✅",
               kb().row(btn("🚫 لیست بلاک", "anon:blocks"),
                        btn("🕵️ چت ناشناس", "menu:anon"))
                    .row(btn("🏠 منوی اصلی", "nav:home")).build())


@route("anon:help")
@guarded("anon.help")
def anon_help(ctx: Context) -> None:
    ctx.answer(
        header("🛡 امنیت و راهنمای چت ناشناس",
               "🔒 چه چیزهایی مخفی می‌ماند؟\n"
               "▫️ شماره تلفن، نام کاربری، نام و شناسه‌ی شما\n"
               "▫️ پیام از مسیر ربات عبور می‌کند و ذخیره نمی‌شود\n\n"
               "🚫 چه چیزهایی ارسال نمی‌شود؟\n"
               "▫️ پیام‌های فورواردی (ممکن است هویت را لو بدهد)\n"
               "▫️ پیام‌های مشکوک و اسپم (محدودیت سرعت)\n\n"
               "🧰 ابزارهای کنترل شما\n"
               "▫️ 🚪 بستن چت — در هر لحظه\n"
               "▫️ 🚫 بلاک — مسدود کردنِ همیشگیِ طرف مقابل\n"
               "▫️ 🪪 افشای هویت — فقط با رضایت هر دو نفر\n"
               "▫️ 🚩 گزارش — ارسال به مدیران ربات\n"
               "▫️ 🚫 ابطال لینک — از کار انداختنِ لینکِ ساخته‌شده\n"
               f"{SEPARATOR}\n"
               + tip("اگر احساس ناامنی کردی، همان لحظه بلاک کن 🔒")),
        kb().row(btn("🔗 ساخت لینک", "anon:new"), btn("📋 لینک‌های من", "anon:links"))
             .row(btn("🕵️ چت ناشناس", "menu:anon"), btn("🏠 منوی اصلی", "nav:home"))
             .build(),
    )
