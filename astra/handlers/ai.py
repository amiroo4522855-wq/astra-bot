"""بخش هوش مصنوعی: چت، تصویرساز، خلاصه‌سازی، ترجمه و پرسش آزاد."""
from __future__ import annotations

import json
import re

from .. import config
from ..core.context import Context
from ..core.keyboards import btn, kb, main_menu
from ..core.router import route, state
from ..core.utils import SEPARATOR, en_to_fa, truncate
from ..services import ai, brain, calculator, clock, convert, currency, weather
from ..services.http import ServiceError
from .common import enter, go, guarded, header, section_closed, tip

TRANSLATE_TARGETS = [
    ("🇬🇧 انگلیسی", "انگلیسی"), ("🇸🇦 عربی", "عربی"), ("🇫🇷 فرانسوی", "فرانسوی"),
    ("🇩🇪 آلمانی", "آلمانی"), ("🇹🇷 ترکی", "ترکی"), ("🇷🇺 روسی", "روسی"),
    ("🇪🇸 اسپانیایی", "اسپانیایی"), ("🇮🇷 فارسی", "فارسی"),
]

MAX_HISTORY = 8

# کیبوردِ سریع برای چت (احساسِ گفتگوی واقعی)
from ..core.keyboards import chat_keypad as _chat_keypad

CHAT_KEYPAD = _chat_keypad([
    [("💡 چه کاری بلدی؟", "چه کاری می‌تونی انجام بدی؟"),
     ("🌤 آب‌وهوا", "آب و هوا تهران")],
    [("💱 قیمت دلار", "قیمت دلار"), ("🕓 ساعت", "ساعت چنده")],
    [("🛑 پایان گفتگو", "🛑 پایان گفتگو")],
])


# --------------------------------------------------------------------------- #
# حافظه‌ی گفتگو
# --------------------------------------------------------------------------- #
def _memory(ctx: Context) -> dict:
    raw = ctx.db.get_setting(f"ai:mem:{ctx.sender_id}", "")
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}


def _remember(ctx: Context, **fields) -> None:
    memory = _memory(ctx)
    memory.update({k: v for k, v in fields.items() if v})
    ctx.db.set_setting(f"ai:mem:{ctx.sender_id}",
                       json.dumps(memory, ensure_ascii=False))


def _api_key(ctx: Context) -> str:
    """کلیدِ شخصیِ کاربر (اختیاری) یا کلیدِ سراسریِ ربات."""
    return ctx.db.get_setting(f"ai:key:{ctx.sender_id}", "") or config.AI_API_KEY


def _chat_header(ctx: Context) -> str:
    """متن خوش‌آمدِ گفتگو (با لحن مؤدبانه و معرفیِ توانایی‌ها)."""
    name = _memory(ctx).get("name") or ctx.update.first_name or ""
    engine = "مدل زبانی پیشرفته 🧠" if _api_key(ctx) else "مغزِ آسترا 🧠"
    return header(
        "💬 گفتگوی هوشمند",
        f"{name + ' عزیز، ' if name else ''}در خدمتم 🌿\n"
        f"{SEPARATOR}\n"
        "من می‌توانم با شما گفتگو کنم و پاسخ‌هایم را — تا جای ممکن —\n"
"\n"
        "از **داده‌ی واقعی** می‌گیرم:\n"
        "• 🌤 آب‌وهوای زنده‌ی ۴۴۹ شهر\n"
        "• 💱 قیمت لحظه‌ای ارز، طلا، سکه و ارز دیجیتال\n"
        "• 🕓 ساعت و تاریخ · 🧮 محاسبه · 🔄 تبدیل واحد\n"
        "• 🌐 ترجمه و 📚 دانش عمومی\n"
        f"{SEPARATOR}\n"
        f"▫️ موتور پاسخ‌گویی: {engine}\n"
        f"{SEPARATOR}\n"
        + tip("بنویسید چه می‌خواهید؛ مثال: «آب و هوا شیراز» یا «قیمت طلا»"),
    )


def _joke_text() -> str:
    from .fun import _load
    items = _load("jokes") or ["فعلاً جوکی ندارم 🌿"]
    import random
    return random.choice(items)


def _poem_text() -> str:
    from .fun import _load
    items = _load("poems") or [{"poet": "آسترا", "text": "شعری در دسترس نیست 🌙"}]
    import random
    item = random.choice(items)
    return f"📜 {item.get('poet', 'شعر')}\n{SEPARATOR}\n{item.get('text', '')}"


def _price_answer(ctx: Context, query: str) -> str:
    """پاسخِ قیمت با داده‌ی واقعی (TGJU/کانال/کریپتو)."""
    from .practical import _report
    query = brain.normalize(query or "")
    if any(word in query for word in ("بیت", "تتر", "اتریوم", "کریپتو", "ارز دیجیتال")):
        kind = "crypto"
    elif any(word in query for word in ("سکه", "طلا", "مثقال", "انس")):
        kind = "gold"
    else:
        kind = "currency"
    return _report(ctx, kind, silent=True)


def _brain_answer(ctx: Context, text: str) -> str:
    """پاسخ با مغزِ آسترا (داده‌های واقعی + دانش + گفتگو)."""
    result = brain.analyze(text, _memory(ctx))
    if result.get("remember"):
        _remember(ctx, **result["remember"])
    kind, slots = result.get("kind"), result.get("slots") or {}

    if kind == "empty":
        return "بفرمایید، گوش می‌کنم 👂"
    if kind == "text":
        return result["text"]
    if kind == "joke":
        return f"😂 یه جوک بامزه\n{SEPARATOR}\n{_joke_text()}"
    if kind == "poem":
        return _poem_text()
    if kind == "wiki":
        summary = brain.wiki(slots.get("query", text))
        if summary:
            return (f"📚 {slots.get('query', '').strip()[:60]}\n{SEPARATOR}\n{summary}\n"
                    f"{SEPARATOR}\n"
                    + tip("منبع: ویکی‌پدیا · اگر دقیق‌تر می‌خواهی، سوالت را مشخص‌تر بپرس."))
        return _fallback(text)
    if kind == "calc":
        try:
            return calculator.render(slots.get("expr", ""))
        except Exception:
            return "🧮 این عبارت را نتوانستم حساب کنم؛ کمی ساده‌تر بنویسید 🙏"
    if kind == "convert":
        text_value = f"{slots.get('value')} {slots.get('source')} به {slots.get('target')}"
        if slots.get("source") in ("دلار", "یورو", "درهم", "تومان", "ریال") or \
           slots.get("target") in ("دلار", "یورو", "درهم", "تومان", "ریال"):
            return _price_answer(ctx, text_value)
        try:
            return convert.convert_text(text_value)
        except Exception:
            return "🔄 این تبدیل را بلد نیستم؛ مثال: «۱۰ کیلومتر به متر» 🙏"
    if kind == "translate":
        translated = brain.translate(slots.get("text", ""), slots.get("target", "انگلیسی"))
        if translated:
            return (f"🌐 ترجمه به {slots.get('target')}\n{SEPARATOR}\n{translated}\n"
                    f"{SEPARATOR}\n"
                    + tip("سرویس ترجمه‌ی رایگان؛ برای متن‌های تخصصی دقت را بررسی کنید."))
        return "🌐 ترجمه در این لحظه در دسترس نیست؛ کمی بعد دوباره امتحان کنید 🙏"
    if kind == "weather":
        city = slots.get("city", "")
        try:
            return weather.render_full(city)
        except Exception:
            try:
                return weather.render(city)
            except Exception:
                return f"🌤 نتوانستم وضعیتِ «{city}» را بگیرم؛ کمی بعد دوباره بپرسید 🙏"
    if kind == "ask_city":
        ctx.set_state("await_ai_city", {})
        return ("🏙 کدام شهر؟\n"
                f"{SEPARATOR}\n"
                "نام شهر را بنویسید (مثال: تهران، کرمانشاه، اصفهان) تا وضعیت هوایش را بگیرم 🌤")
    if kind == "price":
        return _price_answer(ctx, slots.get("query", text))
    if kind == "time":
        return clock.now_report()
    return _fallback(text)


def _fallback(text: str) -> str:
    return (f"{brain._pick(brain.UNKNOWN_REPLIES)}\n"
            f"{SEPARATOR}\n"
            "• 🌤 «آب و هوا تهران» — وضعیت دقیق هوا\n"
            "• 💱 «قیمت دلار» / «قیمت سکه» — نرخ لحظه‌ای\n"
            "• 🕓 «ساعت چنده» — زمان و تاریخ\n"
            "• 🧮 «حاصل ۱۲ ضرب ۵» — محاسبه\n"
            "• 🌐 «ترجمه کن good luck» — ترجمه\n"
            f"{SEPARATOR}\n"
            + tip("یا بپرسید: «چه کاری می‌تونی انجام بدی؟»"))


# --------------------------------------------------------------------------- #
# منو
# --------------------------------------------------------------------------- #
@route("menu:ai")
@guarded("ai.menu")
def ai_menu(ctx: Context) -> None:
    if section_closed(ctx, "ai"):
        return
    enter(ctx, "menu:ai")
    engine = "مدل زبانی پیشرفته 🧠" if _api_key(ctx) else "مغزِ آسترا 🧠"
    keyboard = (
        kb()
        .row(btn("💬 چت هوشمند", "ai:chat"), btn("🎨 ساخت عکس", "ai:image"))
        .row(btn("📄 خلاصه‌سازی متن", "ai:summary"), btn("🌐 ترجمه هوشمند", "ai:translate"))
        .row(btn("❓ پرسش آزاد", "ai:ask"), btn("🔑 کلید شخصی", "ai:key"))
        .nav()
    )
    ctx.answer(
        header("🤖 بخش هوش مصنوعی",
               "گفتگو کن، عکس بساز، متن خلاصه کن یا ترجمه بگیر ✨\n"
               f"{SEPARATOR}\n"
               "پاسخ‌ها تا جای ممکن از **داده‌ی واقعی** می‌آیند:\n"
               "آب‌وهوا، قیمت، ساعت، محاسبه، ترجمه و دانش عمومی 🌿\n"
               f"{SEPARATOR}\n"
               f"▫️ موتور پاسخ‌گویی: {engine}\n"
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
    enter(ctx, "ai:chat")
    ctx.set_state("ai_chat", {"history": []})
    ctx.send(_chat_header(ctx),
             kb().row(btn("💡 چه کاری بلدی؟", "ai:chip:ability"),
                      btn("🌤 آب‌وهوای من", "ai:chip:weather"))
                  .row(btn("💱 قیمت دلار", "ai:chip:price"),
                       btn("🕓 ساعت و تاریخ", "ai:chip:time"))
                  .row(btn("🛑 پایان گفتگو", "ai:stop"),
                       btn("🏠 منوی اصلی", "nav:home"))
                  .build(),
             chat_keypad=CHAT_KEYPAD)


@route("ai:chip", prefix=True)
@guarded("ai.chip")
def ai_chip(ctx: Context) -> None:
    """میانبرهای سریعِ گفتگو."""
    mapping = {
        "ability": "چه کاری می‌تونی انجام بدی؟",
        "weather": "آب و هوا تهران",
        "price": "قیمت دلار",
        "time": "ساعت چنده",
        "joke": "یک جوک بگو",
        "poem": "یک شعر بخون",
        "gold": "قیمت سکه",
        "crypto": "قیمت بیت‌کوین",
    }
    text = mapping.get((ctx.arg or "").strip(), "چه کاری می‌تونی انجام بدی؟")
    ctx.set_state("ai_chat", {"history": []})
    ctx.text = text
    ai_chat_message(ctx)


@state("await_ai_city")
@guarded("ai.city")
def ai_city_answer(ctx: Context) -> None:
    """پاسخ به پرسشِ «کدام شهر؟»."""
    city = (ctx.text or "").strip()
    if city in ("❌ انصراف", "/cancel"):
        ctx.set_state("ai_chat", {"history": []})
        go(ctx, "ai:chat")
        return
    found = weather.find_local(city)
    if not found:
        ctx.send("🏙 این شهر را پیدا نکردم؛ نام شهر را دقیق‌تر بنویسید 🙏")
        return
    _remember(ctx, city=found.name)
    ctx.set_state("ai_chat", {"history": []})
    try:
        ctx.send(weather.render_full(found.name))
    except Exception:
        ctx.send(weather.render(found.name))
    _offer_more(ctx)


def _offer_more(ctx: Context) -> None:
    """دکمه‌های ادامه (همیشه مسیر بعدی وجود دارد)."""
    ctx.send("ادامه می‌دهیم؟ هر چه می‌خواهید بنویسید 👇",
             kb().row(btn("💡 چه کاری بلدی؟", "ai:chip:ability"),
                      btn("💱 قیمت دلار", "ai:chip:price"))
                  .row(btn("🌐 ترجمه", "ai:translate"), btn("🎨 ساخت عکس", "ai:image"))
                  .row(btn("🛑 پایان گفتگو", "ai:stop"),
                       btn("🏠 منوی اصلی", "nav:home"))
                  .build())


@state("ai_chat")
@guarded("ai.chat_msg")
def ai_chat_message(ctx: Context) -> None:
    text = (ctx.text or "").strip()
    if text in ("🛑 پایان گفتگو", "/stop", "/end", "خروج", "❌ انصراف", "پایان"):
        ctx.clear_state()
        go(ctx, "ai:stop")
        return
    if not text:
        return
    if not ctx.consume("ai_chat"):
        from .vip import upgrade_keyboard
        message, keyboard = ctx.limit_message("ai_chat")
        ctx.send(message, keyboard)
        return

    key = _api_key(ctx)
    if key:                                     # مدل زبانی واقعی (در صورت داشتن کلید)
        _, data = ctx.get_state()
        history = data.get("history") or []
        history.append({"role": "user", "content": text[:2000]})
        ctx.send("🤔 دارم فکر می‌کنم…")
        try:
            answer = ai.chat(
                [{"role": "system", "content": config.AI_SYSTEM_PROMPT}]
                + history[-MAX_HISTORY:],
                api_key=key,
            )
        except Exception as exc:
            ctx.log_error("ai.chat", exc)
            answer = _brain_answer(ctx, text)     # افتِ خودکار به مغزِ داخلی
        history.append({"role": "assistant", "content": answer})
        ctx.set_state("ai_chat", {"history": history[-MAX_HISTORY:]})
        ctx.send(f"🤖 {answer}",
                 kb().row(btn("🛑 پایان گفتگو", "ai:stop"),
                          btn("🏠 منوی اصلی", "nav:home")).build())
        return

    answer = _brain_answer(ctx, text)
    ctx.send(answer)
    _offer_more(ctx)


@route("ai:stop")
@guarded("ai.stop")
def ai_stop(ctx: Context) -> None:
    ctx.clear_state()
    ctx.answer("🛑 گفتگو تمام شد.\n"
               f"{SEPARATOR}\n"
               "هر وقت خواستی صدام کن؛ با کمال میل در خدمتم 🤍",
               kb().row(btn("💬 گفتگوی تازه", "ai:chat"),
                        btn("🤖 بخش هوش مصنوعی", "menu:ai"))
                    .row(btn("🏠 منوی اصلی", "nav:home")).build())


# --------------------------------------------------------------------------- #
# کلید شخصی (اختیاری)
# --------------------------------------------------------------------------- #
@route("ai:key")
@guarded("ai.key")
def ai_key_menu(ctx: Context) -> None:
    has = bool(ctx.db.get_setting(f"ai:key:{ctx.sender_id}", ""))
    ctx.answer(
        header("🔑 کلید شخصی (اختیاری)",
               "اگر کلیدِ سرویسِ هوش مصنوعیِ خودتان را دارید، اینجا وارد کنید تا\n"
"\n"
               "گفتگو با مدل زبانیِ پیشرفته انجام شود.\n"
               f"{SEPARATOR}\n"
               f"▫️ وضعیت: {'✅ تنظیم شده' if has else '➖ تنظیم نشده'}\n"
               f"{SEPARATOR}\n"
               + tip("بدون کلید هم آسترا با «مغزِ داخلی» و داده‌های واقعی پاسخ می‌دهد 🧠")),
        kb().row(btn("✍️ وارد کردن کلید", "ai:keyset"), btn("🗑 حذف کلید", "ai:keydel"))
             .row(btn("🤖 بخش هوش مصنوعی", "menu:ai"), btn("🏠 منوی اصلی", "nav:home"))
             .build(),
    )


@route("ai:keyset")
@guarded("ai.key_set")
def ai_key_set(ctx: Context) -> None:
    ctx.set_state("await_ai_key")
    ctx.answer("🔑 کلید را بفرستید (مثل ‎sk-...‎):\n"
               f"{SEPARATOR}\n"
               + tip("برای انصراف بنویسید: لغو"),
               kb().row(btn("❌ انصراف", "ai:key")).build())


@state("await_ai_key")
@guarded("ai.key_save")
def ai_key_save(ctx: Context) -> None:
    text = (ctx.text or "").strip()
    if text in ("لغو", "❌ انصراف", "/cancel"):
        ctx.clear_state()
        go(ctx, "ai:key")
        return
    if not (10 <= len(text) <= 200):
        ctx.send("📏 این کلید معتبر به نظر نمی‌رسد؛ دوباره بفرستید 🙏")
        return
    ctx.clear_state()
    ctx.db.set_setting(f"ai:key:{ctx.sender_id}", text)
    ctx.send("✅ کلید ذخیره شد؛ از این لحظه گفتگو با مدل زبانی انجام می‌شود 🧠",
             kb().row(btn("💬 شروع گفتگو", "ai:chat"), btn("🏠 منوی اصلی", "nav:home"))
                  .build())


@route("ai:keydel")
@guarded("ai.key_del")
def ai_key_del(ctx: Context) -> None:
    ctx.db.set_setting(f"ai:key:{ctx.sender_id}", "")
    ctx.answer("🗑 کلید حذف شد؛ آسترا دوباره با مغزِ داخلی پاسخ می‌دهد 🧠",
               kb().row(btn("🤖 بخش هوش مصنوعی", "menu:ai"),
                        btn("🏠 منوی اصلی", "nav:home")).build())


# --------------------------------------------------------------------------- #
# پرسش آزاد
# --------------------------------------------------------------------------- #
@route("ai:ask")
@guarded("ai.ask")
def ai_ask(ctx: Context) -> None:
    enter(ctx, "ai:ask")
    ctx.set_state("await_ai_question")
    ctx.answer(
        header("❓ پرسش آزاد",
               "هر سوالی داری بپرس؛ کوتاه و دقیق جواب می‌دم 🎯\n"
               f"{SEPARATOR}\n"
               + tip("مثال: «هوش مصنوعی چیست» یا «چطور تمرکزم را بیشتر کنم؟»")),
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
    if _api_key(ctx):
        ctx.send("🔎 دارم جواب رو پیدا می‌کنم…")
        try:
            answer = ai.ask(question, api_key=_api_key(ctx))
        except Exception as exc:
            ctx.log_error("ai.ask", exc)
            answer = _brain_answer(ctx, question)
    else:
        answer = _brain_answer(ctx, question)
    ctx.send(f"❓ {question}\n{SEPARATOR}\n{answer}",
             kb().row(btn("❓ سوال بعدی", "ai:ask"), btn("💬 گفتگو", "ai:chat"))
                  .row(btn("🏠 منوی اصلی", "nav:home")).build())


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
STOP_WORDS = {"و", "در", "به", "از", "که", "این", "را", "با", "است", "برای", "یک",
              "های", "آن", "بر", "هم", "نیز", "تا", "یا", "اما", "اگر", "شده",
              "شود", "باشد", "دارد", "کرد", "بر", "پس", "چه", "the", "and", "of",
              "to", "in", "is", "for", "a", "همه", "هر", "خود", "ما", "شما"}


def _local_summary(text: str, lines: int = 4) -> str:
    """خلاصه‌سازیِ استخراجیِ محلی (بدون نیاز به سرویس خارجی)."""
    sentences = [part.strip() for part in re.split(r"[.!?؟!\n]+", text) if part.strip()]
    if len(sentences) <= lines:
        return "📄 خلاصه‌ی متن شما\n" + SEPARATOR + "\n" + "\n".join(
            f"• {s}" for s in sentences)
    words = re.findall(r"[\u0600-\u06FFa-zA-Z]{3,}", text.lower())
    freq: dict[str, int] = {}
    for word in words:
        if word not in STOP_WORDS:
            freq[word] = freq.get(word, 0) + 1
    scored = sorted(
        ((sum(freq.get(w, 0) for w in re.findall(r"[\u0600-\u06FFa-zA-Z]{3,}",
                                                 sentence.lower()))
          / max(1, len(sentence.split())) ** 0.5, index, sentence)
         for index, sentence in enumerate(sentences)),
        reverse=True)
    best = sorted(scored[:lines], key=lambda item: item[1])
    return ("📄 خلاصه‌ی متن شما\n" + SEPARATOR + "\n" +
            "\n".join(f"• {sentence}" for _, _, sentence in best) +
            f"\n{SEPARATOR}\n"
            f"▫️ از {en_to_fa(len(sentences))} جمله، {en_to_fa(len(best))} جمله‌ی کلیدی انتخاب شد.")



@route("ai:summary")
@guarded("ai.summary")
def ai_summary(ctx: Context) -> None:
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
    if _api_key(ctx):
        try:
            result = ai.summarize(text)
        except Exception:
            result = _local_summary(text)
    else:
        result = _local_summary(text)
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
    result = brain.translate(text, target)
    if not result and _api_key(ctx):
        try:
            result = ai.translate(text, target)
        except Exception:
            result = ""
    if not result:
        result = "🌐 ترجمه در این لحظه ممکن نیست؛ کمی بعد دوباره امتحان کنید 🙏"
    ctx.send(
        f"🌐 ترجمه به {target}\n{SEPARATOR}\n{result}",
        kb().row(btn("🌐 ترجمه‌ی دیگر", "ai:translate"),
                 btn("🏠 منوی اصلی", "nav:home")).build(),
    )
