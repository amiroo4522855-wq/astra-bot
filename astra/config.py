"""تنظیمات مرکزی ربات «آسترا».

تمام مقادیر از فایل ‎.env‎ (یا متغیرهای محیطی) خوانده می‌شوند،
پس برای تغییر تنظیمات نیازی به دست زدن به کد نیست.
"""
from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------- #
# مسیرها
# --------------------------------------------------------------------------- #
BASE_DIR: Path = Path(__file__).resolve().parent.parent      # ریشه پروژه
PKG_DIR: Path = BASE_DIR / "astra"                            # پکیج اصلی
DATA_DIR: Path = BASE_DIR / "data"                            # دیتابیس و کش
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_dotenv(path: Path) -> None:
    """خواندن فایل ‎.env‎ بدون نیاز به کتابخانه‌ی جانبی."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(BASE_DIR / ".env")


# --------------------------------------------------------------------------- #
# کمک‌گیرنده‌ها
# --------------------------------------------------------------------------- #
def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def env_int(key: str, default: int) -> int:
    try:
        return int(str(os.environ.get(key, default)).strip())
    except (TypeError, ValueError):
        return default


def env_bool(key: str, default: bool = False) -> bool:
    value = str(os.environ.get(key, "")).strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on", "بله"}


def env_list(key: str, default: str = "") -> list[str]:
    raw = os.environ.get(key, default)
    return [item.strip() for item in raw.replace(";", ",").split(",") if item.strip()]


# --------------------------------------------------------------------------- #
# هویت ربات
# --------------------------------------------------------------------------- #
BOT_NAME = env("BOT_NAME", "آسترا")
BOT_USERNAME = env("BOT_USERNAME", "AstraToolsBot")
BOT_TAGLINE = env("BOT_TAGLINE", "همه ابزارها در یک ربات ✨")
BOT_VERSION = env("BOT_VERSION", "1.0.0")

# توکن ربات (از @BotFather در روبیکا)
BOT_TOKEN = env("BOT_TOKEN", "")
API_BASE = env("API_BASE", "https://botapi.rubika.ir/v3")

# آدرس مینی‌اپ (Telegram Web App) — روی GitHub Pages
APP_URL = env("APP_URL", "https://amiroo4522855-wq.github.io/astra-bot/")
MINIAPP_TEXT = env("MINIAPP_TEXT", "✨ مینی‌اپ")

# تلگرام: توکن از @BotFather تلگرام (قالب: 123456789:AAxxxxxxxx...)
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", "")
# auto | rubika | telegram  (در حالت auto از روی قالب توکن تشخیص داده می‌شود)
PLATFORM = env("PLATFORM", "auto").lower()

# ادمین‌ها (شناسه عددی یا guid کاربر روبیکا) - اولین نفر ادمین اصلی است
ADMIN_IDS: list[str] = env_list("ADMIN_IDS", "")
SUPPORT_ID = env("SUPPORT_ID", ADMIN_IDS[0] if ADMIN_IDS else "")
CHANNEL_ID = env("CHANNEL_ID", "")            # برای جوین اجباری (اختیاری)
CHANNEL_URL = env("CHANNEL_URL", "")

# --------------------------------------------------------------------------- #
# رفتار و عملکرد
# --------------------------------------------------------------------------- #
POLL_INTERVAL = max(1, env_int("POLL_INTERVAL", 2))     # فاصله‌ی بین دو getUpdates
UPDATE_LIMIT = max(1, min(env_int("UPDATE_LIMIT", 50), 100))
REQUEST_TIMEOUT = max(3, env_int("REQUEST_TIMEOUT", 15))
MAX_RETRIES = max(0, env_int("MAX_RETRIES", 2))
WORKERS = max(1, env_int("WORKERS", 8))                 # پردازش موازی آپدیت‌ها
DB_PATH = Path(env("DB_PATH", str(DATA_DIR / "astra.db")))
TEMP_DIR = Path(env("TEMP_DIR", str(DATA_DIR / "tmp")))
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# محدودیت استفاده‌ی رایگان در روز (عدد ۰ یعنی نامحدود)
FREE_LIMITS = {
    "ai_chat": env_int("FREE_LIMIT_AI_CHAT", 15),
    "ai_image": env_int("FREE_LIMIT_AI_IMAGE", 5),
    "download": env_int("FREE_LIMIT_DOWNLOAD", 8),
    "music": env_int("FREE_LIMIT_MUSIC", 10),
    "tts": env_int("FREE_LIMIT_TTS", 8),
    "ocr": env_int("FREE_LIMIT_OCR", 5),
    "qr": env_int("FREE_LIMIT_QR", 20),
}

# --------------------------------------------------------------------------- #
# عضویت ویژه (VIP)
# --------------------------------------------------------------------------- #
VIP_PLANS = {
    "1": {"days": 30, "label": "ماهانه", "price": env("VIP_PRICE_1", "۴۹,۰۰۰ تومان"), "emoji": "🥉"},
    "3": {"days": 90, "label": "سه‌ماهه", "price": env("VIP_PRICE_3", "۱۲۹,۰۰۰ تومان"), "emoji": "🥈"},
    "6": {"days": 180, "label": "شش‌ماهه", "price": env("VIP_PRICE_6", "۲۲۹,۰۰۰ تومان"), "emoji": "🥇"},
}
CARD_NUMBER = env("CARD_NUMBER", "6037-99xx-xxxx-xxxx")
CARD_OWNER = env("CARD_OWNER", "به نام آسترا")
VIP_PERKS = [
    "حذف کامل محدودیت روزانه ابزارها ♾",
    "کیفیت بالاتر در دانلود موزیک و ویدیو 🎧",
    "اولویت در پاسخ‌دهی هوش مصنوعی ⚡",
    "ابزارهای اختصاصی (OCR، تبدیل متن به ویس نامحدود و…) 🛠",
    "پلی‌لیست شخصی با ظرفیت بیشتر 🎵",
]

# --------------------------------------------------------------------------- #
# هوش مصنوعی (سازگار با OpenAI)
# --------------------------------------------------------------------------- #
AI_API_KEY = env("AI_API_KEY", "")
AI_BASE_URL = env("AI_BASE_URL", "https://api.openai.com/v1")
AI_MODEL = env("AI_MODEL", "gpt-4o-mini")
AI_SYSTEM_PROMPT = env(
    "AI_SYSTEM_PROMPT",
    "تو «آسترا» هستی؛ دستیار هوشمند فارسی‌زبان. مهربان، دقیق و کمی بامزه. "
    "پاسخ‌ها کوتاه، خوانا و مرتب با ایموجی مناسب باشند.",
)
AI_IMAGE_URL = env("AI_IMAGE_URL", "https://image.pollinations.ai/prompt")
AI_MAX_TOKENS = env_int("AI_MAX_TOKENS", 700)

# --------------------------------------------------------------------------- #
# سرویس‌های جانبیِ اختیاری
# --------------------------------------------------------------------------- #
SHORTLINK_API = env("SHORTLINK_API", "https://tinyurl.com/api-create.php")
QR_API = env("QR_API", "https://api.qrserver.com/v1/create-qr-code/")
OCR_API_KEY = env("OCR_API_KEY", "helloworld")       # کلید رایگان OCR.space
OCR_LANG = env("OCR_LANG", "fas")
YTDLP_PATH = env("YTDLP_PATH", "yt-dlp")
TTS_LANG = env("TTS_LANG", "fa")
MAX_UPLOAD_MB = max(5, env_int("MAX_UPLOAD_MB", 45))

# --------------------------------------------------------------------------- #
# بخش‌های ربات (قابل خاموش/روشن از پنل ادمین)
# --------------------------------------------------------------------------- #
SECTION_LABELS = {
    "music": "🎵 موزیک",
    "ai": "🤖 هوش مصنوعی",
    "downloader": "📥 دانلودر",
    "tools": "🛠 ابزارها",
    "practical": "🌤 کاربردی",
    "fun": "🎮 سرگرمی",
    "group": "⚙️ مدیریت گروه",
    "vip": "💎 عضویت ویژه",
    "help": "ℹ️ راهنما و پشتیبانی",
}
DEFAULT_SECTION_STATE = {key: True for key in SECTION_LABELS}

# --------------------------------------------------------------------------- #
# متن‌های ثابت
# --------------------------------------------------------------------------- #
MAINTENANCE_MODE = env_bool("MAINTENANCE_MODE", False)
MAINTENANCE_TEXT = env(
    "MAINTENANCE_TEXT",
    "🛠 آسترا در حال به‌روزرسانی است.\nچند دقیقه‌ی دیگر برمی‌گردیم ✨",
)
