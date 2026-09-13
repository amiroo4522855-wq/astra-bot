"""کوتاه‌کننده‌ی لینک."""
from __future__ import annotations

from urllib.parse import quote

from .. import config
from .http import ServiceError, get_text


def shorten(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    providers = (
        (config.SHORTLINK_API, {"url": url}),
        ("https://is.gd/create.php", {"format": "simple", "url": url}),
    )
    last_error: Exception | None = None
    for endpoint, params in providers:
        try:
            result = get_text(endpoint, params=params, timeout=12).strip()
            if result.startswith("http"):
                return result
            last_error = ServiceError(result[:80])
        except ServiceError as exc:
            last_error = exc
    raise ServiceError(f"کوتاه‌سازی ناموفق بود ({last_error})")
