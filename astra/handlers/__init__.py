"""ثبت تمام handlerها.

فقط با import شدن این ماژول، همه‌ی مسیرها (route/command/state/text)
در ربات ثبت می‌شوند. ترتیب import مهم نیست چون مسیریاب بر اساس
شناسه‌ی دکمه عمل می‌کند، اما برای خوانایی مرتب نگه داشته شده است.
"""
from __future__ import annotations

from . import start            # شروع، منوی اصلی، ناوبری
from . import practical        # آب‌وهوا، ارز، طلا، ارز دیجیتال
from . import tools            # ابزارها
from . import music            # موزیک
from . import ai               # هوش مصنوعی
from . import downloader       # دانلودر
from . import fun              # سرگرمی
from . import food             # آشپزی ایرانی 🍲
from . import games            # بازی دوز ❌⭕️
from . import anon             # چت ناشناس 🕵️
from . import group            # مدیریت گروه
from . import vip              # عضویت ویژه
from . import admin            # پنل ادمین
from . import help as help_mod # راهنما و پشتیبانی
from . import miniapp         # مینی‌اپ (Telegram Web App)
from . import fallback         # زبان طبیعی و پیام ناشناخته

__all__ = [
    "start", "practical", "tools", "music", "ai", "downloader",
    "fun", "group", "vip", "admin", "help_mod", "miniapp", "fallback",
]
