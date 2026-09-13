"""ساعت جهانی و تاریخ شمسی."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..core.utils import PERSIAN_WEEKDAYS, en_to_fa, gregorian_to_jalali, jalali_date

CITIES = {
    "تهران": "Asia/Tehran", "لندن": "Europe/London", "استانبول": "Europe/Istanbul",
    "دبی": "Asia/Dubai", "نیویورک": "America/New_York", "لس‌آنجلس": "America/Los_Angeles",
    "توکیو": "Asia/Tokyo", "پکن": "Asia/Shanghai", "مسکو": "Europe/Moscow",
    "پاریس": "Europe/Paris", "برلین": "Europe/Berlin", "فرانکفورت": "Europe/Berlin",
    "مکه": "Asia/Riyadh", "دوحه": "Asia/Qatar", "سئول": "Asia/Seoul",
    "بمبئی": "Asia/Kolkata", "سیدنی": "Australia/Sydney", "تورنتو": "America/Toronto",
}

# ساعتِ رسمی ایران ثابت است (UTC+3:30) و تغییر ساعت تابستانی ندارد
TEHRAN = timezone(timedelta(hours=3, minutes=30))


def _zone(name: str):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def tehran_time() -> datetime:
    return datetime.now(TEHRAN)


def city_time(city: str) -> tuple[str, str, str] | None:
    """برگرداندن (نام شهر، ساعت، تاریخ شمسی/میلادی)."""
    zone_name = CITIES.get(city.strip())
    if not zone_name:
        return None
    zone = _zone(zone_name)
    now = datetime.now(zone) if zone else tehran_time()
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    date_text = f"{en_to_fa(jd)}/{en_to_fa(jm):0>2}/{en_to_fa(jy)}"
    weekday = PERSIAN_WEEKDAYS[(now.weekday() + 2) % 7]
    return city, en_to_fa(now.strftime("%H:%M")), f"{weekday} {date_text}"


def world_clock() -> str:
    lines = ["🕓 ساعت جهانی", "───────────────"]
    for city in list(CITIES)[:12]:
        info = city_time(city)
        if info:
            lines.append(f"▫️ {city}: {info[1]}")
    return "\n".join(lines)


def now_report() -> str:
    now = tehran_time()
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    weekday = PERSIAN_WEEKDAYS[(now.weekday() + 2) % 7]
    return (
        "🕰 زمان و تاریخ\n"
        "───────────────\n"
        f"🇮🇷 تهران: {en_to_fa(now.strftime('%H:%M:%S'))}\n"
        f"📅 {weekday} {en_to_fa(jd)}/{en_to_fa(jm):0>2}/{en_to_fa(jy)}\n"
        f"🌍 UTC: {en_to_fa(datetime.now(timezone.utc).strftime('%H:%M'))}"
    )
