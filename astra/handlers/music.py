"""بخش موزیک: جستجو، دانلود، پلی‌لیست، رادیو و تبدیل متن به ویس."""
from __future__ import annotations

import random
from pathlib import Path

from .. import config
from ..core.context import Context
from ..core.keyboards import btn, kb, main_menu
from ..core.router import route, state
from ..core.utils import SEPARATOR, en_to_fa, format_duration
from ..services import media
from ..services import music as music_svc, radio, tts
from .common import enter, fail, go, guarded, header, section_closed, tip

RANDOM_QUERIES = [
    "موزیک شاد ایرانی", "آهنگ عاشقانه فارسی", "موزیک بی‌کلام آرام",
    "رپ فارسی جدید", "موسیقی سنتی ایرانی", "پاپ فارسی ۱۴۰۳",
    "موزیک ورزشی انرژی‌بخش", "آهنگ غمگین فارسی", "دی‌جی مهمانی ایرانی",
]

QUALITIES = [("🎚 128 kbps", "128"), ("🎚 192 kbps", "192"), ("🎚 320 kbps", "320")]


def user_quality(ctx: Context) -> str:
    saved = ctx.db.get_setting(f"quality:{ctx.sender_id}", "")
    if saved in ("128", "192", "320"):
        return saved
    return "320" if ctx.is_vip else "192"


# --------------------------------------------------------------------------- #
# منو
# --------------------------------------------------------------------------- #
@route("menu:music")
@guarded("music.menu")
def music_menu(ctx: Context) -> None:
    """زیرمنوی بخش موزیک."""
    if section_closed(ctx, "music"):
        return
    enter(ctx, "menu:music")
    text = header(
        "🎵 بخش موزیک",
        "هر آهنگی بخوای برات پیدا می‌کنم و می‌فرستمش 🎧\n"
        f"{SEPARATOR}\n"
        "از اینجا انتخاب کن 👇",
    )
    keyboard = (
        kb()
        .row(btn("🔍 جستجوی آهنگ", "music:search"), btn("⬇️ دانلود از یوتیوب", "music:yt"))
        .row(btn("🎧 پلی‌لیست من", "music:playlist"), btn("🎲 آهنگ تصادفی", "music:random"))
        .row(btn("📻 رادیو آنلاین", "music:radio"), btn("🗣 متن به ویس", "music:tts"))
        .row(btn(f"🎚 کیفیت ({user_quality(ctx)})", "music:quality"))
        .nav()
    )
    ctx.answer(text, keyboard.build())


# --------------------------------------------------------------------------- #
# جستجو
# --------------------------------------------------------------------------- #
@route("music:search")
@guarded("music.search")
def music_search(ctx: Context) -> None:
    enter(ctx, "music:search")
    ctx.set_state("await_music_query")
    ctx.answer(
        header("🔍 جستجوی آهنگ",
               "اسم آهنگ یا خواننده رو بنویس برات پیدا کنم 🎧\n"
               f"{SEPARATOR}\n"
               + tip("مثال: «همایون شجریان» یا «Sia Cheap Thrills»")),
        kb().row(btn("❌ انصراف", "nav:back")).build(),
    )


@state("await_music_query", "music_pick")
@guarded("music.do_search")
def do_music_search(ctx: Context) -> None:
    query = (ctx.text or "").strip()
    if query in ("❌ انصراف", "/cancel", "لغو"):
        ctx.clear_state()
        go(ctx, "menu:music")
        return
    if len(query) < 2:
        ctx.send("✍️ لطفاً اسم آهنگ یا خواننده رو کامل‌تر بنویس 🙏")
        return
    if not ctx.consume("music"):
        from .vip import upgrade_keyboard
        text, keyboard = ctx.limit_message("music")
        ctx.send(text, keyboard)
        return

    ctx.send(f"🔎 دارم «{query}» رو می‌گردم… کمی صبر کن ⏳")
    results = music_svc.search(query, limit=8)
    if not results:
        ctx.send(
            "🤷‍♂️ آهنگی با این اسم پیدا نکردم!\n"
            f"{SEPARATOR}\n"
            "من موسیقی را از منابعِ واقعی (Deezer و Apple Music) می‌گردم.\n"
            "اگر اسم را فارسی نوشتی، یک بار با انگلیسی امتحان کن\n"
            "مثال: «Ebi» یا «Googoosh»\n"
            f"{SEPARATOR}\n"
            f"🔗 جستجو در یوتیوب: {music_svc.youtube_search_link(query)}",
            kb().row(btn("🔄 جستجوی جدید", "music:search"),
                     btn("✨ جستجو در مینی‌اپ", "app:open"),
                     btn("🔙 بازگشت", "nav:back")).build(),
        )
        return

    ctx.set_state("music_pick", {"results": results, "query": query})
    lines = [header("🎧 نتایج جستجو", f"برای «{query}» این‌ها رو پیدا کردم:")]
    for index, item in enumerate(results):
        duration = format_duration(int(item.get("duration") or 0))
        lines.append(f"{en_to_fa(index + 1)}. {item['title']}")
        lines.append(f"    👤 {item['artist']} · ⏱ {duration} · {item['source_name']}")
    lines.append(SEPARATOR)
    lines.append(tip("روی شماره‌ی آهنگ بزن تا برات بفرستمش 🎵"))

    keyboard = kb()
    keyboard.grid([(f"{en_to_fa(i + 1)} ⬇️ دانلود", f"music:get:{i}")
                   for i in range(len(results))], per_row=3)
    keyboard.row(btn("➕ همه به پلی‌لیست", "music:pladd:all"),
                 btn("🔄 جستجوی جدید", "music:search"))
    keyboard.nav()
    ctx.send("\n".join(lines), keyboard.build())


@route("music:get", prefix=True)
@guarded("music.get")
def music_get(ctx: Context) -> None:
    _, data = ctx.get_state()
    results = data.get("results") or []
    try:
        index = int(ctx.arg or "0")
    except ValueError:
        index = 0
    if not results or index >= len(results):
        ctx.answer("🤔 این نتیجه دیگه معتبر نیست.\nیک جستجوی تازه انجام بده 👇",
                   kb().row(btn("🔍 جستجوی جدید", "music:search"),
                            btn("🏠 منوی اصلی", "nav:home")).build())
        return
    item = results[index]
    send_track(ctx, item, index)


def send_track(ctx: Context, item: dict, index: int = -1) -> None:
    """ارسالِ آهنگ به‌صورتِ فایلِ صوتیِ واقعی (بدون دانلود روی سرور)."""
    if not ctx.consume("music"):
        from .vip import upgrade_keyboard
        text, keyboard = ctx.limit_message("music")
        ctx.send(text, keyboard)
        return
    audio = music_svc.best_audio(item)
    if not audio:
        ctx.send("🎧 متأسفم، فایلِ قابل‌پخش این آهنگ در دسترس نیست 🙏",
                 kb().row(btn("🔍 جستجوی جدید", "music:search")).nav().build())
        return
    ctx.send("⏳ دارم برات می‌فرستم… 🎵")
    caption = music_svc.caption(item) + "\n" + SEPARATOR + "\n✨ آسترا"
    try:
        ctx.client.send_audio_url(
            chat_id=ctx.chat_id, audio_url=audio,
            title=(item.get("title") or "")[:64],
            performer=(item.get("artist") or "")[:64],
            caption=caption,
        )
        keyboard = (
            kb()
            .row(btn("⬇️ لینکِ دانلود", f"music:link:{index}"),
                 btn("➕ پلی‌لیست", f"music:pladd:{index}"))
            .row(btn("🎧 نسخه‌ی کامل در یوتیوب", "music:yt") ,
                 btn("🔍 جستجوی جدید", "music:search"))
            .nav()
        )
        ctx.client.send_file(ctx.chat_id, file_id,
                             caption=caption,
                             file_type=file_type, inline_keypad=keyboard.build())
    finally:
        media.cleanup(path)


@route("music:similar", prefix=True)
@guarded("music.similar")
def music_similar(ctx: Context) -> None:
    _, data = ctx.get_state()
    results = data.get("results") or []
    try:
        index = int(ctx.arg or "0")
    except ValueError:
        index = 0
    if not results or index >= len(results):
        go(ctx, "music:search")
        return
    query = f"{results[index]['uploader']} موزیک مشابه"
    ctx.update.text = query
    do_music_search(ctx)


# --------------------------------------------------------------------------- #
# دانلود مستقیم از لینک یوتیوب
# --------------------------------------------------------------------------- #
@route("music:yt")
@guarded("music.yt")
def music_youtube(ctx: Context) -> None:
    enter(ctx, "music:yt")
    ctx.set_state("await_music_url")
    ctx.answer(
        header("⬇️ دانلود از یوتیوب",
               "لینک آهنگ یا ویدیوی یوتیوب رو بفرست 🎬\n"
               f"{SEPARATOR}\n"
               + tip("مثال: https://youtu.be/xxxxxxxx")),
        kb().row(btn("❌ انصراف", "nav:back")).build(),
    )


@state("await_music_url")
@guarded("music.yt_url")
def do_music_url(ctx: Context) -> None:
    url = (ctx.text or "").strip()
    if "youtu" not in url and "http" not in url:
        ctx.send("🔗 این که لینک نیست!\nیک لینک معتبر یوتیوب بفرست 🙏")
        return
    ctx.clear_state()
    send_track(ctx, url, "آهنگ درخواستی", "یوتیوب")


# --------------------------------------------------------------------------- #
# آهنگ تصادفی
# --------------------------------------------------------------------------- #
@route("music:random")
@guarded("music.random")
def music_random(ctx: Context) -> None:
    query = random.choice(RANDOM_QUERIES)
    ctx.send(f"🎲 امتحان کن: «{query}»")
    ctx.update.text = query
    do_music_search(ctx)


# --------------------------------------------------------------------------- #
# پلی‌لیست
# --------------------------------------------------------------------------- #
@route("music:playlist")
@guarded("music.playlist")
def music_playlist(ctx: Context) -> None:
    enter(ctx, "music:playlist")
    items = ctx.db.playlist_list(ctx.sender_id)
    if not items:
        ctx.answer(
            header("🎧 پلی‌لیست من",
                   "فعلاً خالیه!\n"
                   f"{SEPARATOR}\n"
                   + tip("از بخش جستجو آهنگ پیدا کن و به لیست اضافه کنش.")),
            kb().row(btn("🔍 جستجوی آهنگ", "music:search")).nav().build(),
        )
        return
    lines = [header("🎧 پلی‌لیست من", f"▫️ تعداد آهنگ‌ها: {en_to_fa(len(items))}")]
    for index, item in enumerate(items[:20], start=1):
        lines.append(f"{en_to_fa(index)}. {item['title']} — {item.get('artist') or 'نامشخص'}")
    keyboard = kb()
    keyboard.grid([(f"❌ {en_to_fa(i + 1)}", f"music:pldel:{item['id']}")
                   for i, item in enumerate(items[:12])], per_row=3)
    keyboard.row(btn("🧹 پاک کردن لیست", "music:plclear"))
    keyboard.nav()
    ctx.answer("\n".join(lines), keyboard.build())


@route("music:pladd", prefix=True)
@guarded("music.pladd")
def playlist_add(ctx: Context) -> None:
    _, data = ctx.get_state()
    results = data.get("results") or []
    if not results:
        ctx.answer("🤔 اول یه آهنگ جستجو کن تا بتونم به لیست اضافه کنم.")
        return
    if ctx.arg == "all":
        added = 0
        for item in results:
            if ctx.db.playlist_add(ctx.sender_id, item["title"], item.get("uploader", ""),
                                   item["url"]):
                added += 1
        ctx.answer(f"✅ {en_to_fa(added)} آهنگ به پلی‌لیست اضافه شد 🎧")
        return
    try:
        index = int(ctx.arg or "0")
    except ValueError:
        index = 0
    item = results[min(index, len(results) - 1)]
    ok = ctx.db.playlist_add(ctx.sender_id, item["title"], item.get("uploader", ""), item["url"])
    ctx.answer("✅ به پلی‌لیست اضافه شد 🎧" if ok else "⚠️ ظرفیت پلی‌لیست پر شده!",
               kb().row(btn("🎧 پلی‌لیست من", "music:playlist"),
                        btn("🏠 منوی اصلی", "nav:home")).build())


@route("music:pldel", prefix=True)
@guarded("music.pldel")
def playlist_delete(ctx: Context) -> None:
    try:
        item_id = int(ctx.arg or "0")
    except ValueError:
        ctx.answer("⚠️ مورد نامعتبر است.")
        return
    ctx.db.playlist_remove(ctx.sender_id, item_id)
    music_playlist(ctx)


@route("music:plclear")
@guarded("music.plclear")
def playlist_clear(ctx: Context) -> None:
    ctx.db.playlist_clear(ctx.sender_id)
    ctx.answer("🧹 پلی‌لیست پاک شد.",
               kb().row(btn("🔍 جستجوی آهنگ", "music:search"),
                        btn("🏠 منوی اصلی", "nav:home")).build())


# --------------------------------------------------------------------------- #
# رادیو
# --------------------------------------------------------------------------- #
@route("music:radio")
@guarded("music.radio")
def music_radio(ctx: Context) -> None:
    enter(ctx, "music:radio")
    keyboard = kb()
    keyboard.grid([(name, f"music:radio:{index}")
                   for index, (name, _, _) in enumerate(radio.STATIONS, start=1)], per_row=2)
    keyboard.nav()
    ctx.answer(header("📻 رادیو آنلاین", "یکی از ایستگاه‌ها رو انتخاب کن 👇"),
               keyboard.build())


@route("music:radio", prefix=True)
@guarded("music.radio_pick")
def radio_pick(ctx: Context) -> None:
    try:
        index = int(ctx.arg or "1")
    except ValueError:
        index = 1
    station = radio.station(index)
    if not station:
        ctx.answer("⚠️ ایستگاه پیدا نشد.")
        return
    name, url = station
    ctx.answer(
        f"{name}\n{SEPARATOR}\n"
        f"🔗 لینک پخش:\n{url}\n"
        f"{SEPARATOR}\n"
        + tip("لینک رو باز کن تا رادیو پخش بشه 📻"),
        kb().row(btn("🎵 بخش موزیک", "menu:music"), btn("🏠 منوی اصلی", "nav:home")).build(),
    )


# --------------------------------------------------------------------------- #
# کیفیت
# --------------------------------------------------------------------------- #
@route("music:quality")
@guarded("music.quality")
def music_quality(ctx: Context) -> None:
    enter(ctx, "music:quality")
    current = user_quality(ctx)
    keyboard = kb()
    keyboard.grid([(f"{'✅ ' if q == current else ''}{label}", f"music:q:{q}")
                   for label, q in QUALITIES], per_row=3)
    keyboard.nav()
    ctx.answer(
        header("🎚 کیفیت دانلود",
               f"کیفیت فعلی: {current} kbps\n"
               f"{SEPARATOR}\n"
               "کیفیت بالاتر = حجم بیشتر. "
               + ("💎 کیفیت ۳۲۰ برای VIP آزاد است." if not ctx.is_vip
                  else "💎 اشتراک ویژه داری؛ همه کیفیت‌ها آزاد است.")),
        keyboard.build(),
    )


@route("music:q", prefix=True)
@guarded("music.set_quality")
def set_quality(ctx: Context) -> None:
    quality = (ctx.arg or "192").strip()
    if quality == "320" and not ctx.is_vip:
        ctx.answer("🔒 کیفیت ۳۲۰ مخصوص اعضای ویژه است 💎",
                   kb().row(btn("💎 دیدن پلن‌ها", "menu:vip"),
                            btn("🔙 بازگشت", "nav:back")).build())
        return
    if quality not in ("128", "192", "320"):
        quality = "192"
    ctx.db.set_setting(f"quality:{ctx.sender_id}", quality)
    ctx.answer(f"✅ کیفیت روی {quality} kbps تنظیم شد 🎚")
    go(ctx, "menu:music")


# --------------------------------------------------------------------------- #
# تبدیل متن به ویس
# --------------------------------------------------------------------------- #
@route("music:tts")
@guarded("music.tts")
def music_tts(ctx: Context) -> None:
    enter(ctx, "music:tts")
    ctx.set_state("await_tts_text")
    ctx.answer(
        header("🗣 تبدیل متن به ویس",
               "هر متنی بنویسی برات با صدای فارسی می‌خونمش 🎙\n"
               f"{SEPARATOR}\n"
               + tip("تا ۹۰۰ کاراکتر بهتر است.")),
        kb().row(btn("❌ انصراف", "nav:back")).build(),
    )


@state("await_tts_text")
@guarded("music.tts_do")
def do_tts(ctx: Context) -> None:
    text = (ctx.text or "").strip()
    if text in ("❌ انصراف", "/cancel"):
        ctx.clear_state()
        go(ctx, "menu:music")
        return
    if len(text) < 2:
        ctx.send("✍️ یه متن کوتاه برام بنویس 🙏")
        return
    if not ctx.consume("tts"):
        from .vip import upgrade_keyboard
        text_msg, keyboard = ctx.limit_message("tts")
        ctx.send(text_msg, keyboard)
        return
    ctx.clear_state()
    ctx.send("🎙 دارم ضبط می‌کنم…")
    content, name = tts.synthesize(text)
    file_id = ctx.client.upload_bytes(content, name, "Voice")
    ctx.client.send_file(ctx.chat_id, file_id, caption="🗣 متن شما با صدای آسترا ✨",
                         file_type="Voice",
                         inline_keypad=kb().row(btn("🗣 متن جدید", "music:tts"),
                                                btn("🏠 منوی اصلی", "nav:home")).build())
