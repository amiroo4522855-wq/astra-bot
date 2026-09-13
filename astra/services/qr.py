"""ساخت QR Code (کتابخانه‌ی محلی یا سرویس آنلاین)."""
from __future__ import annotations

import io

from .. import config
from .http import ServiceError, get_bytes

_QR_LIB_ERROR = "کتابخانه‌ی qrcode نصب نیست"


def make_png_bytes(data: str, box_size: int = 10, border: int = 4) -> bytes:
    """ساخت تصویر PNG از متن/لینک."""
    try:
        import qrcode  # type: ignore
    except ImportError:
        # تلاش آنلاین: سرویس عمومی QR
        url = (f"{config.QR_API}?size={box_size * 30}x{box_size * 30}"
               f"&data={data}")
        try:
            return get_bytes(url, timeout=20)
        except ServiceError as exc:
            raise ServiceError(f"{_QR_LIB_ERROR} و سرویس آنلاین هم در دسترس نیست: {exc}") from exc

    img = qrcode.QRCode(version=None, box_size=box_size, border=border)
    img.add_data(data)
    img.make(fit=True)
    image = img.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
