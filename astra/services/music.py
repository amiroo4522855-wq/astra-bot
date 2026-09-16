"""جستجوی واقعیِ موسیقی — Deezer (سرویس) + iTunes (مرورگر و سرویس)."""
from __future__ import annotations

import re
import time
from functools import lru_cache

from ..core.utils import format_duration
from .http import get_json

DEEZER = "https://api.deezer.com/search"
ITUNES = "https://itunes.apple.com/search"
TIMEOUT = 8

# کشِ کوتاه‌مدت برای کاهشِ فشار روی منابع
_CACHE: dict[tuple, tuple[float, list]] = {}
CACHE_TTL = 300


def _cached(key: tuple) -> list | None:
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1]
    return None


def _store(key: tuple, value: list) -> list:
    _CACHE[key] = (time.time(), value)
    return value


# ترانویسیِ ساده‌ی فارسی → لاتین برای نام‌هایی که منابع فقط لاتین دارند
_FA2EN = {
    "ا": "a", "آ": "a", "ب": "b", "پ": "p", "ت": "t", "ث": "s", "ج": "j",
    "چ": "ch", "ح": "h", "خ": "kh", "د": "d", "ذ": "z", "ر": "r", "ز": "z",
    "ژ": "zh", "س": "s", "ش": "sh", "ص": "s", "ض": "z", "ط": "t", "ظ": "z",
    "ع": "a", "غ": "gh", "ف": "f", "ق": "gh", "ک": "k", "گ": "g", "ل": "l",
    "م": "m", "ن": "n", "و": "v", "ه": "h", "ی": "y", "ئ": "y", "ء": "a",
}


def translit(text: str) -> str:
    """تبدیلِ نویسه‌های فارسی به معادلِ لاتین (کمک برای جستجو)."""
    chars = list(text or "")
    out = []
    for i, ch in enumerate(chars):
        if ch in " 	-_،,":
            out.append(" ")
            continue
        mapped = _FA2EN.get(ch)
        if not mapped:
            continue
        if ch == "ی" and (i == len(chars) - 1 or chars[i + 1:i + 2] in ([" "],)):
            mapped = "i"
        if ch == "و" and i == 0:
            mapped = "v"
        out.append(mapped)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def relevant(item: dict, query: str) -> bool:
    """آیا نتیجه واقعاً به پرسش ربط دارد؟ (برای پیغامِ درستِ «پیدا نشد»)"""
    def has_fa(text: str) -> bool:
        return bool(re.search(r"[\u0600-\u06FF]", text or ""))

    hay = f"{item.get('title', '')} {item.get('artist', '')}".lower()
    # اگر خطِ پرسش و نتیجه متفاوت است (فارسی ↔ لاتین)، به مرتبط‌بودنِ خودِ منبع اعتماد کن
    if has_fa(query) != has_fa(hay):
        return True
    words = [w for w in re.split(r"[\s\-_،,()]+", (query or "").lower()) if len(w) > 2]
    if not words:
        return True
    return any(word in hay for word in words)


def _key(item: dict) -> str:
    """کلید برای حذفِ نتایجِ تکراری."""
    title = _clean(item.get("title", "")).lower()
    artist = _clean(item.get("artist", "")).lower()
    return f"{title}|{artist}"


def deezer_search(query: str, limit: int = 12) -> list[dict]:
    """جستجو در Deezer (فقط سمتِ سرور — پیش‌نمایشِ MP3 دارد)."""
    cached = _cached(("dz", query, limit))
    if cached is not None:
        return cached
    try:
        data = get_json(DEEZER, params={"q": query, "limit": str(limit)}, timeout=TIMEOUT)
    except Exception:
        return []
    out = []
    for row in (data or {}).get("data", []) or []:
        preview = row.get("preview") or ""
        out.append({
            "id": f"dz-{row.get('id')}",
            "title": _clean(row.get("title") or ""),
            "artist": _clean(((row.get("artist") or {}).get("name")) or ""),
            "album": _clean(((row.get("album") or {}).get("title")) or ""),
            "cover": ((row.get("album") or {}).get("cover_xl")
                      or ((row.get("album") or {}).get("cover_big")) or ""),
            "preview": preview,
            "duration": int(row.get("duration") or 0),
            "link": row.get("link") or "",
            "source": "deezer",
            "source_name": "Deezer",
        })
    return _store(("dz", query, limit), out)


def itunes_search(query: str, limit: int = 12) -> list[dict]:
    """جستجو در iTunes — برای مرورگر و سرور، با CORSِ باز."""
    cached = _cached(("it", query, limit))
    if cached is not None:
        return cached
    try:
        data = get_json(ITUNES,
                        params={"term": query, "entity": "song", "limit": str(limit)},
                        timeout=TIMEOUT)
    except Exception:
        return []
    out = []
    for row in (data or {}).get("results", []) or []:
        preview = row.get("previewUrl") or ""
        cover = row.get("artworkUrl100") or ""
        if cover:
            cover = cover.replace("100x100bb.jpg", "400x400bb.jpg")
        out.append({
            "id": f"it-{row.get('trackId')}",
            "title": _clean(row.get("trackName") or ""),
            "artist": _clean(row.get("artistName") or ""),
            "album": _clean(row.get("collectionName") or ""),
            "cover": cover,
            "preview": preview,
            "duration": int((row.get("trackTimeMillis") or 0) // 1000),
            "link": row.get("trackViewUrl") or row.get("collectionViewUrl") or "",
            "source": "itunes",
            "source_name": "Apple Music",
        })
    return _store(("it", query, limit), out)


def _merge(query: str, limit: int, sources: tuple) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    if "deezer" in sources:
        items += deezer_search(query, limit)
    if "itunes" in sources:
        items += itunes_search(query, limit)
    out = []
    for item in items:
        if not item["title"] or not item["preview"]:
            continue
        if not relevant(item, query):
            continue
        key = _key(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def search(query: str, limit: int = 10, sources: tuple = ("deezer", "itunes")) -> list[dict]:
    """جستجوی ترکیبی با حذفِ تکراری‌ها (Deezer اولویت دارد چون MP3 است)."""
    query = _clean(query)
    if len(query) < 2:
        return []
    out = _merge(query, limit, sources)
    if out:
        return out
    # نامِ کامل گاهی در منابع نیست؛ با تک‌واژه‌ها امتحان می‌کنیم (مثل «شجریان»)
    words = [w for w in re.split(r"[\s\-_،,]+", query) if len(w) > 2]
    for word in sorted(words, key=len, reverse=True):
        out = _merge(word, limit, sources)
        if out:
            return out
    # آخرین تلاش: ترانویسی به لاتین (مثل «ابی» → abi)
    latin = translit(query)
    if latin and len(latin) > 2 and latin != query:
        out = _merge(latin, limit, sources)
        if out:
            return out
    return []
    items: list[dict] = []
    seen: set[str] = set()
    if "deezer" in sources:
        items += deezer_search(query, limit)
    if "itunes" in sources:
        items += itunes_search(query, limit)
    out = []
    for item in items:
        if not item["title"] or not item["preview"]:
            continue
        if not relevant(item, query):
            continue
        key = _key(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def best_audio(item: dict) -> str:
    """بهترین لینکِ صوتیِ قابل‌پخش/دانلود."""
    return item.get("preview") or ""


def line(item: dict, index: int = 0) -> str:
    """نمایشِ یک‌خطی برای فهرستِ نتایج."""
    dur = format_duration(item.get("duration") or 0)
    head = f"{index}. " if index else ""
    album = f" · {item['album']}" if item.get("album") else ""
    return f"{head}🎵 {item['title']} — {item['artist']}{album} ({dur})"


def caption(item: dict) -> str:
    """توضیحِ کامل برای ارسال در تلگرام."""
    parts = [f"🎵 {item['title']}", f"👤 {item['artist']}"]
    if item.get("album"):
        parts.append(f"💿 {item['album']}")
    if item.get("duration"):
        parts.append(f"⏱ {format_duration(item['duration'])}")
    parts.append(f"🔗 منبع: {item.get('source_name', '')}")
    return "\n".join(parts)


def youtube_search_link(query: str) -> str:
    from urllib.parse import quote
    return f"https://www.youtube.com/results?search_query={quote(query)}"
