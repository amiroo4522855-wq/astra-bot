"""تبدیل واحد: طول، وزن، دما، زمان، حجم، داده، سرعت و مساحت."""
from __future__ import annotations

from ..core.utils import en_to_fa, fa_to_en

# واحدها بر اساس ضریب تبدیل به واحد پایه هر دسته
UNITS: dict[str, dict[str, tuple[str, float, float]]] = {
    "length": {
        # کلید: (نام فارسی، ضریب، مقدار ثابتِ اضافه)
        "m": ("متر", 1.0, 0.0), "cm": ("سانتی‌متر", 0.01, 0.0),
        "mm": ("میلی‌متر", 0.001, 0.0), "km": ("کیلومتر", 1000.0, 0.0),
        "in": ("اینچ", 0.0254, 0.0), "ft": ("فوت", 0.3048, 0.0),
        "yd": ("یارد", 0.9144, 0.0), "mi": ("مایل", 1609.344, 0.0),
    },
    "mass": {
        "kg": ("کیلوگرم", 1.0, 0.0), "g": ("گرم", 0.001, 0.0),
        "mg": ("میلی‌گرم", 1e-6, 0.0), "lb": ("پوند", 0.45359237, 0.0),
        "oz": ("اونس", 0.0283495231, 0.0), "ton": ("تن", 1000.0, 0.0),
    },
    "time": {
        "s": ("ثانیه", 1.0, 0.0), "min": ("دقیقه", 60.0, 0.0),
        "h": ("ساعت", 3600.0, 0.0), "d": ("روز", 86400.0, 0.0),
        "w": ("هفته", 604800.0, 0.0), "mo": ("ماه", 2592000.0, 0.0),
        "y": ("سال", 31536000.0, 0.0),
    },
    "data": {
        "b": ("بایت", 1.0, 0.0), "kb": ("کیلوبایت", 1024.0, 0.0),
        "mb": ("مگابایت", 1024.0 ** 2, 0.0), "gb": ("گیگابایت", 1024.0 ** 3, 0.0),
        "tb": ("ترابایت", 1024.0 ** 4, 0.0),
    },
    "speed": {
        "ms": ("متر بر ثانیه", 1.0, 0.0), "kmh": ("کیلومتر بر ساعت", 0.2777778, 0.0),
        "mph": ("مایل بر ساعت", 0.44704, 0.0), "kn": ("گره دریایی", 0.514444, 0.0),
    },
    "area": {
        "m2": ("متر مربع", 1.0, 0.0), "km2": ("کیلومتر مربع", 1_000_000.0, 0.0),
        "ha": ("هکتار", 10_000.0, 0.0), "ft2": ("فوت مربع", 0.092903, 0.0),
        "acre": ("جریب", 4046.86, 0.0),
    },
    "volume": {
        "l": ("لیتر", 1.0, 0.0), "ml": ("میلی‌لیتر", 0.001, 0.0),
        "m3": ("متر مکعب", 1000.0, 0.0), "cup": ("پیمانه", 0.24, 0.0),
        "gal": ("گالن آمریکایی", 3.78541, 0.0),
    },
}

CATEGORY_LABELS = {
    "length": "📏 طول", "mass": "⚖️ وزن", "temperature": "🌡 دما",
    "time": "⏱ زمان", "data": "💾 داده", "speed": "🚀 سرعت",
    "area": "🗺 مساحت", "volume": "🧪 حجم",
}

TEMP_UNITS = {"c": "سانتی‌گراد", "f": "فارنهایت", "k": "کلوین"}

# نام‌های جایگزین فارسی/انگلیسی
ALIASES = {
    "متر": "m", "سانت": "cm", "سانتی متر": "cm", "سانتی‌متر": "cm", "کیلومتر": "km",
    "کیلو متر": "km", "اینچ": "in", "فوت": "ft", "یارد": "yd", "مایل": "mi",
    "کیلوگرم": "kg", "کیلو گرم": "kg", "کیلو": "kg", "گرم": "g", "پوند": "lb",
    "اونس": "oz", "تن": "ton", "ثانیه": "s", "دقیقه": "min", "ساعت": "h",
    "روز": "d", "هفته": "w", "ماه": "mo", "سال": "y", "بایت": "b",
    "کیلوبایت": "kb", "مگابایت": "mb", "گیگابایت": "gb", "ترابایت": "tb",
    "سانتیگراد": "c", "سانتی‌گراد": "c", "فارنهایت": "f", "کلوین": "k",
    "celsius": "c", "fahrenheit": "f", "kelvin": "k", "meter": "m", "kilometer": "km",
}


def _normalize(token: str) -> str:
    token = fa_to_en(token).strip().lower().replace("°", "")
    return ALIASES.get(token, token)


def find_category(unit: str) -> str | None:
    if unit in TEMP_UNITS:
        return "temperature"
    for category, units in UNITS.items():
        if unit in units:
            return category
    return None


def convert(value: float, source: str, target: str) -> float:
    """تبدیل مقدار از یک واحد به واحد دیگر."""
    if source in TEMP_UNITS and target in TEMP_UNITS:
        return _convert_temp(value, source, target)
    category = find_category(source)
    if not category or category == "temperature":
        raise ValueError("واحد مبدا پشتیبانی نمی‌شود")
    if target not in UNITS[category]:
        raise ValueError("واحد مقصد با مبدا هم‌خانواده نیست")
    base = value * UNITS[category][source][1]
    return base / UNITS[category][target][1]


def _convert_temp(value: float, source: str, target: str) -> float:
    if source == target:
        return value
    if source == "c":
        celsius = value
    elif source == "f":
        celsius = (value - 32) * 5 / 9
    else:
        celsius = value - 273.15
    if target == "c":
        return celsius
    if target == "f":
        return celsius * 9 / 5 + 32
    return celsius + 273.15


def unit_label(unit: str) -> str:
    if unit in TEMP_UNITS:
        return TEMP_UNITS[unit]
    for units in UNITS.values():
        if unit in units:
            return units[unit][0]
    return unit


def pretty(value: float) -> str:
    if value == 0:
        return "0"
    if abs(value) >= 1000 or abs(value) < 0.001:
        return f"{value:.4g}"
    return f"{value:.6g}"


def convert_text(text: str) -> str:
    """تبدیل یک عبارت متنی: «10 کیلومتر به متر» یا «100 f to c»."""
    cleaned = fa_to_en(text).strip()
    cleaned = cleaned.replace("به", " to ").replace("→", " to ")
    parts = [p for p in cleaned.replace("  ", " ").split() if p]
    if len(parts) < 3:
        raise ValueError("فرمت درست نیست")
    value = float(parts[0].replace(",", ""))
    source = _normalize(parts[1])
    target = _normalize(parts[-1])
    result = convert(value, source, target)
    return (f"🔄 تبدیل واحد\n───────────────\n"
            f"▫️ {en_to_fa(pretty(value))} {unit_label(source)}\n"
            f"▫️ برابر است با:\n"
            f"✨ {en_to_fa(pretty(result))} {unit_label(target)}")
