"""دستورِ غذاهای ایرانی — ۱۰۰ غذای اصیل با مواد و مراحلِ واقعی."""
from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path

# داده در docs/data است (همان منبعی که مینی‌اپ منتشر می‌کند)
_CANDIDATES = (
    Path(__file__).resolve().parent.parent.parent / "docs" / "data" / "recipes.json",
    Path(__file__).resolve().parent.parent / "data" / "recipes.json",
)
DATA = next((p for p in _CANDIDATES if p.exists()), _CANDIDATES[0])


@lru_cache(maxsize=1)
def load() -> dict:
    """بارگذاریِ یک‌باره‌ی فایلِ دستورها."""
    try:
        return json.loads(DATA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"items": [], "categories": []}


def categories() -> list[dict]:
    return load().get("categories", [])


def all_items() -> list[dict]:
    return load().get("items", [])


def _norm(text: str) -> str:
    repl = {"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ي": "ی", "ك": "ک",
            "ؤ": "و", "‌": "", "\u200c": "", "ً": "", "ٌ": "", "ٍ": ""}
    for a, b in repl.items():
        text = text.replace(a, b)
    return text.strip().lower()


def find(query: str) -> dict | None:
    """یافتنِ غذا بر اساسِ نام (تطبیقِ دقیق، سپس جزئی)."""
    items = all_items()
    if not items:
        return None
    key = _norm(query or "")
    if not key:
        return None
    for item in items:                                  # تطبیقِ کامل
        if _norm(item["name"]) == key:
            return item
    for item in items:                                  # تطبیقِ جزئی
        if _norm(item["name"]) in key or key in _norm(item["name"]):
            return item
    for item in items:                                  # واژه‌های کلیدی
        words = [w for w in key.replace("؟", " ").split() if len(w) > 2]
        if any(w in _norm(item["name"]) for w in words):
            return item
    return None


def by_category(cat: str) -> list[dict]:
    return [i for i in all_items() if i.get("cat") == cat]


def random_recipe(cat: str = "") -> dict | None:
    pool = by_category(cat) if cat else all_items()
    return random.choice(pool) if pool else None


def short_list(cat: str = "", limit: int = 18) -> list[str]:
    """فهرستِ کوتاهِ نام‌ها برای نمایش در منو."""
    pool = by_category(cat) if cat else all_items()
    return [i["name"] for i in pool[:limit]]


def render(item: dict, full: bool = True) -> str:
    """نمایشِ تمیزِ یک دستورِ غذا."""
    cat_name = item.get("cat", "")
    for cat in categories():
        if cat["id"] == cat_name:
            cat_name = cat["name"]
            break
    lines = [
        f"🍲 {item['name']}" + (f" · {cat_name}" if cat_name else ""),
        f"📍 {item['origin']} · ⏱ {item['time']} · 📊 {item['level']} · 👥 {item['serves']} نفر",
        "───────────────",
        "🥕 مواد لازم:",
    ]
    lines += [f"▫️ {i}" for i in item["ingredients"]]
    lines += ["───────────────", "👩‍🍳 طرز تهیه:"]
    lines += [f"{idx}. {step}" for idx, step in enumerate(item["steps"], 1)]
    lines += ["───────────────", f"💡 {item['tip']}"]
    if not full and len(lines) > 16:                    # نسخه‌ی کوتاه برای گروه
        lines = lines[:14] + ["…", "───────────────", "ادامه‌اش را در مینی‌اپ ببین ✨"]
    return "\n".join(lines)


def suggestion_text() -> str:
    """یک پیشنهادِ شانسی برای «امروز چی بپزم؟»"""
    item = random_recipe()
    if not item:
        return ""
    return (f"🎲 پیشنهاد امروز: «{item['name']}»\n"
            f"───────────────\n"
            f"📍 {item['origin']} · ⏱ {item['time']} · 📊 {item['level']}\n"
            f"🥕 مواد اصلی: {'، '.join(item['ingredients'][:4])}\n"
            f"───────────────\n"
            f"برای دستورِ کامل بنویسید: «دستور پخت {item['name']}»")
