"""مغزِ آسترا 🧠 — پاسخ‌گوی هوشمند، مؤدب و واقعی (بدون نیاز به کلید).

اگر کلیدِ مدل زبانی (‎AI_API_KEY‎) تنظیم شده باشد، چت از مدل واقعی استفاده
می‌کند. در غیر این صورت آسترا با این مغز پاسخ می‌دهد و برای هر پاسخ،
تا جای ممکن از **داده‌ی واقعی** استفاده می‌کند:

    🌤 آب‌وهوا  ← Open-Meteo (۴۴۹ شهر ایران)
    💱 قیمت‌ها ← TGJU / کانالِ متصل
    🕓 زمان     ← ساعت و تاریخ دقیق
    🧮 محاسبه   ← موتور محاسباتیِ ایمن
    📚 دانش     ← ویکی‌پدیا (فارسی ← انگلیسی)
    🌐 ترجمه    ← سرویس ترجمه‌ی رایگان (MyMemory)

طراحیِ گفتگو: مؤدب، کوتاه، دقیق و همیشه با پیشنهادِ قدمِ بعدی.
"""
from __future__ import annotations

import random
import re
import time
from functools import lru_cache

from ..core.utils import en_to_fa
from .http import request

BOT_NAME = "آسترا"
MAX_WIKI_CHARS = 620
UA = {"User-Agent": "AstraBot/2.0 (assistant; +https://t.me/Astra225bot)"}

# --------------------------------------------------------------------------- #
# یکسان‌سازی متن
# --------------------------------------------------------------------------- #
_REPLACEMENTS = {
    "ك": "ک", "ي": "ی", "ى": "ی", "ة": "ه", "ؤ": "و", "إ": "ا", "أ": "ا",
    "آ": "آ", "ً": "", "ٌ": "", "ٍ": "", "َ": "", "ُ": "", "ِ": "", "ّ": "",
    "ْ": "", "ٰ": "", "ـ": "", "​": "", "‎": "", "‏": "", "‌": "",
}
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def normalize(text: str) -> str:
    """یکسان‌سازیِ متن فارسی برای تطبیقِ دقیق‌تر."""
    out = (text or "").strip()
    for old, new in _REPLACEMENTS.items():
        out = out.replace(old, new)
    out = re.sub(r"\s+", " ", out)
    return out


def to_en_digits(text: str) -> str:
    return (text or "").translate(_DIGITS)


# --------------------------------------------------------------------------- #
# واژه‌نامه‌ها
# --------------------------------------------------------------------------- #
GREETINGS = ("سلام", "درود", "صبح بخیر", "عصر بخیر", "شب بخیر", "هی", "های", "hello",
             "hi", "salam", "سلوم", "سلام علیکم", "سلامم", "سلاممم")
MOODS = ("حالت", "چطوری", "چطوری", "چه خبر", "خوبی", "چیکار", "چخبر", "how are you",
         "چطوری آسترا", "حالت چطوره")
THANKS = ("ممنون", "مرسی", "تشکر", "مچکرم", "سپاس", "thanks", "tnx", "دستت درد نکنه",
          "خیلی ممنون", "ممنونم")
BYES = ("خداحافظ", "بای", "bye", "فعلا", "فعلاً", "شب خوش", "تا بعد", "خدانگهدار",
        "می‌رم", "میرم", "دیگه برم")
WHOS = ("تو کیستی", "تو کی هستی", "کی هستی", "کیستی", "خودت رو معرفی کن", "اسم چیه",
        "اسمت چیه", "نامت چیه", "who are you", "معرفی")
ABILITIES = ("چیکار می‌تونی", "چه کاری", "چه کارهایی", "کمکم می‌تونی", "چی بلدی",
             "توانایی", "قابلیت", "چه کمکی", "راهنما", "چه می‌تونی", "بلدی چیکار")
PRAISE = ("دمت گرم", "عالی", "خوبی آسترا", "دوست داشتنی", "باهوش", "خوشگل", "عالیی",
          "بهترین", "خفن", "دمت")
COMPLAINT = ("بدرد نمی‌خوری", "خنگ", "احمق", "داغون", "خراب", "کار نمی‌کنه", "افتضاح",
             "بده", "ضعیفی")
NAMES_INTRO = ("اسم من", "من اسمم", "من رو صدا بزن", "صدا کن منو", "نام من")

CITY_WORDS = ("آب و هوا", "آب‌وهوا", "هوای", "دمای", "دما", "باران", "برف", "گرم",
              "سرد", "هوا", "weather", "پیش‌بینی")
PRICE_WORDS = ("قیمت", "نرخ", "چنده", "چقدره", "ارز", "دلار", "یورو", "پوند", "درهم",
               "سکه", "طلا", "مثقال", "بیت", "بیت‌کوین", "تتر", "کریپتو", "لیر", "یوان")
TIME_WORDS = ("ساعت", "تاریخ", "چندشنبه", "چه روزی", "امروز", "وقت", "ساعت چنده",
              "تاریخ امروز", "الان")
JOKE_WORDS = ("جوک", "بخند", "خنده", "یه جوک", "joke", "لطیفه")
POEM_WORDS = ("شعر", "غزل", "حافظ", "شعر بخون", "یک بیت", "بیت بگو", "ابیات")
FAL_WORDS = ("فال", "فالم", "تفال", "حافظ")


# --------------------------------------------------------------------------- #
# پاسخ‌های آماده (متنوع و مؤدبانه)
# --------------------------------------------------------------------------- #
def _pick(options: tuple[str, ...]) -> str:
    return random.choice(options)


GREET_REPLIES = (
    "سلام! خیلی خوش‌آمدید 🌿 چطور می‌تونم کمکتون کنم؟",
    "درود بر شما ✨ بفرمایید، گوش می‌کنم.",
    "سلام و احترام 🤍 هر کاری دارید بگویید؛ با کمال میل راهنمایی‌تان می‌کنم.",
)
MOOD_REPLIES = (
    "ممنون که پرسیدید، من عالی‌ام 😊 شما چطورید؟ امروز چه کاری از دستم برمی‌آید؟",
    "خوبم، سرشار از انرژی ⚡️ حال شما چطور است؟",
    "در خدمتم 🌿 هر وقت آماده بودید، بفرمایید.",
)
THANKS_REPLIES = (
    "خواهش می‌کنم 🌸 کاری نبود؛ باز هم در خدمتم.",
    "ممنون از محبتتون 🤍 خوشحالم که مفید بودم.",
    "قابل شما رو نداشت؛ هر وقت خواستید صدام کنید 🌿",
)
BYE_REPLIES = (
    "خداحافظ؛ روز خوبی داشته باشید 🌤 هر وقت برگشتید اینجام.",
    "در پناه حق 🤍 منتظر برگشتنتون می‌مونم.",
    "فعلاً بدرود ✨ موفق باشید.",
)
PRAISE_REPLIES = (
    "خیلی ممنون؛ لطف دارید 🌸 باعث افتخاره که راضی بودید.",
    "ممنون از انرژی خوبتون 🤍 ادامه می‌دیم.",
)
COMPLAINT_REPLIES = (
    "شرمنده‌ام که رضایت نداشتید 🙏 لطفاً دقیق‌تر بگویید چه مشکلی بود تا درستش کنم.",
    "حق با شماست اگر جایی کم گذاشتم؛ بفرمایید کدام بخش، پیگیری می‌کنم 🌿",
)
UNKNOWN_REPLIES = (
    "راستش جوابِ دقیقِ این سوال را ندارم 🙏 ولی می‌توانم در این زمینه کمک کنم:",
    "اجازه بدهید صادق باشم: در این مورد مطمئن نیستم. اما این کارها از دستم برمی‌آید:",
)


# --------------------------------------------------------------------------- #
# دانشِ واقعی: ویکی‌پدیا
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=300)
def wiki(query: str, lang: str = "fa", limit: int = MAX_WIKI_CHARS) -> str:
    """خلاصه‌ی واقعی از ویکی‌پدیا (فارسی، در صورت نبود: انگلیسی)."""
    query = normalize(query).strip()
    if len(query) < 2:
        return ""
    for code in ((lang, "en") if lang == "fa" else (lang,)):
        try:
            found = request(
                f"https://{code}.wikipedia.org/w/api.php",
                params={"action": "query", "list": "search", "srsearch": query,
                        "format": "json", "srlimit": 1},
                headers=UA, timeout=12,
            )
            hits = ((found or {}).get("query") or {}).get("search") or []
            if not hits:
                continue
            title = hits[0].get("title", "")
            if not _relevant(query, title):
                continue
            data = request(
                f"https://{code}.wikipedia.org/api/rest_v1/page/summary/{title}",
                headers=UA, timeout=12,
            )
            extract = (data or {}).get("extract") or ""
            if extract:
                return _tidy(extract, limit)
        except Exception:
            continue
    return ""


STOP_QUERY = ("چطور", "چگونه", "چیست", "کیست", "چه", "چیه", "بگو", "لطفا",
              "لطفاً", "راجع", "درباره", "توضیح", "معنی", "یک", "یه", "از",
              "برای", "را", "با", "های", "ترین", "کند", "کنم", "بیشتر")


def _relevant(query: str, title: str) -> bool:
    """آیا نتیجه‌ی جستجو به پرسش ربط دارد؟ (جلوگیری از پاسخِ بی‌ربط)"""
    words = [w for w in re.split(r"[\s\u200c]+", normalize(query))
             if len(w) >= 4 and w not in STOP_QUERY]
    if not words:
        return True
    clean_title = normalize(title)
    return any(word in clean_title or clean_title in word for word in words)


def _tidy(text: str, limit: int) -> str:
    short = re.sub(r"\s+", " ", text).strip()
    if len(short) <= limit:
        return short
    cut = short[:limit]
    stop = max(cut.rfind(". "), cut.rfind("؟ "), cut.rfind("»"))
    return (cut[:stop + 1] if stop > limit * 0.5 else cut.rstrip() + "…")


# --------------------------------------------------------------------------- #
# ترجمه‌ی واقعی
# --------------------------------------------------------------------------- #
LANG_CODES = {"انگلیسی": "en", "عربی": "ar", "فرانسوی": "fr", "آلمانی": "de",
              "ترکی": "tr", "روسی": "ru", "اسپانیایی": "es", "ایتالیایی": "it",
              "چینی": "zh", "ژاپنی": "ja", "هندی": "hi", "اردو": "ur",
              "فارسی": "fa", "کردی": "ckb"}

LANG_NAMES = {v: k for k, v in LANG_CODES.items()}


def _is_persian(text: str) -> bool:
    letters = [c for c in (text or "") if c.isalpha()]
    if not letters:
        return False
    persian = sum(1 for c in letters if "؀" <= c <= "ۿ")
    return persian / len(letters) > 0.5


def translate(text: str, target: str = "انگلیسی") -> str:
    """ترجمه‌ی واقعی با سرویس رایگان MyMemory (بدون کلید)."""
    target_code = LANG_CODES.get(target, "en")
    source_code = "fa" if _is_persian(text) else "en"
    if source_code == target_code:
        target_code = "fa" if source_code == "en" else "en"
    try:
        data = request(
            "https://api.mymemory.translated.net/get",
            params={"q": text[:480], "langpair": f"{source_code}|{target_code}"},
            headers=UA, timeout=15,
        )
        result = ((data or {}).get("responseData") or {}).get("translatedText") or ""
        if result and "MYMEMORY WARNING" not in result.upper():
            return result.strip()
    except Exception:
        pass
    return ""


# --------------------------------------------------------------------------- #
# تحلیلِ نیت
# --------------------------------------------------------------------------- #
MATH_WORDS = ("حاصل", "محاسبه", "جمع", "تفریق", "ضرب", "تقسیم", "بعلاوه", "منهای",
              "توان", "جذر", "ریشه", "درصد", "چند میشه", "چند می‌شود", "حساب کن")
MATH_SYMBOLS = re.compile(r"[0-9۰-۹]\s*[\+\-\*\/\×\÷\^\%]|[0-9۰-۹]\s*\+\s*[0-9۰-۹]")

CONVERT_RE = re.compile(
    r"([0-9۰-۹]+(?:[\.,][0-9۰-۹]+)?)\s*"
    r"(کیلومتر|متر|سانتی\u200cمتر|مایل|کیلوگرم|گرم|پوند|اونس|ساعت|دقیقه|ثانیه|"
    r"دلار|یورو|پوند|درهم|تومان|ریال|سانتی\u200cگراد|فارنهایت|کلوین)\s*"
    r"(?:به|چند|معادل)\s*"
    r"(کیلومتر|متر|سانتی\u200cمتر|مایل|کیلوگرم|گرم|پوند|اونس|ساعت|دقیقه|ثانیه|"
    r"دلار|یورو|درهم|تومان|ریال|سانتی\u200cگراد|فارنهایت|کلوین)")

QUESTION_RE = re.compile(
    r"(چیست|چی هست|کیست|کی هست|کی بود|چی شد|یعنی چه|یعنی چی|تعریف|توضیح بده|"
    r"درباره|درباره‌ی|بگو چی|بگو کی|معنی)")


def _city_in(text: str) -> str:
    """پیدا کردن نام شهر در متن (از میان ۴۴۹ شهر)."""
    try:
        from .weather import cities
        names = [p.name for p in cities()]
    except Exception:
        return ""
    clean = normalize(text)
    best = ""
    for name in names:
        plain = normalize(name)
        if plain and plain in clean and len(plain) > len(best):
            best = plain
    return best


WORD_EDGE = "؀-ۿ\u200c\u200dA-Za-z"


def _has_word(text: str, word: str) -> bool:
    """تطبیقِ دقیقِ واژه (نه بخشی از یک واژه‌ی دیگر).

    مثال: «اصطلاح» نباید به‌خاطر «طلا» قیمت تلقی شود.
    """
    word = normalize(word).lower()
    if not word:
        return False
    try:
        return re.search(rf"(?<![{WORD_EDGE}]){re.escape(word)}(?![{WORD_EDGE}])",
                         text or "") is not None
    except re.error:
        return word in (text or "")


def _has_prefix(text: str, word: str) -> bool:
    """تطبیقِ واژه‌های مرکب: «بیت» در «بیتکوین» هم پذیرفته می‌شود."""
    word = normalize(word).lower()
    if len(word) < 3:
        return False
    return any(token.startswith(word) for token in re.split(r"[\s\u200c]+", text or "")
               if token)


def _match_any(text: str, words) -> bool:
    clean = normalize(text).lower()
    return any(_has_word(clean, word) for word in words)


def analyze(text: str, memory: dict | None = None) -> dict:
    """تشخیص نیتِ پیام و آماده‌سازی پاسخ.

    خروجی: {"kind", "text", "slots", "remember", "suggest"}
    """
    memory = memory or {}
    raw = (text or "").strip()
    clean = normalize(raw)
    low = clean.lower()
    slots: dict = {}
    remember: dict = {}
    suggest: list[str] = []

    if not raw:
        return {"kind": "empty", "text": "بفرمایید، گوش می‌کنم👂",
                "slots": {}, "remember": {}, "suggest": []}

    # --- نام کاربر ---
    for intro in NAMES_INTRO:
        if intro in low:
            name = raw.split(intro, 1)[-1].strip(" است.:،!؟? ") [:24]
            if name:
                remember["name"] = name
                return {"kind": "text",
                        "text": f"به‌روی چشم، {name} عزیز 🤍 از این به بعد با همین اسم صداتان می‌کنم.",
                        "slots": {}, "remember": remember,
                        "suggest": ["چه کاری می‌تونی انجام بدی؟", "آب و هوا تهران"]}

    # --- احوال‌پرسی و تعارف ---
    if _match_any(low, GREETINGS):
        name = memory.get("name", "")
        reply = _pick(GREET_REPLIES)
        if random.random() < 0.5:
            reply = f"{greeting_for()} {reply}"
        return {"kind": "text", "text": f"{name + ' عزیز، ' if name else ''}{reply}",
                "slots": {}, "remember": {}, "suggest": ["قیمت دلار", "آب و هوا تهران"]}
    if _match_any(low, MOODS):
        return {"kind": "text", "text": _pick(MOOD_REPLIES), "slots": {},
                "remember": {}, "suggest": ["یک جوک بگو", "چه کاری می‌تونی انجام بدی؟"]}
    if _match_any(low, THANKS):
        return {"kind": "text", "text": _pick(THANKS_REPLIES), "slots": {},
                "remember": {}, "suggest": []}
    if _match_any(low, BYES):
        return {"kind": "text", "text": _pick(BYE_REPLIES), "slots": {},
                "remember": {}, "suggest": []}
    if _match_any(low, PRAISE):
        return {"kind": "text", "text": _pick(PRAISE_REPLIES), "slots": {},
                "remember": {}, "suggest": []}
    if _match_any(low, COMPLAINT):
        return {"kind": "text", "text": _pick(COMPLAINT_REPLIES), "slots": {},
                "remember": {}, "suggest": []}

    # --- معرفی و توانایی ---
    if _match_any(low, WHOS):
        return {"kind": "text", "text": ABOUT_TEXT, "slots": {}, "remember": {},
                "suggest": ["چه کاری می‌تونی انجام بدی؟", "قیمت دلار"]}
    if _match_any(low, ABILITIES):
        return {"kind": "text", "text": ABILITY_TEXT, "slots": {}, "remember": {},
                "suggest": ["آب و هوا تهران", "قیمت سکه", "یک جوک بگو"]}

    # --- سرگرمی ---
    if _match_any(low, JOKE_WORDS):
        return {"kind": "joke", "text": "", "slots": {}, "remember": {}, "suggest": []}
    if _match_any(low, POEM_WORDS) or _match_any(low, FAL_WORDS):
        return {"kind": "poem", "text": "", "slots": {}, "remember": {}, "suggest": []}

    # --- محاسبه ---
    expr = _extract_math(raw)
    if expr and (MATH_SYMBOLS.search(_math_text(clean)) or _match_any(low, MATH_WORDS)):
        return {"kind": "calc", "text": "", "slots": {"expr": expr},
                "remember": {}, "suggest": []}

    # --- تبدیل واحد/ارز ---
    match = CONVERT_RE.search(clean)
    if match:
        slots = {"value": to_en_digits(match.group(1)).replace(",", "."),
                 "source": match.group(2), "target": match.group(3)}
        return {"kind": "convert", "text": "", "slots": slots,
                "remember": {}, "suggest": []}

    # --- ترجمه ---
    if "ترجمه" in low or low.startswith("معنی "):
        target = "فارسی" if _is_persian(raw) else "انگلیسی"
        for name in LANG_CODES:
            if f"به {name}" in low or f"{name}:" in low:
                target = name
                break
        payload = _strip_translate(raw, target)
        if payload:
            return {"kind": "translate", "text": "",
                    "slots": {"text": payload, "target": target},
                    "remember": {}, "suggest": []}
        return {"kind": "text",
                "text": "با کمال میل ترجمه می‌کنم 🌐\n"
                        "مثال: «ترجمه کن good morning» یا «۱۰ دلار چند تومان»",
                "slots": {}, "remember": {}, "suggest": []}

    # --- آب‌وهوا ---
    if _match_any(low, CITY_WORDS):
        city = _city_in(clean) or memory.get("city", "")
        if city:
            remember["city"] = city
            return {"kind": "weather", "text": "", "slots": {"city": city},
                    "remember": remember, "suggest": ["قیمت دلار", "ساعت چنده؟"]}
        return {"kind": "ask_city", "text": "",
                "slots": {}, "remember": {}, "suggest": []}

    # --- قیمت در برابر زمان (امتیازدهی وزنی برای دقت) ---
    price_score = 0
    for word, weight in (("قیمت", 2), ("نرخ", 2), ("دلار", 3), ("یورو", 3), ("پوند", 3),
                         ("درهم", 3), ("سکه", 3), ("طلا", 3), ("مثقال", 3),
                         ("بیت", 3), ("تتر", 3), ("ارز", 2), ("کریپتو", 3),
                         ("لیر", 2), ("یوان", 2), ("تومان", 1), ("چنده", 1),
                         ("چقدره", 1)):
        if _has_word(low, word) or word in ("بیت", "کریپتو", "تتر") and _has_prefix(low, word):
            price_score += weight
    time_score = sum(2 for word in ("ساعت", "تاریخ", "چندشنبه", "وقت")
                     if _has_word(low, word))
    if price_score >= 2 and price_score >= time_score:
        return {"kind": "price", "text": "", "slots": {"query": raw[:80]},
                "remember": {}, "suggest": ["قیمت سکه", "قیمت بیت‌کوین"]}
    if time_score:
        return {"kind": "time", "text": "", "slots": {}, "remember": {}, "suggest": []}

    # --- دانش (ویکی‌پدیا) ---
    if QUESTION_RE.search(clean) or len(clean.split()) >= 2:
        topic = _topic_from_question(clean)
        return {"kind": "wiki", "text": "", "slots": {"query": topic or raw[:80]},
                "remember": {}, "suggest": []}

    return {"kind": "unknown", "text": _pick(UNKNOWN_REPLIES), "slots": {},
            "remember": {}, "suggest": ["چه کاری می‌تونی انجام بدی؟", "آب و هوا تهران"]}


def _math_text(raw: str) -> str:
    """تبدیل عملگرهای کلمه‌ای به نماد ریاضی."""
    text = to_en_digits(normalize(raw))
    for word, sign in (("تقسیم بر", "/"), ("ضربدر", "*"), ("ضرب در", "*"),
                       ("ضرب", "*"), ("تقسیم", "/"), ("بعلاوه", "+"),
                       ("منهای", "-"), ("به توان", "**"), ("×", "*"), ("÷", "/"),
                       ("جمع با", "+"), ("جمع", "+"), ("تفریق", "-")):
        text = text.replace(word, sign)
    return text.replace(" ", "")


def _extract_math(raw: str) -> str:
    """استخراج عبارت ریاضی از جمله."""
    text = _math_text(raw)
    found = re.findall(r"[0-9\.\+\-\*\/\(\)\%\s]{3,}", text)
    for part in found:
        candidate = part.strip()
        if re.search(r"[0-9]", candidate) and re.search(r"[\+\-\*\/]", candidate):
            return candidate.replace(" ", "")
    return ""


def _strip_translate(raw: str, target: str) -> str:
    """جدا کردن متنِ مورد نظر برای ترجمه از دستورِ ترجمه."""
    text = raw
    for word in ("ترجمه کن", "ترجمه", "معنی", "به زبان", "به", ":", "؟", "?"):
        text = text.replace(word, " ")
    text = re.sub(r"\b(انگلیسی|فارسی|عربی|فرانسوی|آلمانی|ترکی|روسی|اسپانیایی|"
                  r"ایتالیایی|چینی|ژاپنی|هندی|اردو|کردی)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .,،؛;")
    return text[:400] if len(text) >= 2 else ""


def _topic_from_question(clean: str) -> str:
    """استخراج موضوع از جملاتِ پرسشی."""
    topic = clean
    for word in ("چیست", "چی هست", "کیست", "کی هست", "کی بود", "چی شد", "یعنی چه",
                 "یعنی چی", "تعریف", "توضیح بده", "درباره‌ی", "درباره", "بگو چی",
                 "بگو کی", "معنی", "لطفا", "لطفاً", "بگو", "چیه", "چی", "؟", "?"):
        topic = topic.replace(word, " ")
    return re.sub(r"\s+", " ", topic).strip()[:60]


@lru_cache(maxsize=200)
def duckduckgo(query: str) -> str:
    """خلاصه‌ی دانش‌نامه‌ای از DuckDuckGo (برای موضوعات انگلیسی)."""
    try:
        data = request("https://api.duckduckgo.com/",
                       params={"q": query[:120], "format": "json", "no_html": "1",
                               "skip_disambig": "1"},
                       headers=UA, timeout=12)
        text = ((data or {}).get("AbstractText") or "").strip()
        return _tidy(text, 480) if text else ""
    except Exception:
        return ""


# پاسخ‌های آماده برای پرسش‌های پرتکرار (محتوای واقعی و کاربردی)
ADVICE: tuple[tuple[tuple[str, ...], str], ...] = (
    (("تمرکز", "حواس‌پرت", "پرتی حواس"),
     "برای تمرکز بیشتر: ۱) موبایل را از دسترس خارج کن 📵\n"
     "۲) از روش «پومودورو» استفاده کن: ۲۵ دقیقه کار، ۵ دقیقه استراحت\n"
     "۳) هر بار فقط یک کار را انجام بده؛ چندوظیفگی تمرکز را می‌کشد\n"
     "۴) کار سخت را در ساعتی انجام بده که انرژی‌ات بیشتر است."),
    (("خواب", "بی‌خوابی", "نمی‌خوابم", "زود بیدار"),
     "برای خواب بهتر: ۱) ساعت خواب و بیداری را ثابت نگه دار ⏰\n"
     "۲) تا یک ساعت قبل از خواب صفحه‌نمایش را کنار بگذار\n"
     "۳) کافئین را بعد از عصر حذف کن ☕️\n"
     "۴) اتاق را خنک و تاریک کن و اگر ۲۰ دقیقه نخوابیدی، برخیز و کاری آرام انجام بده."),
    (("انگیزه", "بی‌حوصله", "ناامید", "تنبلی"),
     "انگیزه معمولاً بعد از شروع می‌آید، نه قبل از آن 🌱\n"
     "• هدف را به قدم‌های خیلی کوچک تقسیم کن (۵ دقیقه)\n"
     "• پیشرفت را بنویس تا ببینی در حال حرکتی\n"
     "• خودت را با دیروزش مقایسه کن، نه با دیگران\n"
     "• بعد از هر قدمِ کوچک، به خودت پاداش بده."),
    (("مدیریت زمان", "وقت کم", "برنامه‌ریزی"),
     "مدیریت زمان یعنی مدیریتِ توجه ⏳\n"
     "• هر شب ۳ کارِ مهمِ فردا را بنویس\n"
     "• کارهای مشابه را پشت‌سرهم انجام بده\n"
     "• برای کارِ عمیق، زمانِ بدون نوتیفیکیشن بگذار\n"
     "• به «نه گفتن» عادت کن؛ وقتت محدود است."),
    (("یادگیری زبان", "زبان انگلیسی", "زبان یاد"),
     "یادگیری زبان با تداوم است، نه شدت 🗣\n"
     "• روزانه ۱۵ دقیقه گوش بده (پادکست/فیلم با زیرنویس)\n"
     "• ۱۰ لغتِ پرتکرار را در جمله تمرین کن\n"
     "• هر روز ۲ دقیقه با خودت بلند صحبت کن\n"
     "• اشتباه کردن بخشی از مسیر است؛ ادامه بده."),
    (("استرس", "اضطراب", "نگران", "آرامش"),
     "برای کاهش استرس: ۱) تنفس ۴-۷-۸ (دم ۴، حبس ۷، بازدم ۸ ثانیه) 🌬\n"
     "۲) نگرانی‌ها را بنویس تا از ذهن خارج شوند\n"
     "۳) پیاده‌رویِ ۱۰ دقیقه‌ای معجزه می‌کند\n"
     "۴) اگر استرس ماندگار شد، کمک گرفتن از متخصص بهترین کار است."),
    (("ورزش", "تناسب", "لاغر", "چاق"),
     "اصلِ طلایی: تداوم از شدت مهم‌تر است 🏃\n"
     "• هفته‌ای ۳ بار، هر بار ۳۰ دقیقه فعالیت\n"
     "• ترکیبِ هوازی + قدرتی بهترین نتیجه را دارد\n"
     "• خواب و تغذیه نیمی از مسیرند\n"
     "• قبل از هر برنامه‌ی جدید با پزشک مشورت کن."),
    (("تغذیه", "رژیم", "غذا", "وزن"),
     "تغذیه‌ی سالم یعنی تعادل، نه محرومیت 🥗\n"
     "• نیمی از بشقاب را سبزیجات بگذار\n"
     "• آب کافی بنوش و قندِ مایع را کم کن\n"
     "• پروتئین را در هر وعده داشته باش\n"
     "• برای رژیمِ اختصاصی حتماً با متخصص تغذیه مشورت کن."),
    (("رمز عبور", "امنیت", "هک", "پسورد"),
     "امنیتِ حساب‌ها 🔐\n"
     "• برای هر سرویس رمزِ متفاوت و بلند (حداقل ۱۲ کاراکتر) بگذار\n"
     "• تأییدِ دو مرحله‌ای را همیشه فعال کن\n"
     "• روی لینک‌های ناشناس کلیک نکن\n"
     "• از مدیریت‌کننده‌ی رمز استفاده کن."),
    (("برنامه‌نویسی", "کدنویسی", "یادگیری برنامه", "پایتون"),
     "یادگیری برنامه‌نویسی = پروژه + تمرینِ روزانه 💻\n"
     "• یک زبان را انتخاب کن (پایتون برای شروع عالی است)\n"
     "• مفاهیم را با پروژه‌ی کوچک تمرین کن، نه فقط ویدئو\n"
     "• خطاها را بخوان؛ بهترین معلم‌اند\n"
     "• روزانه ۳۰ دقیقه کد بزن؛ تداوم از استعداد مهم‌تر است."),
    (("رزومه", "مصاحبه", "کار پیدا", "استخدام"),
     "برای استخدامِ بهتر 🧾\n"
     "• رزومه را برای هر شرکت سفارشی کن\n"
     "• دستاوردها را با عدد نشان بده (مثال: ۳۰٪ افزایش فروش)\n"
     "• قبل از مصاحبه درباره‌ی شرکت تحقیق کن\n"
     "• دو سؤالِ هوشمندانه برای پایانِ مصاحبه آماده کن."),
    (("مطالعه", "درس", "امتحان", "حفظ"),
     "مطالعه‌ی مؤثر 📚\n"
     "• روش «یادآوری فعال»: بعد از خواندن، از خودت امتحان بگیر\n"
     "• مرورِ با فاصله (فردا، ۳ روز بعد، یک هفته بعد)\n"
     "• هر ۴۵ دقیقه ۱۰ دقیقه استراحت\n"
     "• مفاهیم را با مثالِ شخصی معنا کن تا بمانند."),
    (("سرمایه‌گذاری", "پول", "پس‌انداز", "بورس"),
     "پایه‌ی مالی شخصی 💰\n"
     "• اول صندوقِ اضطراری (۳ تا ۶ ماه هزینه) بساز\n"
     "• سرمایه‌گذاری را با مبلغِ کوچک و متنوع شروع کن\n"
     "• وامِ با بهره‌ی بالا را اولویتِ تسویه قرار بده\n"
     "• قبل از هر تصمیمِ بزرگ با مشاورِ مالی مشورت کن."),
)


def advice(query: str) -> str:
    """پاسخِ آماده برای پرسش‌های پرتکرار (در صورت تطبیق)."""
    clean = normalize(query or "").lower()
    best, hits = "", 0
    for keywords, text in ADVICE:
        score = sum(1 for word in keywords if normalize(word).lower() in clean)
        if score > hits:
            best, hits = text, score
    return best if hits else ""


def greeting_for(hour: int | None = None) -> str:
    """سلامِ متناسب با زمانِ روز."""
    hour = time.localtime().tm_hour if hour is None else hour
    if 5 <= hour < 12:
        return "صبح‌تان به‌خیر 🌤"
    if 12 <= hour < 18:
        return "ظهر/عصرتان به‌خیر ☀️"
    if 18 <= hour < 22:
        return "عصرتان به‌خیر 🌇"
    return "شب‌تان به‌خیر 🌙"


# --------------------------------------------------------------------------- #
# متن‌های ثابتِ معرفی
# --------------------------------------------------------------------------- #
ABOUT_TEXT = (
    "من «آسترا» هستم؛ دستیار هوشمند و مؤدبِ شما 🤍\n"
    "هدفم این است که کارهای روزمره را برایتان ساده و دقیق انجام دهم:\n"
    "از آب‌وهوا و قیمت ارز گرفته تا ابزارها، سرگرمی و مدیریت گروه."
)

ABILITY_TEXT = (
    "این‌ها کارهایی است که برایتان انجام می‌دهم 🌿\n"
    "• 🌤 آب‌وهوای دقیقِ ۴۴۹ شهر ایران (۷ روز + کیفیت هوا)\n"
    "• 💱 قیمت لحظه‌ای ارز، طلا، سکه و ارزهای دیجیتال\n"
    "• 🕓 ساعت و تاریخ دقیقِ ایران و جهان\n"
    "• 🧮 محاسبه و تبدیل واحد و ارز\n"
    "• 🌐 ترجمه و 📚 دانشِ عمومی\n"
    "• 🎵 موزیک، 📥 دانلود، 🛠 ابزارها و 🎮 سرگرمی\n\n"
    "کافی است بنویسید چه می‌خواهید؛ مثال: «آب و هوا تهران» یا «قیمت دلار»."
)
