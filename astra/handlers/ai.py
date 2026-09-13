"""بخش هوش مصنوعی: چت، تصویرساز، خلاصه‌سازی، ترجمه و پرسش آزاد."""
from __future__ import annotations

from .. import config
from ..core.context import Context
from ..core.keyboards import btn, kb, main_menu
from ..core.router import route, state
from ..core.utils import SEPARATOR, en_to_fa, truncate
from ..services import ai
from ..services.http import ServiceError
from .common import enter, go, guarded, header, section_closed, tip

TRANSLATE_TARGETS = [
    ("🇬🇧 انگلیسی", "انگلیسی"), ("🇸🇦 عربی", "عربی"), ("🇫🇷 فرانسوی", "فرانسوی"),
    ("🇩🇪 آلمانی", "آلمانی"), ("🇹🇷 ترکی", "ترکی"), ("🇷🇺 روسی", "روسی"),
    ("🇪🇸 اسپانیایی", "اسپانیایی"), ("🇮🇷 فارسی", "فارسی"),
]

MAX_HISTORY = 8


def _no_key_message(ctx: Context) -> None:
    ctx.send(
        "🤖 این بخش فعلاً فعال نیست.\n"
        f"{SEPARATOR}\n"
        "کلید سرویس هوش مصنوعی در تنظیمات ربات قرار نگرفته.\n"
        "اگر صاحب ربات هستی، فایل ‎.env‎ را کامل کن و ربات را ری‌استارت کن.",
        kb().row(btn("🏠 منوی اصلی", "nav:home")).build(),
    )


# --------------------------------------------------------------------------- #
# منو
# --------------------------------------------------------------------------- #
@route("menu:ai")
@guarded("ai.menu")
def ai_menu(ctx: Context) -> None:
    if section_closed(ctx, "ai"):
        return
    enter(ctx, "menu:ai")
    keyboard = (
        kb()
        .row(btn("💬 چت هوشمند", "ai:chat"), btn("🎨 ساخت عکس", "ai:image"))
        .row(btn("📄 خلاصه‌سازی متن", "ai:summary"), btn("🌐 ترجمه هوشمند", "ai:translate"))
        .row(btn("❓ پرسش آزاد", "ai:ask"))
        .nav()
    )
    ctx.answer(
        header("🤖 بخش هوش مصنوعی",
               "چت کن، عکس بساز، متن خلاصه کن یا ترجمه بگیر ✨\n"
               f"{SEPARATOR}\n"
               + tip(f"سهمیه‌ی امروز: {en_to_fa(config.FREE_LIMITS['ai_chat'])} پیام رایگان")),
        keyboard.build(),
    )


# --------------------------------------------------------------------------- #
# چت
# --------------------------------------------------------------------------- #
@route("ai:chat")
@guarded("ai.chat")
def ai_chat(ctx: Context) -> None:
    if not config.AI_API_KEY:
        _no_key_message(ctx)
        return
    enter(ctx, "ai:chat")
    ctx.set_state("ai_chat", {"history": []})
    ctx.answer(
        header("💬 چت هوشمند",
               "از این به بعد هر چی بنویسی رو جواب می‌دم 🧠\n"
               f"{SEPARATOR}\n"
               + tip("برای پایان، دکمه‌ی زیر رو بزن.")),
        kb().row(btn("🛑 پایان گفتگو", "ai:stop")).build(),
    )


@state("ai_chat")
@guarded("ai.chat_msg")
def ai_chat_message(ctx: Context) -> None:
    text = (ctx.text or "").strip()
    if text in ("🛑 پایان گفتگو", "/stop", "خروج", "❌ انصراف"):
        ctx.clear_state()
        go(ctx, "menu:ai")
        return
    if not text:
        return
    if not ctx.consume("ai_chat"):
        from .vip import upgrade_keyboard
        message, keyboard = ctx.limit_message("ai_chat")
        ctx.send(message, keyboard)
        return

    _, data = ctx.get_state()
    history = data.get("history") or []
    history.append({"role": "user", "content": text[:2000]})
    ctx.send("🤔 دارم فکر می‌کنم…")
    answer = ai.chat(
        [{"role": "system", "content": config.AI_SYSTEM_PROMPT}] + history[-MAX_HISTORY:]
    )
    history.append({"role": "assistant", "content": answer})
    ctx.set_state("ai_chat", {"history": history[-MAX_HISTORY:]})
    ctx.send(
        f"🤖 {answer}",
        kb().row(btn("🛑 پایان گفتگو", "ai:stop"),
                 btn("🏠 منوی اصلی", "nav:home")).build(),
    )


@route("ai:stop")
@guarded("ai.stop")
def ai_stop(ctx: Context) -> None:
    ctx.clear_state()
    ctx.answer("🛑 گفتگو تمام شد.",
               kb().row(btn("🤖 بخش هوش مصنوعی", "menu:ai"),
                        btn("🏠 منوی اصلی", "nav:home")).build())


# --------------------------------------------------------------------------- #
# پرسش آزاد
# --------------------------------------------------------------------------- #
@route("ai:ask")
@guarded("ai.ask")
def ai_ask(ctx: Context) -> None:
    if not config.AI_API_KEY:
        _no_key_message(ctx)
        return
    enter(ctx, "ai:ask")
    ctx.set_state("await_ai_question")
    ctx.answer(
        header("❓ پرسش آزاد",
               "هر سوالی داری بپرس؛ کوتاه و دقیق جواب می‌دم 🎯\n"
               f"{SEPARATOR}\n"
               + tip("مثال: چطور تمرکزم رو بیشتر کنم؟")),
        kb().row(btn("❌ انصراف", "nav:back")).build(),
    )


@state("await_ai_question")
@guarded("ai.ask_do")
def ai_ask_answer(ctx: Context) -> None:
    question = (ctx.text or "").strip()
    if question in ("❌ انصراف", "/cancel"):
        ctx.clear_state()
        go(ctx, "menu:ai")
        return
    if len(question) < 3:
        ctx.send("✍️ سوال رو کامل‌تر بنویس 🙏")
        return
    if not ctx.consume("ai_chat"):
        from .vip import upgrade_keyboard
        message, keyboard = ctx.limit_message("ai_chat")
        ctx.send(message, keyboard)
        return
    ctx.clear_state()
    ctx.send("🔎 دارم جواب رو پیدا می‌کنم…")
    answer = ai.ask(question)
    ctx.send(
        f"❓ {question}\n{SEPARATOR}\n{answer}",
        kb().row(btn("❓ سوال بعدی", "ai:ask"), btn("🏠 منوی اصلی", "nav:home")).build(),
    )


# --------------------------------------------------------------------------- #
# تصویرساز
# --------------------------------------------------------------------------- #
@route("ai:image")
@guarded("ai.image")
def ai_image(ctx: Context) -> None:
    enter(ctx, "ai:image")
    ctx.set_state("await_ai_image")
    ctx.answer(
        header("🎨 ساخت عکس با هوش مصنوعی",
               "توصیف تصویر رو بنویس (فارسی یا انگلیسی) 🖼\n"
               f"{SEPARATOR}\n"
               + tip("مثال: «یه گربه‌ی فضانورد روی ماه» یا «a cyberpunk Tehran at night»")),
        kb().row(btn("❌ انصراف", "nav:back")).build(),
    )


@state("await_ai_image")
@guarded("ai.image_do")
def ai_image_make(ctx: Context) -> None:
    prompt = (ctx.text or "").strip()
    if prompt in ("❌ انصراف", "/cancel"):
        ctx.clear_state()
        go(ctx, "menu:ai")
        return
    if len(prompt) < 3:
        ctx.send("✍️ توصیف کوتاهه! کمی بیشتر توضیح بده 🙏")
        return
    if not ctx.consume("ai_image"):
        from .vip import upgrade_keyboard
        message, keyboard = ctx.limit_message("ai_image")
        ctx.send(message, keyboard)
        return
    ctx.clear_state()
    ctx.send("🎨 دارم تصویرت رو می‌سازم… کمی صبر کن 🖌")
    image_bytes = ai.image_bytes(prompt)
    file_id = ctx.client.upload_bytes(image_bytes, "astra-ai.png", "Image")
    ctx.client.send_file(
        ctx.chat_id, file_id,
        caption=f"🖼 {truncate(prompt, 80)}\n✨ ساخته‌شده با آسترا",
        file_type="Image",
        inline_keypad=kb().row(btn("🎨 عکس بعدی", "ai:image"),
                               btn("🏠 منوی اصلی", "nav:home")).build(),
    )


# --------------------------------------------------------------------------- #
# خلاصه‌سازی
# --------------------------------------------------------------------------- #
@route("ai:summary")
@guarded("ai.summary")
def ai_summary(ctx: Context) -> None:
    if not config.AI_API_KEY:
        _no_key_message(ctx)
        return
    enter(ctx, "ai:summary")
    ctx.set_state("await_ai_summary")
    ctx.answer(
        header("📄 خلاصه‌سازی متن",
               "متن یا مقاله رو بفرست تا در چند خط خلاصه‌ش کنم 📝\n"
               f"{SEPARATOR}\n"
               + tip("تا ۶ هزار کاراکتر پشتیبانی می‌شود.")),
        kb().row(btn("❌ انصراف", "nav:back")).build(),
    )


@state("await_ai_summary")
@guarded("ai.summary_do")
def ai_summary_do(ctx: Context) -> None:
    text = (ctx.text or "").strip()
    if text in ("❌ انصراف", "/cancel"):
        ctx.clear_state()
        go(ctx, "menu:ai")
        return
    if len(text) < 60:
        ctx.send("📏 متن خیلی کوتاهه؛ یه متن واقعی بفرست تا خلاصه کنم 🙏")
        return
    if not ctx.consume("ai_chat"):
        from .vip import upgrade_keyboard
        message, keyboard = ctx.limit_message("ai_chat")
        ctx.send(message, keyboard)
        return
    ctx.clear_state()
    ctx.send("📝 دارم خلاصه می‌کنم…")
    result = ai.summarize(text)
    ctx.send(
        f"📄 خلاصه‌ی متن شما\n{SEPARATOR}\n{result}",
        kb().row(btn("📄 متن بعدی", "ai:summary"), btn("🏠 منوی اصلی", "nav:home")).build(),
    )


# --------------------------------------------------------------------------- #
# ترجمه
# --------------------------------------------------------------------------- #
@route("ai:translate")
@guarded("ai.translate")
def ai_translate(ctx: Context) -> None:
    if not config.AI_API_KEY:
        _no_key_message(ctx)
        return
    enter(ctx, "ai:translate")
    keyboard = kb()
    keyboard.grid([(label, f"ai:tr:{value}") for label, value in TRANSLATE_TARGETS], per_row=2)
    keyboard.nav()
    ctx.answer(header("🌐 ترجمه هوشمند", "می‌خوای به چه زبانی ترجمه کنم؟ 👇"),
               keyboard.build())


@route("ai:tr", prefix=True)
@guarded("ai.translate_pick")
def ai_translate_pick(ctx: Context) -> None:
    target = (ctx.arg or "انگلیسی").strip()
    ctx.set_state("await_translate", {"target": target})
    ctx.answer(
        header(f"🌐 ترجمه به {target}",
               "متن رو بفرست تا ترجمه کنم ✍️\n"
               f"{SEPARATOR}\n"
               + tip("متن‌های تا ۳ هزار کاراکتر بهتر هستند.")),
        kb().row(btn("🔄 تغییر زبان", "ai:translate"), btn("❌ انصراف", "nav:back")).build(),
    )


@state("await_translate")
@guarded("ai.translate_do")
def ai_translate_do(ctx: Context) -> None:
    text = (ctx.text or "").strip()
    if text in ("❌ انصراف", "/cancel"):
        ctx.clear_state()
        go(ctx, "menu:ai")
        return
    _, data = ctx.get_state()
    target = data.get("target", "انگلیسی")
    if len(text) < 2:
        ctx.send("✍️ متنی برای ترجمه نفرستادی!")
        return
    if not ctx.consume("ai_chat"):
        from .vip import upgrade_keyboard
        message, keyboard = ctx.limit_message("ai_chat")
        ctx.send(message, keyboard)
        return
    ctx.clear_state()
    ctx.send("🌐 دارم ترجمه می‌کنم…")
    result = ai.translate(text, target)
    ctx.send(
        f"🌐 ترجمه به {target}\n{SEPARATOR}\n{result}",
        kb().row(btn("🌐 ترجمه‌ی دیگر", "ai:translate"),
                 btn("🏠 منوی اصلی", "nav:home")).build(),
    )
