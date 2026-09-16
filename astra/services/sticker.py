"""ساختِ استیکر واقعی (WebP) با Pillow — متنِ فارسی و عکس."""
from __future__ import annotations

import io
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent.parent
FONT_DIR = ROOT / "assets" / "fonts"
SIZE = 512

# الگوهای رنگی (بالا → پایین)
STYLES = {
    "violet":   ("#7c5cff", "#22d3ee"),
    "sunset":   ("#fb923c", "#f472b6"),
    "mint":     ("#34d399", "#22d3ee"),
    "night":    ("#1e1b4b", "#4c1d95"),
    "rose":     ("#f43f5e", "#fb923c"),
    "sky":      ("#38bdf8", "#818cf8"),
    "gold":     ("#f59e0b", "#facc15"),
    "dark":     ("#0f172a", "#1e293b"),
}


def _fonts() -> tuple[str, str]:
    bold = FONT_DIR / "Vazirmatn-Bold.ttf"
    regular = FONT_DIR / "Vazirmatn-Regular.ttf"
    return str(bold if bold.exists() else regular), str(regular if regular.exists() else bold)


def shape(text: str) -> str:
    """اتصال و جهت‌دهیِ درستِ حروفِ فارسی/عربی."""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(text or ""))
    except Exception:                                   # در نبودِ کتابخانه، متن همان‌طور می‌ماند
        return text or ""


@lru_cache(maxsize=64)
def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _fit_font(draw: ImageDraw.ImageDraw, text: str, font_path: str, box: int,
              max_size: int = 96, min_size: int = 22) -> ImageFont.FreeTypeFont:
    size = max_size
    while size > min_size:
        font = _font(font_path, size)
        w = draw.textbbox((0, 0), text, font=font)[2]
        if w <= box:
            return font
        size -= 2
    return _font(font_path, min_size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, box: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines, current = [], words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textbbox((0, 0), trial, font=font)[2] <= box:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _gradient(top: str, bottom: str, size: int = SIZE) -> Image.Image:
    """تولیدِ پس‌زمینه‌ی گرادیانی."""
    img = Image.new("RGB", (size, size), top)
    draw = ImageDraw.Draw(img)
    r1, g1, b1 = _rgb(top)
    r2, g2, b2 = _rgb(bottom)
    for y in range(size):
        t = y / max(1, size - 1)
        draw.line([(0, y), (size, y)],
                  fill=(int(r1 + (r2 - r1) * t),
                        int(g1 + (g2 - g1) * t),
                        int(b1 + (b2 - b1) * t)))
    return img


def _rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _rounded(img: Image.Image, radius: int = 64) -> Image.Image:
    """گوشه‌های گرد با شفافیت."""
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.size[0] - 1, img.size[1] - 1],
                                           radius=radius, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def text_sticker(text: str, style: str = "violet", emoji: str = "") -> bytes:
    """ساختِ استیکرِ متنی (خروجی WebP)."""
    text = (text or "").strip()
    if not text:
        text = "آسترا ✨"
    top, bottom = STYLES.get(style, STYLES["violet"])
    img = _gradient(top, bottom)
    draw = ImageDraw.Draw(img)

    # هاله‌ی روشن در مرکز
    glow = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    ImageDraw.Draw(glow).ellipse([SIZE * 0.1, SIZE * 0.12, SIZE * 0.9, SIZE * 0.72],
                                 fill=_rgb(bottom))
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    img = Image.blend(img, glow, 0.35)
    draw = ImageDraw.Draw(img)

    bold_path, regular_path = _fonts()
    shaped = shape(text)
    box = int(SIZE * 0.82)
    font = _fit_font(draw, shaped, bold_path, box)
    lines = _wrap(draw, shaped, font, box)
    if len(lines) > 6:
        lines = lines[:6]
    line_h = font.size + 18
    total = line_h * len(lines)
    y = (SIZE - total) // 2 - 10

    for line in lines:
        w = draw.textbbox((0, 0), line, font=font)[2]
        x = (SIZE - w) // 2
        draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 90))
        draw.text((x, y), line, font=font, fill="white")
        y += line_h

    # امضایِ کوچک
    try:
        small = _font(regular_path, 22)
        sign = shape("آسترا ✨")
        sw = draw.textbbox((0, 0), sign, font=small)[2]
        draw.text(((SIZE - sw) // 2, SIZE - 54), sign, font=small, fill=(255, 255, 255, 190))
    except Exception:
        pass

    out = _rounded(img, 72)
    buf = io.BytesIO()
    out.save(buf, "WEBP", quality=92)
    return buf.getvalue()


def photo_sticker(data: bytes) -> bytes:
    """تبدیلِ عکس به استیکرِ چهارگوشِ ۵۱۲ در ۵۱۲."""
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    img.thumbnail((SIZE, SIZE), Image.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.paste(img, ((SIZE - img.width) // 2, (SIZE - img.height) // 2), img)
    buf = io.BytesIO()
    canvas.save(buf, "WEBP", quality=92)
    return buf.getvalue()


def styles_list() -> list[tuple[str, str, str]]:
    """فهرستِ سبک‌ها برای نمایش در منو."""
    names = {"violet": "بنفش", "sunset": "غروب", "mint": "نعنایی", "night": "شب",
             "rose": "صورتی", "sky": "آسمانی", "gold": "طلایی", "dark": "تیره"}
    return [(key, names.get(key, key), f"{top} → {bottom}")
            for key, (top, bottom) in STYLES.items()]
