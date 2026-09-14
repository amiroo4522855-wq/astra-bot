"""ساخت کلاینت مناسب بر اساس پلتفرم (روبیکا / تلگرام)."""
from __future__ import annotations

from .. import config
from .client import RubikaClient
from .telegram import TelegramClient, detect_platform


def resolve_platform(platform: str | None = None, token: str | None = None) -> str:
    """تعیین پلتفرم: از آرگومان، از تنظیمات یا از روی قالب توکن."""
    chosen = (platform or config.PLATFORM or "auto").lower()
    if chosen in ("rubika", "telegram"):
        return chosen
    probe = token or (config.TELEGRAM_BOT_TOKEN or config.BOT_TOKEN)
    return detect_platform(probe)


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
