"""نرخ ارز، طلا، سکه و ارز دیجیتال.

منابع به‌ترتیب امتحان می‌شوند؛ اگر منبعی در دسترس نبود،
ربات پیام دوستانه می‌دهد (هرگز پیام خالی یا خطای خام نمی‌فرستد).
"""
from __future__ import annotations

import json
import re
import time

from .. import config
from ..core.utils import en_to_fa, money
from .http import ServiceError, get_json

TGJU_URL = "https://call1.tgju.org/ajax.json"
CRYPTO_URL = "https://api.coingecko.com/api/v3/simple/price"
FOREX_URL = "https://open.er-api.com/v6/latest/USD"

# کلیدهای tgju → (عنوان فارسی، واحد: irr = ریال، irt = تومان)
TGJU_MAP = {
    "price_dollar_rl": ("💵 دلار آمریکا", "irr"),
    "price_eur": ("💶 یورو", "irr"),
    "price_gbp": ("💷 پوند انگلیس", "irr"),
    "price_aed": ("🕌 درهم امارات", "irr"),
    "price_try": ("🇹🇷 لیر ترکیه", "irr"),
    "price_cny": ("🇨🇳 یوان چین", "irr"),
    "price_iqd": ("🇮🇶 دینار عراق", "irr"),
    "price_afn": ("🇦🇫 افغانی", "irr"),
    "sekee": ("🪙 سکه امامی", "irr"),
    "nim": ("🥈 نیم‌سکه", "irr"),
    "rob": ("🥉 ربع‌سکه", "irr"),
    "sekeb": ("🌸 سکه گرمی", "irr"),
    "geram18": ("✨ طلای ۱۸ عیار", "irr"),
    "geram24": ("💛 طلای ۲۴ عیار", "irr"),
    "mesghal": ("⚖️ مثقال طلا", "irr"),
    "ons": ("🌍 انس جهانی طلا", "usd"),
    "bitcoin": ("🟠 بیت‌کوین", "usd"),
}

CRYPTO_IDS = {
    "bitcoin": "🟠 بیت‌کوین (BTC)",
    "ethereum": "🟣 اتریوم (ETH)",
    "tether": "🟢 تتر (USDT)",
    "binancecoin": "🟡 بی‌ان‌بی (BNB)",
    "tron": "🔴 ترون (TRX)",
    "litecoin": "⚪️ لایت‌کوین (LTC)",
    "dogecoin": "🟤 دوج‌کوین (DOGE)",
    "solana": "🟦 سولانا (SOL)",
}

CRYPTO_FA = {
    "بیت کوین": "bitcoin", "بیت‌کوین": "bitcoin", "بیتکوین": "bitcoin", "btc": "bitcoin",
    "اتریوم": "ethereum", "eth": "ethereum", "تتر": "tether", "usdt": "tether",
    "ترون": "tron", "trx": "tron", "دوج": "dogecoin", "دوج کوین": "dogecoin",
    "سولانا": "solana", "لایت کوین": "litecoin", "لایت‌کوین": "litecoin",
    "bnb": "binancecoin", "بایننس": "binancecoin",
}

FOREX_FA = {
    "دلار": "USD", "یورو": "EUR", "پوند": "GBP", "درهم": "AED", "لیر": "TRY",
    "یوان": "CNY", "ین": "JPY", "روبل": "RUB", "فرانک": "CHF", "دلار کانادا": "CAD",
    "دینار": "IQD", "افغانی": "AFN", "ریال عربستان": "SAR", "روپیه": "INR",
}


# برچسب‌هایی که در پیام کانال‌های قیمت جست‌وجو می‌شوند
CHANNEL_LABELS = {
    "دلار": "💵 دلار آمریکا", "یورو": "💶 یورو", "پوند": "💷 پوند انگلیس",
    "درهم": "🕌 درهم امارات", "لیر": "🇹🇷 لیر ترکیه", "یوان": "🇨🇳 یوان چین",
    "سکه امامی": "🪙 سکه امامی", "سکه تمام": "🪙 سکه امامی", "سکه": "🪙 سکه امامی",
    "نیم سکه": "🥈 نیم‌سکه", "نیم‌سکه": "🥈 نیم‌سکه",
    "ربع سکه": "🥉 ربع‌سکه", "ربع‌سکه": "🥉 ربع‌سکه",
    "طلای ۱۸": "✨ طلای ۱۸ عیار", "طلای 18": "✨ طلای ۱۸ عیار",
    "طلای ۲۴": "💛 طلای ۲۴ عیار", "طلای 24": "💛 طلای ۲۴ عیار",
    "مثقال": "⚖️ مثقال طلا", "انس": "🌍 انس جهانی طلا", "اونس": "🌍 انس جهانی طلا",
    "تتر": "🟢 تتر", "بیت‌کوین": "🟠 بیت‌کوین", "بیت کوین": "🟠 بیت‌کوین",
    "اتریوم": "🟣 اتریوم",
}
CHANNEL_KEY = "prices:channel"
CHANNEL_WEB_KEY = "prices:web"


def _to_en_digits(text: str) -> str:
    return "".join("0123456789"["۰۱۲۳۴۵۶۷۸۹".index(c)] if c in "۰۱۲۳۴۵۶۷۸۹" else c
                   for c in text)


def parse_prices(text: str) -> list[tuple[str, float, str]]:
    """استخراج قیمت از متن یک کانال (مثل «💵 دلار: ۱۰۸,۵۰۰ تومان»).

    خروجی: (برچسب، مقدار، واحد) — واحد یا «تومان» است یا «دلار».
    """
    rows: list[tuple[str, float, str]] = []
    seen: set[str] = set()
    number_re = re.compile(r"[\d۰-۹][\d۰-۹,\.\s]{2,}")

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line or len(line) > 200:
            continue
        for key, label in CHANNEL_LABELS.items():
            if key not in line or label in seen:
                continue
            # فقط عددی که «بعد از برچسب» آمده را می‌گیریم (نه عددِ خود برچسب)
            position = line.find(key)
            segment = line[position + len(key):]
            found = number_re.findall(segment) or number_re.findall(line)
            if not found:
                continue
            number = _to_en_digits(found[0].replace(",", "").replace("٬", "").replace(" ", "").strip())
            try:
                value = float(number)
            except ValueError:
                continue
            if value <= 0:
                continue

            unit = "تومان"
            if "ریال" in line:
                value /= 10
            elif ("دلار" in line or "$" in line) and not any(
                    word in line for word in ("تومان", "ریال")):
                unit = "دلار"

            if unit == "تومان" and value < 50:      # عدد غیرمنطقی
                continue
            rows.append((label, value, unit))
            seen.add(label)
            break
    return rows


def save_channel_prices(db, text: str) -> int:
    """ذخیره‌ی قیمت‌های استخراج‌شده از کانال (برای استفاده در گزارش)."""
    rows = parse_prices(text)
    if not rows:
        return 0
    payload = {"ts": time.time(), "rows": [list(row) for row in rows]}
    db.set_setting(CHANNEL_KEY, json.dumps(payload, ensure_ascii=False))
    return len(rows)


def channel_prices(db, max_age: int = 2400) -> list[tuple[str, str, float]]:
    """خواندن قیمت‌های کانال اگر تازه باشند (پیش‌فرض: ۴۰ دقیقه)."""
    raw = db.get_setting(CHANNEL_KEY, "")
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if time.time() - float(payload.get("ts", 0)) > max_age:
        return []
    rows = []
    for item in payload.get("rows", []):
        if len(item) == 2:
            label, value = item
            unit = "تومان"
        else:
            label, value, unit = item
        rows.append((label, f"{money(round(float(value)))} {unit}", float(value)))
    return rows


def _clean_number(raw: str) -> float | None:
    """تبديل رشته‌ی عددیِ شلخته به عدد (با حذف نیم‌فاصله، کاما و فاصله)."""
    text = str(raw or "")
    for junk in ("\u200c", "\u200f", "\u200e", "،", ",", " ", "\u00a0", "\u0640", "٬"):
        text = text.replace(junk, "")
    text = "".join("0123456789."["۰۱۲۳۴۵۶۷۸۹.".index(c)] if c in "۰۱۲۳۴۵۶۷۸۹." else c
                   for c in text)
    try:
        return float(text)
    except ValueError:
        return None


# بازه‌های مجاز برای جلوگیری از نمایش عدد اشتباه (تومان / دلار)
VALID_TOMAN = {
    "💵 دلار": (20_000, 5_000_000),
    "💶 یورو": (20_000, 8_000_000),
    "💷 پوند": (20_000, 8_000_000),
    "🕌 درهم": (5_000, 2_000_000),
    "🇹🇷 لیر": (100, 500_000),
    "🇨🇳 یوان": (1_000, 2_000_000),
    "🇨🇦 دلار کانادا": (10_000, 5_000_000),
    "🇦🇺 دلار استرالیا": (10_000, 5_000_000),
    "🪙 سکه امامی": (1_000_000, 3_000_000_000),
    "✨ طلای ۱۸ عیار": (500_000, 1_000_000_000),
    "💛 طلای ۲۴ عیار": (500_000, 1_000_000_000),
    "⚖️ مثقال طلا": (1_000_000, 2_000_000_000),
    "🟢 تتر": (20_000, 5_000_000),
    "💸 دلار فردایی": (20_000, 5_000_000),
}
VALID_USD = {
    "🟠 بیت\u200cکوین": (1_000, 2_000_000),
    "🟣 اتریوم": (100, 200_000),
    "🌍 انس جهانی طلا": (300, 50_000),
}
# ترتیب مهم است: عبارت‌های خاص اول بررسی می‌شوند
KEY_ORDER = (
    ("دلار کانادا", "🇨🇦 دلار کانادا"), ("دلار استرالیا", "🇦🇺 دلار استرالیا"),
    ("دلار فردایی", "💸 دلار فردایی"), ("دلار", "💵 دلار"), ("یورو", "💶 یورو"),
    ("پوند", "💷 پوند"), ("درهم", "🕌 درهم"), ("لیر", "🇹🇷 لیر"), ("یوان", "🇨🇳 یوان"),
    ("سکه امامی", "🪙 سکه امامی"), ("سکه", "🪙 سکه امامی"),
    ("طلای ۱۸", "✨ طلای ۱۸ عیار"), ("طلای 18", "✨ طلای ۱۸ عیار"),
    ("طلای ۲۴", "💛 طلای ۲۴ عیار"), ("طلای 24", "💛 طلای ۲۴ عیار"),
    ("مثقال", "⚖️ مثقال طلا"), ("تتر", "🟢 تتر"),
    ("بیت\u200cکوین", "🟠 بیت\u200cکوین"), ("بیت کوین", "🟠 بیت\u200cکوین"),
    ("اتریوم", "🟣 اتریوم"), ("انس", "🌍 انس جهانی طلا"), ("اونس", "🌍 انس جهانی طلا"),
)
SUMMARY_RE = re.compile(r"([^\d\n:]{2,50}):\s*([\d۰-۹][\d۰-۹,\.\s]{2,20})\s*(تومان|ریال|دلار)?")
FUTURE_RE = re.compile(r"([\d۰-۹][\d۰-۹,\s]{4,20})\s*(?:تومان)?\s*(?:خـ?رید|فروش|معامله)")


def _canonical(text: str) -> str | None:
    for needle, label in KEY_ORDER:
        if needle in text:
            return label
    return None


def _valid(label: str, value: float, unit: str) -> bool:
    if unit == "دلار":
        low, high = VALID_USD.get(label, (0, float("inf")))
    else:
        low, high = VALID_TOMAN.get(label, (0, float("inf")))
    return low <= value <= high


def extract_channel_rows(text: str) -> list[tuple[str, float, str]]:
    """استخراج ایمنِ قیمت از یک پیامِ کانال (با اعتبارسنجی بازه)."""
    rows: list[tuple[str, float, str]] = []
    seen: set[str] = set()

    # ۱) خطوطِ «برچسب: عدد واحد»
    for line in (text or "").splitlines():
        match = SUMMARY_RE.search(line)
        if not match:
            continue
        label = _canonical(match.group(1))
        if not label or label in seen:
            continue
        value = _clean_number(match.group(2))
        if not value:
            continue
        unit = match.group(3) or "تومان"
        if "ریال" in line:
            value, unit = value / 10, "تومان"
        # ارزهایی که معمولاً به دلارند (بیت‌کوین، اتریوم، انس)
        if unit == "تومان" and label in VALID_USD:
            low, high = VALID_USD[label]
            if low <= value <= high:
                unit = "دلار"
        if not _valid(label, value, unit):
            continue
        rows.append((label, value, unit))
        seen.add(label)

    # ۲) الگوی «دلار فردایی تهران 💵 233,300 معامله»
    if "💸 دلار فردایی" not in seen:
        for line in (text or "").splitlines():
            if "فردایی" not in line:
                continue
            found = re.findall(r"[\d۰-۹][\d۰-۹,\s]{4,20}", line)
            if not found:
                continue
            value = _clean_number(found[-1])
            if value and _valid("💸 دلار فردایی", value, "تومان"):
                rows.append(("💸 دلار فردایی", value, "تومان"))
                seen.add("💸 دلار فردایی")
                break

    return rows


def fetch_channel_web(username: str | None = None,
                      max_age: int = 600) -> list[tuple[str, str, float]]:
    """خواندن آخرین قیمت‌ها از پیش\u200cنمایش عمومی یک کانال تلگرام.

    فقط کانال‌های عمومی (که ‎t.me/s/<username>‎ دارند) قابل خواندن هستند
    و نتیجه تا ۱۰ دقیقه کش می‌شود تا به تلگرام فشار نیاید.
    """
    from .http import get_text

    name = (username or getattr(config, "PRICE_CHANNEL", "") or "").lstrip("@").strip()
    if not name:
        return []

    cached = _cache_read(CHANNEL_WEB_KEY, max_age)
    if cached is not None:
        return cached

    try:
        html = get_text(f"https://t.me/s/{name}", timeout=18)
    except Exception:
        return []
    blocks = re.findall(
        r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', html or "", re.S)
    stamps = re.findall(r'<time[^>]*datetime="([^"]+)"', html or "")
    if not blocks:
        return []

    def strip_tags(chunk: str) -> str:
        chunk = re.sub(r"<br\s*/?>", "\n", chunk)
        chunk = re.sub(r"<[^>]+>", "", chunk)
        for code, char in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                           ("&#33;", "!"), ("&rlm;", "")):
            chunk = chunk.replace(code, char)
        return chunk.strip()

    latest: dict[str, tuple[float, str]] = {}
    for block in reversed(blocks):          # از جدید به قدیم
        for label, value, unit in extract_channel_rows(strip_tags(block)):
            latest.setdefault(label, (value, unit))
        if len(latest) >= 8:
            break

    rows = [(label, f"{money(round(value))} {unit}", value)
            for label, (value, unit) in latest.items()]
    if rows:
        _cache_write(CHANNEL_WEB_KEY, rows, stamps[-1] if stamps else "")
    return rows


def channel_stamp() -> str:
    """زمان آخرین پیامی که از کانال خوانده شده (رشته‌ی آماده‌ی نمایش)."""
    _, stamp = _CACHE.get(CHANNEL_WEB_KEY + ":stamp", (0, ""))
    return str(stamp or "")


def _cache_read(key: str, max_age: int):
    import time as _t
    stamp, rows = _CACHE.get(key, ("", None))
    if rows is None or _t.time() - float(stamp or 0) > max_age:
        return None
    return rows


def _cache_write(key: str, rows, stamp: str = "") -> None:
    import time as _t
    _CACHE[key] = (_t.time(), rows)
    _CACHE[key + ":stamp"] = (_t.time(), stamp)


_CACHE: dict = {}


def _to_toman(value: float, unit: str) -> float:
    if unit == "irr":
        return value / 10.0
    return float(value)


def _fmt(value: float, unit: str) -> str:
    if unit == "usd":
        return f"{money(round(value, 2))} دلار"
    return f"{money(round(_to_toman(value, unit)))} تومان"


def fetch_tgju() -> list[tuple[str, str, float]]:
    """دریافت نرخ‌ها از TGJU."""
    data = get_json(TGJU_URL, timeout=10)
    rows: list[tuple[str, str, float]] = []
    for key, (label, unit) in TGJU_MAP.items():
        raw = (data or {}).get(key)
        if isinstance(raw, dict):
            value = raw.get("p") or raw.get("price") or raw.get("value")
        else:
            value = raw
        try:
            value = float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            continue
        if value <= 0:
            continue
        rows.append((label, _fmt(value, unit), value))
    return rows


def fetch_crypto() -> list[tuple[str, str, float]]:
    ids = ",".join(CRYPTO_IDS)
    data = get_json(CRYPTO_URL, params={"ids": ids, "vs_currencies": "usd"}, timeout=10)
    rows = []
    for coin_id, label in CRYPTO_IDS.items():
        value = ((data or {}).get(coin_id) or {}).get("usd")
        if value:
            rows.append((label, f"{money(round(float(value), 2))} دلار", float(value)))
    return rows


def fetch_forex() -> list[tuple[str, str, float]]:
    data = get_json(FOREX_URL, timeout=10)
    rates = (data or {}).get("rates") or {}
    rows = []
    for code, label in (("USD", "💵 دلار"), ("EUR", "💶 یورو"), ("GBP", "💷 پوند"),
                        ("AED", "🕌 درهم"), ("TRY", "🇹🇷 لیر"), ("CNY", "🇨🇳 یوان"),
                        ("JPY", "🇯🇵 ین (۱۰۰ واحد)"), ("CHF", "🇨🇭 فرانک")):
        value = rates.get(code)
        rows.append((label, f"{money(round(float(value), 1))} ریال", float(value)))
    return rows


def market_report() -> str:
    """گزارش کامل بازار (ارز + طلا + سکه + ارز دیجیتال)."""
    blocks: list[str] = []
    try:
        rows = fetch_tgju()
        if rows:
            blocks.append("💰 نرخ ارز و طلا (تومان)")
            blocks.append("───────────────")
            blocks += [f"{label} : {text}" for label, text, _ in rows]
    except ServiceError:
        try:
            rows = fetch_forex()
            blocks.append("💰 نرخ ارزها (بر اساس نرخ رسمی)")
            blocks.append("───────────────")
            blocks += [f"{label} : {text}" for label, text, _ in rows]
        except ServiceError:
            blocks.append("⚠️ دریافت نرخ ارز در این لحظه ممکن نیست.\nچند دقیقه‌ی دیگر دوباره امتحان کن.")

    try:
        crypto = fetch_crypto()
        if crypto:
            blocks.append("───────────────")
            blocks.append("🪙 ارزهای دیجیتال")
            blocks += [f"{label} : {text}" for label, text, _ in crypto]
    except ServiceError:
        pass

    if not blocks:
        raise ServiceError("هیچ منبعی در دسترس نبود")
    return "\n".join(blocks)


def single_asset(query: str) -> str:
    """جستجوی یک دارایی خاص: «قیمت بیت‌کوین»، «دلار»، «طلا»…"""
    key = (query or "").strip().lower()
    if not key:
        return market_report()

    crypto_id = CRYPTO_FA.get(key.replace("قیمت", "").strip())
    if crypto_id:
        data = get_json(CRYPTO_URL, params={"ids": crypto_id, "vs_currencies": "usd,irr"},
                        timeout=10)
        payload = (data or {}).get(crypto_id) or {}
        usd = payload.get("usd")
        if usd is None:
            raise ServiceError("قیمت این ارز در دسترس نیست")
        return (
            f"{CRYPTO_IDS.get(crypto_id, '🪙 ' + crypto_id)}\n"
            "───────────────\n"
            f"💲 قیمت: {money(round(float(usd), 2))} دلار"
        )

    code = FOREX_FA.get(key.replace("قیمت", "").strip())
    if code:
        try:
            for label, text, _ in fetch_tgju():
                pass
        except ServiceError:
            pass
        return market_report()

    return market_report()
