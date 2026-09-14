"""انتشار قیمت‌های کانال برای مینی‌اپ.

ربات (که روی GitHub Actions اجرا می‌شود) قیمت‌ها را از کانال می‌خواند،
در ``docs/data/prices.json`` می‌نویسد و اگر تغییر کرده باشد در مخزن
منتشر می‌کند؛ GitHub Pages هم همان را به مینی‌اپ می‌دهد.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

from .. import config
from . import currency

PRICES_FILE = Path("docs") / "data" / "prices.json"


def payload() -> dict | None:
    """داده‌ی آماده برای مینی‌اپ."""
    rows = currency.fetch_channel_web()
    if not rows:
        return None
    items = []
    for label, formatted, value in rows:
        unit = "تومان"
        if formatted.endswith("دلار"):
            unit = "دلار"
        items.append({"label": label, "value": formatted, "unit": unit, "raw": value})
    return {
        "channel": (config.PRICE_CHANNEL or "").lstrip("@"),
        "stamp": currency.channel_stamp(),
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "rows": items,
    }


def write_file() -> bool:
    """نوشتن فایل در صورت وجود پوشه‌ی docs (محیط انتشار)."""
    if not PRICES_FILE.parent.exists():
        return False
    data = payload()
    if not data:
        return False
    try:
        current = json.loads(PRICES_FILE.read_text(encoding="utf-8"))
    except Exception:
        current = {}
    signature = [(item["label"], item["value"]) for item in data["rows"]]
    if signature == [(item["label"], item["value"]) for item in current.get("rows", [])]:
        return False
    PRICES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return True


def _git(*args: str) -> bool:
    try:
        result = subprocess.run(["git", *args], capture_output=True, text=True, timeout=90)
        return result.returncode == 0
    except Exception:
        return False


def publish() -> bool:
    """نوشتن + کامیت + انتشار (در صورت امکان)."""
    if not write_file():
        return False
    if not _git("rev-parse", "--is-inside-work-tree"):
        return True                       # فایل نوشته شد، گیت در دسترس نیست
    _git("add", str(PRICES_FILE))
    committed = _git("-c", "user.name=Astra Bot", "-c", "user.email=bot@users.noreply.github.com",
                     "commit", "-m", "💱 بروزرسانی قیمت‌های کانال [skip ci]")
    if not committed:
        return True
    _git("pull", "--rebase", "origin", "main")
    _git("push", "origin", "main")
    return True
