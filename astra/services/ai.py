"""لایه‌ی هوش مصنوعی: چت، تصویرساز، ترجمه و خلاصه‌ساز.

سازگار با هر سرویس OpenAI-like (OpenAI، Together، Groq، LocalAI و…).
اگر کلید تنظیم نشده باشد، پیام راهنما داده می‌شود نه خطای خام.
"""
from __future__ import annotations

from urllib.parse import quote

from .. import config
from ..core.utils import chunk_text
from .http import ServiceError, get_bytes, request


class AIError(Exception):
    """خطای هوش مصنوعی."""


def _headers() -> dict:
    if not config.AI_API_KEY:
        raise AIError("کلید هوش مصنوعی تنظیم نشده است")
    return {"Authorization": f"Bearer {config.AI_API_KEY}",
            "Content-Type": "application/json"}


def chat(messages: list[dict], temperature: float = 0.7,
         max_tokens: int | None = None) -> str:
    """ارسال گفتگو به مدل و دریافت پاسخ."""
    if not config.AI_API_KEY:
        raise AIError("کلید هوش مصنوعی تنظیم نشده است")
    payload = {
        "model": config.AI_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens or config.AI_MAX_TOKENS,
    }
    try:
        data = request(f"{config.AI_BASE_URL.rstrip('/')}/chat/completions",
                       method="POST", json_body=payload, headers=_headers(), timeout=90)
    except ServiceError as exc:
        raise AIError(f"ارتباط با سرویس هوش مصنوعی برقرار نشد: {exc}") from exc
    choices = (data or {}).get("choices") or []
    if not choices:
        raise AIError("پاسخی از مدل دریافت نشد")
    return (choices[0].get("message") or {}).get("content", "").strip()


def ask(question: str, system: str | None = None) -> str:
    return chat([
        {"role": "system", "content": system or config.AI_SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ])


def translate(text: str, target: str = "انگلیسی") -> str:
    prompt = (
        f"متن زیر را به {target} روان و طبیعی ترجمه کن. "
        "فقط خود ترجمه را بنویس، بدون توضیح اضافه:\n\n" + text[:3000]
    )
    return chat([
        {"role": "system", "content": "تو یک مترجم حرفه‌ای و دقیق هستی."},
        {"role": "user", "content": prompt},
    ], temperature=0.3)


def summarize(text: str) -> str:
    prompt = (
        "متن زیر را در ۳ تا ۵ سطر، ساده و خوانا خلاصه کن. "
        "از bullet استفاده کن:\n\n" + text[:6000]
    )
    return chat([
        {"role": "system", "content": "تو یک خلاصه‌ساز حرفه‌ای فارسی هستی."},
        {"role": "user", "content": prompt},
    ], temperature=0.4)


def image_bytes(prompt: str, size: str = "1024x1024") -> bytes:
    """تولید تصویر؛ پیش‌فرض از سرویس رایگان Pollinations استفاده می‌کند."""
    url = f"{config.AI_IMAGE_URL.rstrip('/')}/{quote(prompt)}"
    try:
        return get_bytes(url, params={"width": 1024, "height": 1024, "nologo": "true"},
                         timeout=120)
    except ServiceError as exc:
        raise AIError(f"ساخت تصویر ناموفق بود: {exc}") from exc


def split_long(text: str) -> list[str]:
    return chunk_text(text, 3000)
