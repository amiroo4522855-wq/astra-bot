"""پیام‌ساز: ساختِ متنِ آماده برای مناسبت‌ها در لحن‌های مختلف."""
from __future__ import annotations

import json
import math
import random
from functools import lru_cache
from pathlib import Path

_CANDIDATES = (
    Path(__file__).resolve().parent.parent.parent / "docs" / "data" / "messages.json",
    Path(__file__).resolve().parent.parent / "data" / "messages.json",
)
DATA = next((p for p in _CANDIDATES if p.exists()), _CANDIDATES[0])

DEFAULT_TONE = "ejtemaei"
MAX_LINES = 20


@lru_cache(maxsize=1)
def load() -> dict:
    try:
        return json.loads(DATA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def categories() -> list[dict]:
    return load().get("categories", [])


def tones() -> list[dict]:
    return load().get("tones", [])


def cat_name(cid: str) -> str:
    for c in categories():
        if c["id"] == cid:
            return f"{c.get('icon', '')} {c['name']}".strip()
    return cid


def tone_name(tid: str) -> str:
    for t in tones():
        if t["id"] == tid:
            return f"{t.get('icon', '')} {t['name']}".strip()
    return tid


def find_cat(word: str) -> str | None:
    """یافتنِ دسته بر اساسِ واژه‌ی فارسیِ کاربر."""
    key = (word or "").strip()
    if not key:
        return None
    for c in categories():
        if c["name"] == key or c["id"] == key:
            return c["id"]
    for c in categories():
        if c["name"] in key:
            return c["id"]
    return None


def _pick(seq, seed: float):
    if not seq:
        return ""
    idx = int(abs(math.sin(seed * 12.9898) * 43758.5453)) % len(seq)
    return seq[idx]


def _shuffled(seq, seed: float) -> list:
    out = list(seq)
    for i in range(len(out) - 1, 0, -1):
        j = int(abs(math.sin((seed + i) * 78.233) * 43758.5453)) % (i + 1)
        out[i], out[j] = out[j], out[i]
    return out


def _fill(text: str, to: str, from_: str) -> str:
    to = (to or "").strip() or "عزیزم"
    out = text.replace("{to}", to).replace("{from}", (from_ or "").strip())
    return out


def build(cat: str = "tabrik", tone: str = DEFAULT_TONE, lines: int = 8,
          to: str = "", from_: str = "", poem: bool = False,
          seed: float | None = None) -> list[str]:
    """ساختِ پیام؛ خروجی فهرستی از خط‌ها است."""
    data = load()
    block = (data.get("messages") or {}).get(cat)
    if not block:
        block = (data.get("messages") or {}).get("tabrik")
    if not block:
        return []
    if seed is None:
        seed = random.random() * 1000
    lines = max(3, min(MAX_LINES, int(lines or 8)))

    signed = bool((from_ or "").strip())
    room = lines - 2 if signed else lines - 1        # بدون امضا، یک خط بیشتر برای متن
    pool = _shuffled(block.get("lines", []), seed + 3)
    body = pool[: min(len(pool), max(1, room))]
    need = max(0, min(MAX_LINES - 2, room) - len(body))
    if poem and need == 0:
        need = 2                                     # دست‌کم یک بیت افزوده شود
    if (poem or need > 0) and data.get("poems"):
        for p in _shuffled(data["poems"], seed + 9):
            if need <= 0:
                break
            body.append(f"«{p['a']}»")
            need -= 1
            if need > 0:
                body.append(f"«{p['b']}» — {p['poet']}")
                need -= 1

    openers = block.get("openers", {}) or {}
    closers = block.get("closers", {}) or {}
    opener = _pick(openers.get(tone) or openers.get(DEFAULT_TONE) or [""], seed)
    closer = _pick(closers.get(tone) or closers.get(DEFAULT_TONE) or [""], seed + 2)

    out = [_fill(opener, to, from_)] + body
    if (from_ or "").strip() and closer:
        out.append(_fill(closer, to, from_))
    return [line for line in out if line.strip()]


def render(cat: str = "tabrik", tone: str = DEFAULT_TONE, lines: int = 8,
           to: str = "", from_: str = "", poem: bool = False,
           seed: float | None = None) -> str:
    parts = build(cat, tone, lines, to, from_, poem, seed)
    if not parts:
        return ""
    head = f"✍️ {cat_name(cat)} · {tone_name(tone)}"
    return "\n".join([head, "───────────────", *parts])
