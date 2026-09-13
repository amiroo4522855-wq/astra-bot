"""استخراج متن از تصویر (OCR) با استفاده از OCR.space."""
from __future__ import annotations

import base64

from .. import config
from .http import ServiceError, request

OCR_ENDPOINT = "https://api.ocr.space/parse/image"


def extract_text(image_bytes: bytes, language: str | None = None) -> str:
    payload = {
        "apikey": config.OCR_API_KEY,
        "language": language or config.OCR_LANG,
        "isOverlayRequired": False,
        "detectOrientation": True,
        "scale": True,
        "base64Image": "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode(),
    }
    data = request(OCR_ENDPOINT, method="POST", data=payload, timeout=45)
    results = (data or {}).get("ParsedResults") or []
    if not results:
        message = (data or {}).get("ErrorMessage") or "متنی در تصویر پیدا نشد"
        raise ServiceError(str(message))
    text = "\n".join((item.get("ParsedText") or "").strip() for item in results)
    text = "\n".join(line for line in text.splitlines() if line.strip())
    if not text:
        raise ServiceError("متنی در تصویر تشخیص داده نشد")
    return text
