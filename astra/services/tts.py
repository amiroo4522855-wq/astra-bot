"""تبدیل متن به گفتار (Text To Speech)."""
from __future__ import annotations

import io

from .. import config


def synthesize(text: str, lang: str | None = None) -> tuple[bytes, str]:
    """تبدیل متن به فایل صوتی؛ خروجی (بایت‌ها، نام فایل)."""
    try:
        from gtts import gTTS  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "برای تبدیل متن به ویس باید کتابخانه‌ی gTTS نصب باشد: pip install gTTS"
        ) from exc

    buffer = io.BytesIO()
    gTTS(text=text[:900], lang=lang or config.TTS_LANG).write_to_fp(buffer)
    return buffer.getvalue(), "astra-voice.mp3"
