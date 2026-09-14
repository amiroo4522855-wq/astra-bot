"""ساخت کلاینت مناسب بر اساس پلتفرم (روبیکا / تلگرام)."""
from __future__ import annotations

from .. import config
from .client import RubikaClient
from .telegram import TelegramClient, detect_platform


def resolve_platform(platform: str | None = None, token: str | None = None) -> str:
    """تعیین پلتفرم: از آرگومان، از تنظیمات یا از روی قالب توکن.

    اولویت: آرگومان > مقدار PLATFORM در تنظیمات > تشخیص از روی توکن.
    اگر هر دو توکن تنظیم شده باشند و PLATFORM=auto باشد، روبیکا انتخاب
    می‌شود و در بوت‌استرپ یک هشدار چاپ می‌گردد.
    """
    chosen = (platform or config.PLATFORM or "auto").lower()
    if chosen in ("rubika", "telegram"):
        return chosen
    if token:
        return detect_platform(token)
    if config.TELEGRAM_BOT_TOKEN and not config.BOT_TOKEN:
        return "telegram"
    if config.BOT_TOKEN and not config.TELEGRAM_BOT_TOKEN:
        return "rubika"
    return "rubika"


def active_token(platform: str, token: str | None = None) -> str:
    """انتخاب توکنِ درست برای پلتفرم انتخاب‌شده."""
    if token and detect_platform(token) == platform:
        return token
    return config.TELEGRAM_BOT_TOKEN if platform == "telegram" else config.BOT_TOKEN


def create_client(platform: str | None = None, token: str | None = None):
    """برگرداندن نمونه‌ی کلاینت (‎RubikaClient‎ یا ‎TelegramClient‎)."""
    resolved = resolve_platform(platform, token)
    chosen_token = active_token(resolved, token)
    if resolved == "telegram":
        return TelegramClient(chosen_token)
    return RubikaClient(chosen_token)
