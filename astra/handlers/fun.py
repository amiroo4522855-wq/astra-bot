"""بخش سرگرمی: جوک، شعر، فال، بازی، چالش روزانه و استیکر/گیف."""
from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path

from ..core.context import Context
from ..core.keyboards import btn, kb, main_menu
from ..core.router import route, state
from ..core.utils import SEPARATOR, day_index, en_to_fa
from ..services import ai
from .common import enter, fail, go, guarded, header, section_closed, tip

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

STICKER_PACKS = [
    ("😂 خنده‌دار", "funny persian sticker, cute cartoon, white background, bold outlines"),
    ("❤️ عاشقانه", "romantic persian sticker, hearts, kawaii style, white background"),
    ("🎉 تبریک", "happy birthday congratulation sticker, confetti, cartoon, white background"),
    ("💪 انگیزشی", "motivational sticker, energetic explosion, bold text style illustration"),
    ("😎 باحال", "cool sunglasses character sticker, vector art, white background"),
    ("🌙 شب‌بخیر", "good night sticker, moon and stars, cute cartoon style"),
]

GAMES = [("🎯 حدس عدد", "game:guess"), ("✊ سنگ‌کاغذقیچی", "game:rps"),
         ("🎲 تاس", "game:dice")]


@lru_cache(maxsize=8)
def _load(name: str) -> list:
    path = DATA_DIR / f"{name}.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


# --------------------------------------------------------------------------- #
# منو
# --------------------------------------------------------------------------- #
@route("menu:fun")
@guarded("fun.menu")
def fun_menu(ctx: Context) -> None:
    if section_closed(ctx, "fun"):
        return
    enter(ctx, "menu:fun")
    keyboard = (
        kb()
        .row(btn("😂 جوک و خاطره", "fun:joke"), btn("📜 شعر", "fun:poem"))
        .row(btn("🔮 فال حافظ", "fun:fal"), btn("🎮 بازی‌ها", "fun:games"))
        .row(btn("🏆 چالش روزانه", "fun:challenge"), btn("🎨 استیکر و گیف", "fun:sticker"))
        .nav()
    )
    ctx.answer(
        header("🎮 بخش سرگرمی",
               "اینجا قراره حالتو خوب کنم 😄\n"
               f"{SEPARATOR}\n"
               + tip("همه چیز رایگان و نامحدود است ♾")),
        keyboard.build(),
    )


# --------------------------------------------------------------------------- #
# جوک و شعر و فال
# --------------------------------------------------------------------------- #
@route("fun:joke")
@guarded("fun.joke")
def joke(ctx: Context) -> None:
    jokes = _load("jokes") or ["فعلاً جوکی ندارم 😅"]
    text = random.choice(jokes)
    ctx.answer(
        f"😂 یه جوک بامزه\n{SEPARATOR}\n{text}",
        kb().row(btn("😂 یکی دیگه", "fun:joke"), btn("🎮 سرگرمی", "menu:fun"))
             .row(btn("🏠 منوی اصلی", "nav:home")).build(),
    )


@route("fun:poem")
@guarded("fun:poem")
def poem(ctx: Context) -> None:
    poems = _load("poems") or [{"text": "شعری در دسترس نیست 🌙", "poet": "آسترا"}]
    item = random.choice(poems)
    ctx.answer(
        f"📜 {item.get('poet', 'شعر')}\n{SEPARATOR}\n{item.get('text', '')}",
        kb().row(btn("📜 شعر دیگر", "fun:poem"), btn("🎮 سرگرمی", "menu:fun"))
             .row(btn("🏠 منوی اصلی", "nav:home")).build(),
    )


@route("fun:fal")
@guarded("fun.fal")
def fal(ctx: Context) -> None:
    fal_data = _load("hafez")
    if not fal_data:
        ctx.answer("🔮 فال در دسترس نیست 😕")
        return
    index = day_index() % len(fal_data)
    item = fal_data[index]
    ctx.answer(
        f"🔮 فال امروز شما\n{SEPARATOR}\n"
        f"{item.get('poem', '')}\n"
        f"{SEPARATOR}\n"
        f"📖 تفسیر:\n{item.get('meaning', '')}",
        kb().row(btn("🎲 فال تصادفی", "fun:falrandom"), btn("🎮 سرگرمی", "menu:fun"))
             .row(btn("🏠 منوی اصلی", "nav:home")).build(),
    )


@route("fun:falrandom")
@guarded("fun.fal_random")
def fal_random(ctx: Context) -> None:
    fal_data = _load("hafez")
    if not fal_data:
        ctx.answer("🔮 فال در دسترس نیست 😕")
        return
    item = random.choice(fal_data)
    ctx.answer(
        f"🎲 فال تصادفی\n{SEPARATOR}\n{item.get('poem', '')}\n"
        f"{SEPARATOR}\n📖 تفسیر:\n{item.get('meaning', '')}",
        kb().row(btn("🔮 فال دیگر", "fun:falrandom"), btn("🏠 منوی اصلی", "nav:home")).build(),
    )


@route("fun:challenge")
@guarded("fun.challenge")
def challenge(ctx: Context) -> None:
    items = _load("challenges") or ["امروز به یک نفر محبت کن ❤️"]
    item = items[day_index() % len(items)]
    ctx.answer(
        f"🏆 چالش امروز\n{SEPARATOR}\n{item}\n"
        f"{SEPARATOR}\n"
        + tip("انجامش بده و برای دوستات بفرست 😉"),
        kb().row(btn("🎮 بازی‌ها", "fun:games"), btn("🎮 سرگرمی", "menu:fun"))
             .row(btn("🏠 منوی اصلی", "nav:home")).build(),
    )


# --------------------------------------------------------------------------- #
# بازی‌ها
# --------------------------------------------------------------------------- #
@route("fun:games")
@guarded("fun.games")
def games_menu(ctx: Context) -> None:
    enter(ctx, "fun:games")
    keyboard = kb()
    keyboard.grid([(label, cb) for label, cb in GAMES], per_row=3)
    keyboard.nav()
    ctx.answer(header("🎮 بازی‌ها", "یکی رو انتخاب کن تا شروع کنیم 🎯"), keyboard.build())


@route("game:guess")
@guarded("game.guess")
def game_guess(ctx: Context) -> None:
    enter(ctx, "game:guess")
    secret = random.randint(1, 100)
    ctx.set_state("await_guess", {"secret": secret, "tries": 0})
    ctx.answer(
        header("🎯 حدس عدد",
               "یک عدد بین ۱ تا ۱۰۰ انتخاب کردم 🤫\n"
               f"{SEPARATOR}\n"
               "حدس بزن! (بنویس: ۴۲)\n"
               + tip("اگر خسته شدی بنویس «بس»")),
        kb().row(btn("❌ پایان بازی", "nav:back")).build(),
    )


@state("await_guess")
@guarded("game.guess_do")
def guess_do(ctx: Context) -> None:
    from ..core.utils import fa_to_en
    raw = (ctx.text or "").strip()
    if raw in ("بس", "❌ پایان بازی", "/cancel", "خروج"):
        _, data = ctx.get_state()
        ctx.clear_state()
        ctx.send(f"🏳️ بازی تمام شد. عدد من {en_to_fa(data.get('secret', 0))} بود!")
        go(ctx, "fun:games")
        return
    number = None
    try:
        number = int(float(fa_to_en(raw)))
    except (TypeError, ValueError):
        number = None
    if number is None:
        ctx.send("🔢 فقط یک عدد بفرست (مثل ‎42‎) 🙏")
        return

    _, data = ctx.get_state()
    secret = int(data.get("secret", 0))
    tries = int(data.get("tries", 0)) + 1
    if number == secret:
        ctx.clear_state()
        ctx.send(
            f"🎉 آفرین! درست گفتی\n{SEPARATOR}\n"
            f"▫️ عدد: {en_to_fa(secret)}\n"
            f"▫️ تعداد حدس: {en_to_fa(tries)}\n"
            f"🏆 {'عالی بود!' if tries <= 4 else 'بالاخره پیداش کردی 😄'}",
            kb().row(btn("🎯 بازی دوباره", "game:guess"),
                     btn("🎮 بازی دیگر", "fun:games")).build(),
        )
        return
    hint = "بالاتر ⬆️" if number < secret else "پایین‌تر ⬇️"
    ctx.set_state("await_guess", {"secret": secret, "tries": tries})
    ctx.send(f"🤔 نه! {hint}\n▫️ حدس شماره {en_to_fa(tries)}")


@route("game:rps")
@guarded("game.rps")
def game_rps(ctx: Context) -> None:
    enter(ctx, "game:rps")
    ctx.answer(
        header("✊ سنگ، کاغذ، قیچی",
               "یکی رو انتخاب کن 👇"),
        kb().row(btn("✊ سنگ", "game:rps:rock"), btn("📄 کاغذ", "game:rps:paper"))
             .row(btn("✌️ قیچی", "game:rps:scissors"))
             .nav().build(),
    )


@route("game:rps", prefix=True)
@guarded("game.rps_play")
def rps_play(ctx: Context) -> None:
    choices = {"rock": ("✊ سنگ", "scissors"), "paper": ("📄 کاغذ", "rock"),
               "scissors": ("✌️ قیچی", "paper")}
    user_choice = (ctx.arg or "rock").strip()
    if user_choice not in choices:
        user_choice = "rock"
    bot_choice = random.choice(list(choices))
    user_label, beats = choices[user_choice]
    bot_label = choices[bot_choice][0]
    if user_choice == bot_choice:
        result = "🤝 مساوی!"
    elif beats == bot_choice:
        result = "🎉 تو بردی!"
    else:
        result = "🤖 من بردم!"
    ctx.answer(
        f"{result}\n{SEPARATOR}\n"
        f"🧑 تو: {user_label}\n🤖 من: {bot_label}",
        kb().row(btn("🔄 دوباره", "game:rps"), btn("🎮 بازی دیگر", "fun:games"))
             .row(btn("🏠 منوی اصلی", "nav:home")).build(),
    )


@route("game:dice")
@guarded("game.dice")
def game_dice(ctx: Context) -> None:
    faces = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}
    value = random.randint(1, 6)
    ctx.answer(
        f"🎲 تاس انداختم: {faces[value]}\n{SEPARATOR}\n"
        f"عدد: {en_to_fa(value)}",
        kb().row(btn("🎲 دوباره", "game:dice"), btn("🎮 بازی دیگر", "fun:games"))
             .row(btn("🏠 منوی اصلی", "nav:home")).build(),
    )


# --------------------------------------------------------------------------- #
# استیکر و گیف
# --------------------------------------------------------------------------- #
@route("fun:sticker")
@guarded("fun.sticker")
def sticker_menu(ctx: Context) -> None:
    enter(ctx, "fun:sticker")
    keyboard = kb()
    keyboard.grid([(label, f"fun:stk:{index}")
                   for index, (label, _) in enumerate(STICKER_PACKS)], per_row=2)
    keyboard.row(btn("✍️ استیکر با متن خودم", "fun:stkcustom"))
    keyboard.nav()
    ctx.answer(
        header("🎨 استیکر و گیف",
               "یه دسته رو انتخاب کن تا برات استیکر بسازم 🖼\n"
               f"{SEPARATOR}\n"
               + tip("استیکرها با هوش مصنوعی ساخته می‌شوند.")),
        keyboard.build(),
    )


@route("fun:stk", prefix=True)
@guarded("fun.sticker_make")
def sticker_make(ctx: Context) -> None:
    try:
        index = int(ctx.arg or "0")
    except ValueError:
        index = 0
    if not ctx.is_vip and not ctx.consume("ai_image"):
        from .vip import upgrade_keyboard
        message, keyboard = ctx.limit_message("ai_image")
        ctx.send(message, keyboard)
        return
    label, prompt = STICKER_PACKS[index % len(STICKER_PACKS)]
    ctx.send(f"🎨 دارم استیکر «{label}» رو می‌سازم…")
    try:
        image = ai.image_bytes(prompt)
    except Exception as exc:
        fail(ctx, "fun.sticker", exc, "⚠️ ساخت استیکر در این لحظه ممکن نیست. بعداً امتحان کن 🙏")
        return
    file_id = ctx.client.upload_bytes(image, "astra-sticker.png", "Image")
    ctx.client.send_file(
        ctx.chat_id, file_id, caption=f"{label}\n✨ استیکر آسترا",
        file_type="Image",
        inline_keypad=kb().row(btn("🎨 استیکر دیگر", "fun:sticker"),
                               btn("🏠 منوی اصلی", "nav:home")).build(),
    )


@route("fun:stkcustom")
@guarded("fun.sticker_custom")
def sticker_custom(ctx: Context) -> None:
    enter(ctx, "fun:stkcustom")
    ctx.set_state("await_sticker_text")
    ctx.answer(
        header("✍️ استیکر دلخواه",
               "چی می‌خوای تو استیکر باشه؟ بنویس 🖌\n"
               f"{SEPARATOR}\n"
               + tip("مثال: یه ربات خوشحال که چای می‌خوره")),
        kb().row(btn("❌ انصراف", "nav:back")).build(),
    )


@state("await_sticker_text")
@guarded("fun.sticker_custom_do")
def sticker_custom_do(ctx: Context) -> None:
    text = (ctx.text or "").strip()
    if text in ("❌ انصراف", "/cancel"):
        ctx.clear_state()
        go(ctx, "fun:sticker")
        return
    if len(text) < 3:
        ctx.send("✍️ کمی بیشتر توضیح بده 🙏")
        return
    if not ctx.consume("ai_image"):
        from .vip import upgrade_keyboard
        message, keyboard = ctx.limit_message("ai_image")
        ctx.send(message, keyboard)
        return
    ctx.clear_state()
    ctx.send("🎨 دارم می‌سازم…")
    try:
        image = ai.image_bytes(f"sticker, {text}, vector art, white background")
    except Exception as exc:
        fail(ctx, "fun.sticker_custom", exc, "⚠️ ساخت استیکر ممکن نیست؛ دوباره امتحان کن 🙏")
        return
    file_id = ctx.client.upload_bytes(image, "astra-sticker.png", "Image")
    ctx.client.send_file(
        ctx.chat_id, file_id, caption=f"🎨 {text}\n✨ استیکر آسترا",
        file_type="Image",
        inline_keypad=kb().row(btn("🎨 استیکر دیگر", "fun:sticker"),
                               btn("🏠 منوی اصلی", "nav:home")).build(),
    )
