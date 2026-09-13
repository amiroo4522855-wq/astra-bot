"""یک لایه‌ی ایمن برای درخواست‌های اینترنتی.

هیچ سرویسی مستقیماً ‎requests‎ صدا نمی‌زند؛ همه از اینجا می‌گذرند تا
مدیریتtimeout، تلاش مجدد و گزارش خطا یکسان باشد.
"""
from __future__ import annotations

from typing import Any

import requests

from .. import config


class ServiceError(Exception):
    """خطای سرویس خارجی (شبکه، کلید نامعتبر، پاسخ خراب...)."""


def request(url: str, *, method: str = "GET", params: dict | None = None,
            json_body: dict | None = None, data: dict | None = None,
            headers: dict | None = None, timeout: int | None = None,
            as_json: bool = True, retries: int = 1) -> Any:
    """اجرای درخواست؛ در صورت خطا ‎ServiceError‎ پرتاب می‌شود."""
    timeout = timeout or config.REQUEST_TIMEOUT
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = requests.request(
                method.upper(), url, params=params, json=json_body, data=data,
                headers=headers, timeout=timeout,
            )
            if response.status_code >= 400:
                raise ServiceError(f"کد پاسخ {response.status_code}")
            if not as_json:
                return response.content
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last = exc
            if attempt < retries:
                continue
    raise ServiceError(f"ارتباط با {url.split('?')[0][:60]} ناموفق بود ({last})")


def get_json(url: str, **kwargs: Any) -> Any:
    return request(url, method="GET", as_json=True, **kwargs)


def get_bytes(url: str, **kwargs: Any) -> bytes:
    return request(url, method="GET", as_json=False, **kwargs)


def get_text(url: str, **kwargs: Any) -> str:
    raw = request(url, method="GET", as_json=False, **kwargs)
    return raw.decode("utf-8", errors="ignore")
