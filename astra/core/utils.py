"""ابزارهای کمکی: تاریخ شمسی، اعداد فارسی، قالب‌بندی متن و …"""
from __future__ import annotations

import math
import re
import time
from datetime import datetime, timedelta, timezone

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
PERSIAN_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]
PERSIAN_WEEKDAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]

SEPARATOR = "───────────────"
SPACER = "\u200b"  # نیم‌فاصله‌ی نامرئی برای جلوگیری از به‌هم‌ریختگی


# --------------------------------------------------------------------------- #
# اعداد و ارقام
# --------------------------------------------------------------------------- #
def en_to_fa(text: str) -> str:
    """تبدیل ارقام انگلیسی و عربی به فارسی."""
    if text is None:
        return ""
    text = str(text)
    for src in (ARABIC_DIGITS, PERSIAN_DIGITS):
        pass
    table = str.maketrans({**{ARABIC_DIGITS[i]: PERSIAN_DIGITS[i] for i in range(10)},
                           **{str(i): PERSIAN_DIGITS[i] for i in range(10)}})
    return text.translate(table)


def fa_to_en(text: str) -> str:
    """تبدیل ارقام فارسی/عربی به انگلیسی (برای محاسبات)."""
    if text is None:
        return ""
    table = str.maketrans({**{PERSIAN_DIGITS[i]: str(i) for i in range(10)},
                           **{ARABIC_DIGITS[i]: str(i) for i in range(10)},
                           "٫": ".", "،": "", " ": "", "_": ""})
    return str(text).translate(table)


def money(value: float | int | str, unit: str = "") -> str:
    """قالب‌بندی عدد با جداکننده‌ی هزارگان و ارقام فارسی."""
    try:
        number = float(fa_to_en(str(value)))
    except (TypeError, ValueError):
        return en_to_fa(str(value))
    if number == int(number):
        text = f"{int(number):,}"
    else:
        text = f"{number:,.2f}".rstrip("0").rstrip(".")
    return en_to_fa(text).replace(",", "\u066c") + (f" {unit}" if unit else "")


def normalize_digits(text: str) -> str:
    return fa_to_en(text)


def digits_to_en(text: str) -> str:
    """تبدیل ارقام فارسی/عربی به انگلیسی **بدون دست‌زدن به فاصله‌ها**.

    برای عباراتی مثل «10 کیلومتر به متر» که باید ساختار جمله حفظ شود.
    """
    if text is None:
        return ""
    table = {**{PERSIAN_DIGITS[i]: str(i) for i in range(10)},
             **{ARABIC_DIGITS[i]: str(i) for i in range(10)}}
    return str(text).translate(str.maketrans(table))


# --------------------------------------------------------------------------- #
# تاریخ شمسی
# --------------------------------------------------------------------------- #
def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """تبدیل استاندارد میلادی به شمسی (الگوریتم رایج و دقیق)."""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gm > 2:
        gy2 = gy + 1
    else:
        gy2 = gy
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) \
        + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def jalali_date(ts: int | None = None, with_weekday: bool = True) -> str:
    now = datetime.fromtimestamp(ts or time.time())
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    text = f"{en_to_fa(jd)} {PERSIAN_MONTHS[jm - 1]} {en_to_fa(jy)}"
    if with_weekday:
        text = f"{PERSIAN_WEEKDAYS[(now.weekday() + 2) % 7]} {text}"
    return text


def jalali_full(ts: int | None = None) -> str:
    now = datetime.fromtimestamp(ts or time.time())
    return f"{jalali_date(ts)} · ساعت {en_to_fa(now.strftime('%H:%M'))}"


def human_time(ts: int | None = None) -> str:
    now = datetime.fromtimestamp(ts or time.time())
    return f"{jalali_date(ts, with_weekday=False)} - {en_to_fa(now.strftime('%H:%M'))}"


# --------------------------------------------------------------------------- #
# متن
# --------------------------------------------------------------------------- #
def clean(text: str) -> str:
    """حذف فاصله‌های اضافی و نرمال‌سازی کاراکترهای عربی."""
    if not text:
        return ""
    text = str(text).replace("ي", "ی").replace("ك", "ک").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def truncate(text: str, length: int = 120, suffix: str = "…") -> str:
    text = clean(text)
    return text if len(text) <= length else text[:length].rstrip() + suffix


def chunk_text(text: str, size: int = 3500) -> list[str]:
    """تکه‌تکه کردن پیام‌های خیلی طولانی (محدودیت پیام روبیکا)."""
    text = text or ""
    if len(text) <= size:
        return [text] if text else []
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > size:
            if current:
                chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


def bullet(items: list[str], marker: str = "▫️") -> str:
    return "\n".join(f"{marker} {item}" for item in items if item)


def numbered(items: list[str], start: int = 1) -> str:
    out = []
    for i, item in enumerate(items, start=start):
        out.append(f"{en_to_fa(i)}️⃣ {item}")
    return "\n".join(out)


def progress_bar(value: float, maximum: float, length: int = 10) -> str:
    if maximum <= 0:
        return "░" * length
    ratio = max(0.0, min(1.0, value / maximum))
    filled = int(round(ratio * length))
    return "▓" * filled + "░" * (length - filled)


def escape_html(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# --------------------------------------------------------------------------- #
# تشخیص ورودی
# --------------------------------------------------------------------------- #
URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)


def extract_url(text: str) -> str:
    match = URL_RE.search(text or "")
    return match.group(0) if match else ""


def is_url(text: str) -> bool:
    return bool(URL_RE.fullmatch((text or "").strip()))


def parse_number(text: str) -> float | None:
    try:
        return float(fa_to_en(text).replace(",", ""))
    except (TypeError, ValueError):
        return None


def day_index(ts: int | None = None) -> int:
    """شماره‌ی یکتای روز (برای چالش روزانه و فال روزانه)."""
    now = datetime.fromtimestamp(ts or time.time())
    return now.timetuple().tm_yday + now.year * 366


def tehran_now() -> datetime:
    """زمان تهران (Asia/Tehran = UTC+3:30 بدون DST)."""
    return datetime.now(timezone(timedelta(hours=3, minutes=30)))


def format_duration(seconds: float) -> str:
    seconds = int(max(0, seconds))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{en_to_fa(hours)}:{en_to_fa(minutes):0>2}:{en_to_fa(sec):0>2}"
    return f"{en_to_fa(minutes)}:{en_to_fa(sec):0>2}"


def format_size(num_bytes: int | float) -> str:
    if not num_bytes:
        return "0 بایت"
    units = ["بایت", "کیلوبایت", "مگابایت", "گیگابایت"]
    power = int(min(math.log(num_bytes, 1024), len(units) - 1))
    value = num_bytes / (1024 ** power)
    return f"{en_to_fa(round(value, 1))} {units[power]}"


def short_id(user_id: str) -> str:
    return str(user_id)[-6:] if user_id else "------"
