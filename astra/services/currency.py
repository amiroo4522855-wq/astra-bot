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
