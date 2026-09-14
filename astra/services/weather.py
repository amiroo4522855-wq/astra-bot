"""آب‌وهوا با استفاده از Open-Meteo (بدون نیاز به کلید)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..core.utils import en_to_fa, money
from .http import ServiceError, get_json

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CITIES_FILE = DATA_DIR / "cities.json"

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# معادل‌سازی نام شهرهای پرکاربرد برای جستجوی دقیق‌تر
CITY_ALIASES = {
    "تهران": "Tehran", "مشهد": "Mashhad", "اصفهان": "Isfahan", "شیراز": "Shiraz",
    "تبریز": "Tabriz", "کرمان": "Kerman", "اهواز": "Ahvaz", "قم": "Qom",
    "کرمانشاه": "Kermanshah", "گرگان": "Gorgan", "رشت": "Rasht", "ساری": "Sari",
    "بندرعباس": "Bandar Abbas", "یزد": "Yazd", "ارومیه": "Urmia", "زاهدان": "Zahedan",
    "سنندج": "Sanandaj", "همدان": "Hamadan", "اردبیل": "Ardabil", "بوشهر": "Bushehr",
    "کرج": "Karaj", "قزوین": "Qazvin", "زنجان": "Zanjan", "بیرجند": "Birjand",
    "خرم‌آباد": "Khorramabad", "لندن": "London", "استانبول": "Istanbul",
    "دبی": "Dubai", "پاریس": "Paris", "برلین": "Berlin", "فرانکفورت": "Frankfurt",
    "کابل": "Kabul", "بغداد": "Baghdad", "نجف": "Najaf", "کربلا": "Karbala",
}

# کدهای وضعیت هوا در Open-Meteo → ترجمه + ایموجی
WMO = {
    0: ("آفتابی", "☀️"), 1: ("کمی ابری", "🌤"), 2: ("نیمه‌ابری", "⛅️"), 3: ("ابری", "☁️"),
    45: ("مه‌آلود", "🌫"), 48: ("مه یخ‌زده", "🌫"), 51: ("نم‌نم باران", "🌦"),
    53: ("باران ملایم", "🌦"), 55: ("باران شدید", "🌧"), 56: ("نم‌نم یخ‌زده", "🌨"),
    57: ("باران یخ‌زده", "🌨"), 61: ("باران سبک", "🌧"), 63: ("باران", "🌧"),
    65: ("باران شدید", "🌧🌧"), 66: ("باران یخ‌زده", "🌨"), 67: ("باران یخ‌زده شدید", "🌨"),
    71: ("برف سبک", "🌨"), 73: ("برف", "❄️"), 75: ("برف شدید", "❄️"),
    77: ("دانه‌های برف", "🌨"), 80: ("رگبار", "🌦"), 81: ("رگبار شدید", "🌧"),
    82: ("رگبار خیلی شدید", "⛈"), 85: ("رگبار برف", "🌨"), 86: ("رگبار برف شدید", "❄️"),
    95: ("رعد و برق", "⛈"), 96: ("رعد و برق با تگرگ", "⛈🧊"),
    99: ("رعد و برق شدید", "⛈🧊"),
}


@dataclass
class Place:
    name: str
    lat: float
    lon: float
    country: str = ""
    admin: str = ""


@dataclass
class Current:
    temp: float
    feels: float
    humidity: int
    wind: float
    code: int


def describe(code: int) -> tuple[str, str]:
    return WMO.get(int(code), ("نامشخص", "🌡"))


def _normalize(name: str) -> str:
    """نرمال‌سازی نام شهر برای تطبیق بهتر."""
    return (name or "").replace("\u200c", "").replace(" ", "").strip().rstrip("ه").lower()


def load_cities() -> list[Place]:
    """خواندن فهرست شهرهای ایران از فایل محلی (۱۶۳ شهر، ۳۰ استان)."""
    if not CITIES_FILE.exists():
        return []
    try:
        data = json.loads(CITIES_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [
        Place(name=item.get("name", ""), lat=float(item.get("lat", 0)),
              lon=float(item.get("lon", 0)), country="IR",
              admin=item.get("province", ""))
        for item in data.get("cities", [])
        if item.get("lat") is not None
    ]


_CITIES_CACHE: list[Place] | None = None


def cities() -> list[Place]:
    """فهرست شهرها (یک بار خوانده و کش می‌شود)."""
    global _CITIES_CACHE
    if _CITIES_CACHE is None:
        _CITIES_CACHE = load_cities()
    return _CITIES_CACHE


def provinces() -> list[str]:
    return sorted({place.admin for place in cities() if place.admin})


def cities_of(province: str) -> list[Place]:
    return [p for p in cities() if p.admin == province]


def find_local(city: str) -> Place | None:
    """جستجوی شهر در فهرست محلی (سریع و بدون اینترنت)."""
    target = _normalize(city)
    if not target:
        return None
    for place in cities():
        if _normalize(place.name) == target:
            return place
    for place in cities():                       # تطبیق جزئی (مثل «بندر» → بندرعباس)
        if target and target in _normalize(place.name):
            return place
    return None


def geocode(city: str) -> Place | None:
    """پیدا کردن مختصات شهر: اول فهرست محلی، بعد سرویس آنلاین."""
    city = (city or "").strip()
    if not city:
        return None
    local = find_local(city)
    if local:
        return local
    query = CITY_ALIASES.get(city, city)
    for name in (query, city):
        try:
            data = get_json(GEO_URL, params={"name": name, "count": 1,
                                             "language": "fa", "format": "json"},
                            timeout=10)
        except ServiceError:
            continue
        results = (data or {}).get("results") or []
        if results:
            first = results[0]
            return Place(
                name=first.get("name") or name,
                lat=float(first.get("latitude")),
                lon=float(first.get("longitude")),
                country=first.get("country") or "",
                admin=first.get("admin1") or "",
            )
    return None


def forecast(place: Place, days: int = 3) -> dict:
    data = get_json(
        FORECAST_URL,
        params={
            "latitude": place.lat,
            "longitude": place.lon,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                       "weather_code,wind_speed_10m,is_day",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "timezone": "auto",
            "forecast_days": days,
        },
        timeout=12,
    )
    current_raw = (data or {}).get("current") or {}
    daily_raw = (data or {}).get("daily") or {}
    return {
        "current": Current(
            temp=float(current_raw.get("temperature_2m", 0)),
            feels=float(current_raw.get("apparent_temperature", 0)),
            humidity=int(current_raw.get("relative_humidity_2m", 0)),
            wind=float(current_raw.get("wind_speed_10m", 0)),
            code=int(current_raw.get("weather_code", 0)),
        ),
        "daily": daily_raw,
        "timezone": (data or {}).get("timezone", ""),
    }


def render(city_query: str) -> str:
    """خروجی آماده‌ی نمایش برای کاربر."""
    place = geocode(city_query)
    if place is None:
        raise ServiceError("شهر پیدا نشد")
    info = forecast(place)
    cur: Current = info["current"]
    label, emoji = describe(cur.code)
    daily = info["daily"] or {}

    lines = [
        f"{emoji} آب‌وهوای {place.name}" + (f" ({place.admin})" if place.admin else ""),
        "───────────────",
        f"🌡 دما: {en_to_fa(round(cur.temp, 1))}°C",
        f"🤔 حس واقعی: {en_to_fa(round(cur.feels, 1))}°C",
        f"💧 رطوبت: {en_to_fa(cur.humidity)}٪",
        f"💨 سرعت باد: {en_to_fa(round(cur.wind, 1))} km/h",
        f"📌 وضعیت: {label}",
    ]

    dates = daily.get("time") or []
    if dates:
        lines.append("───────────────")
        lines.append("📅 پیش‌بینی روزهای آینده:")
        for index, day in enumerate(dates[:3]):
            code = (daily.get("weather_code") or [0])[index]
            high = (daily.get("temperature_2m_max") or [0])[index]
            low = (daily.get("temperature_2m_min") or [0])[index]
            label_day, emoji_day = describe(code)
            lines.append(
                f"▫️ {en_to_fa(day[5:])} · {emoji_day} {label_day} · "
                f"{en_to_fa(round(high))}° / {en_to_fa(round(low))}°"
            )
    return "\n".join(lines)
