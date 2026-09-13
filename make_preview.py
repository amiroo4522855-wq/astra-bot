#!/usr/bin/env python3
"""ساخت پیش‌نمایش HTML از پیام‌های ربات (بر اساس رونوشت شبیه‌سازی).

اجرا:
    python simulate.py && python make_preview.py
خروجی:
    preview.html  →  یک صفحه‌ی مستقل (بدون وابستگی خارجی)
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TRANSCRIPT = ROOT / "data" / "transcript.json"
OUTPUT = ROOT / "preview.html"

# پیام‌هایی که در پیش‌نمایش نمایش داده می‌شوند (ترتیب در رونوشت)
WANTED_TRIGGERS = [
    "/start", "menu:music", "menu:ai", "menu:dl", "menu:tools",
    "menu:practical", "menu:fun", "menu:group", "menu:vip", "menu:help",
    "music:search", "music:quality", "music:radio", "practical:weather",
    "tools:font", "fun:games", "vip:buy:3", "admin:panel", "admin:stats",
    "help:guide", "unknown",
]

HEAD_HTML = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>پیش‌نمایش ربات آسترا ✨</title>
</head>
<body style="margin:0;padding:32px 16px;background:#0e1117;color:#e6edf3;
font-family:'Vazirmatn','Segoe UI',Tahoma,sans-serif;">
<div style="max-width:960px;margin:0 auto;">
  <div style="text-align:center;margin-bottom:28px;">
    <div style="font-size:40px;">✨</div>
    <h1 style="margin:8px 0 4px;font-size:26px;">آسترا (Astra)</h1>
    <p style="margin:0;color:#8b949e;font-size:14px;">همه ابزارها در یک ربات · پیش‌نمایش منوها و پیام‌ها</p>
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:18px;justify-content:center;">
"""

BUBBLE = """
    <div style="width:330px;background:#161b22;border:1px solid #30363d;
    border-radius:16px;padding:14px 14px 12px;box-shadow:0 6px 20px rgba(0,0,0,.35);">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
        <div style="width:30px;height:30px;border-radius:50%;background:linear-gradient(135deg,#7c3aed,#2563eb);
        display:flex;align-items:center;justify-content:center;font-size:15px;">✨</div>
        <div>
          <div style="font-size:13px;font-weight:700;">آسترا</div>
          <div style="font-size:11px;color:#8b949e;">@AstraToolsBot</div>
        </div>
      </div>
      <div style="white-space:pre-wrap;font-size:13px;line-height:1.85;margin:0 2px 12px;">{text}</div>
      {keyboard}
    </div>
"""

BUTTON = """<span style="display:inline-block;margin:3px 2px;padding:6px 11px;border-radius:10px;
background:rgba(88,166,255,.10);border:1px solid rgba(88,166,255,.35);color:#79c0ff;
font-size:12px;">{label}</span>"""


def render_keyboard(keyboard: dict | None) -> str:
    if not keyboard:
        return ""
    rows = keyboard.get("rows") or []
    html_rows = []
    for row in rows:
        buttons = "".join(BUTTON.format(label=escape(str(b.get("button_text", ""))))
                          for b in row.get("buttons", []))
        html_rows.append(f'<div style="text-align:center;">{buttons}</div>')
    return f'<div style="border-top:1px dashed #30363d;padding-top:10px;">{"".join(html_rows)}</div>'


def main() -> int:
    if not TRANSCRIPT.exists():
        print("⚠️ ابتدا python simulate.py را اجرا کن.")
        return 1
    data = json.loads(TRANSCRIPT.read_text(encoding="utf-8"))

    by_trigger = {}
    for item in data:
        trigger = item.get("trigger") or ""
        for wanted in WANTED_TRIGGERS:
            if trigger == wanted and wanted not in by_trigger:
                by_trigger[wanted] = item
    ordered = [by_trigger[t] for t in WANTED_TRIGGERS if t in by_trigger]

    bubbles = []
    for item in ordered:
        text = escape(item.get("text", "")).replace("\n─", "\n─")
        bubbles.append(BUBBLE.format(text=text,
                                     keyboard=render_keyboard(item.get("keyboard"))))

    tail = """
  </div>
  <p style="text-align:center;color:#6e7681;font-size:12px;margin-top:28px;">
    این پیش‌نمایش به‌صورت خودکار از خروجی <code>simulate.py</code> ساخته شده است.
  </p>
</div>
</body>
</html>
"""
    OUTPUT.write_text(HEAD_HTML + "".join(bubbles) + tail, encoding="utf-8")
    print(f"✅ پیش‌نمایش ساخته شد: {OUTPUT} ({len(ordered)} پیام)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
