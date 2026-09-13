"""فونت‌ساز آسترا — ۱۶ سبک مختلف برای متن فارسی و انگلیسی.

سبک‌هایی که با ‎✅‎ مشخص شده‌اند روی حروف فارسی هم کار می‌کنند.
"""
from __future__ import annotations

# --------------------------------------------------------------------------- #
# جدول‌های تبدیل حروف انگلیسی
# --------------------------------------------------------------------------- #
def _range_map(start: int, source: str, target_offset: bool = True) -> dict[str, str]:
    return {char: chr(start + index) for index, char in enumerate(source)}


LATIN_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LATIN_LOWER = "abcdefghijklmnopqrstuvwxyz"
DIGITS = "0123456789"

ALPHABETS = {
    "bold": (_range_map(0x1D400, LATIN_UPPER),
             _range_map(0x1D41A, LATIN_LOWER),
             _range_map(0x1D7CE, DIGITS)),
    "italic": (_range_map(0x1D434, LATIN_UPPER),
               _range_map(0x1D44E, LATIN_LOWER),
               {}),
    "bold_italic": (_range_map(0x1D468, LATIN_UPPER),
                    _range_map(0x1D482, LATIN_LOWER),
                    {}),
    "script": (_range_map(0x1D49C, LATIN_UPPER),
               _range_map(0x1D4B6, LATIN_LOWER),
               {}),
    "script_bold": (_range_map(0x1D4D0, LATIN_UPPER),
                    _range_map(0x1D4EA, LATIN_LOWER),
                    {}),
    "fraktur": (_range_map(0x1D504, LATIN_UPPER),
                _range_map(0x1D51E, LATIN_LOWER),
                {}),
    "double": (_range_map(0x1D538, LATIN_UPPER),
               _range_map(0x1D552, LATIN_LOWER),
               _range_map(0x1D7D8, DIGITS)),
    "mono": (_range_map(0x1D670, LATIN_UPPER),
             _range_map(0x1D68A, LATIN_LOWER),
             _range_map(0x1D7F6, DIGITS)),
    "sans_bold": (_range_map(0x1D5D4, LATIN_UPPER),
                  _range_map(0x1D5EE, LATIN_LOWER),
                  _range_map(0x1D7EC, DIGITS)),
    "bubble": ({c: chr(0x24B6 + i) for i, c in enumerate(LATIN_UPPER)},
               {c: chr(0x24D0 + i) for i, c in enumerate(LATIN_LOWER)},
               {**{d: chr(0x2460 + i) for i, d in enumerate(DIGITS[1:])}, "0": "⓪"}),
    "square": ({c: chr(0x1F130 + i) for i, c in enumerate(LATIN_UPPER)},
               {c: chr(0x1F150 + i) for i, c in enumerate(LATIN_LOWER)},
               {d: d + "\ufe0f\u20e3" for d in DIGITS}),
    "tiny": (dict(zip(LATIN_UPPER, "ᴬᴮᶜᴰᴱᶠᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᵠᴿˢᵀᵁⱽᵂˣʸᶻ")),
             dict(zip(LATIN_LOWER, "ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖᑫʳˢᵗᵘᵛʷˣʸᶻ")),
             dict(zip(DIGITS, "⁰¹²³⁴⁵⁶⁷⁸⁹"))),
}

# نویسه‌های ترکیبی که روی فارسی هم جواب می‌دهند
COMBINING_MARK = "\u0323"      # نقطه زیر
LOW_LINE = "\u0332"            # زیرخط
STRIKE = "\u0336"              # خط‌خورده
OVER_LINE = "\u0305"           # بالاخط
TILDE_OVER = "\u0334"          # ~ بالا

STYLES: dict[str, tuple[str, str]] = {
    "bold": ("پررنگ", "🔤"),
    "italic": ("کج", "✒️"),
    "bold_italic": ("پررنگ‌کج", "🖋"),
    "script": ("دست‌نویس", "✍️"),
    "script_bold": ("دست‌نویس پررنگ", "🖊"),
    "fraktur": ("کلاسیک", "📜"),
    "double": ("دابل‌استروک", "🧮"),
    "mono": ("ماشین‌تحریر", "⌨️"),
    "sans_bold": ("ساده‌پررنگ", "🅰️"),
    "bubble": ("حبابی", "🫧"),
    "square": ("مربعی", "🟦"),
    "tiny": ("ریز", "🔬"),
    "underline": ("زیرخط‌دار ✅", "➖"),
    "strike": ("خط‌خورده ✅", "❌"),
    "overline": ("بالاخط‌دار ✅", "➰"),
    "dotted": ("نقطه‌دار ✅", "⁘"),
    "spaced": ("درشت و فاصله‌دار ✅", "🌬"),
    "glitter": ("جواهری ✅", "✨"),
    "boxed": ("کادری ✅", "🎁"),
}

# ترتیب نمایش در منو
ORDER = [
    "bold", "italic", "bold_italic", "script", "script_bold", "fraktur",
    "double", "mono", "sans_bold", "bubble", "square", "tiny",
    "underline", "strike", "overline", "dotted", "spaced", "glitter", "boxed",
]


def _alphabet_apply(text: str, style: str) -> str:
    upper_map, lower_map, digit_map = ALPHABETS[style]
    out = []
    for char in text:
        if char in upper_map:
            out.append(upper_map[char])
        elif char in lower_map:
            out.append(lower_map[char])
        elif char in digit_map:
            out.append(digit_map[char])
        else:
            out.append(char)
    return "".join(out)


def apply(text: str, style: str) -> str:
    """تبدیل متن به سبک مورد نظر."""
    text = (text or "").strip()
    if not text:
        return ""
    if style in ALPHABETS:
        return _alphabet_apply(text, style)
    if style == "underline":
        return "".join(ch + LOW_LINE for ch in text)
    if style == "strike":
        return "".join(ch + STRIKE for ch in text)
    if style == "overline":
        return "".join(ch + OVER_LINE for ch in text)
    if style == "dotted":
        return "".join(ch + COMBINING_MARK for ch in text)
    if style == "spaced":
        return " ".join(text)
    if style == "glitter":
        return "✨".join(text) + "✨"
    if style == "boxed":
        return "".join(f"[{ch}]" for ch in text)
    return text


def apply_all(text: str, limit: int = 6) -> list[tuple[str, str]]:
    """چند سبک آماده برای نمایش سریع."""
    return [(STYLES[name][0], apply(text, name)) for name in ORDER[:limit]]


def style_keyboard(prefix: str = "font:pick") -> list[tuple[str, str]]:
    return [(f"{STYLES[name][1]} {STYLES[name][0]}", f"{prefix}:{name}") for name in ORDER]
