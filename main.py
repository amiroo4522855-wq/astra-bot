#!/usr/bin/env python3
"""نقطه‌ی ورود ربات آسترا.

نمونه استفاده:
    python main.py                 # اجرا با Long Polling
    python main.py --check         # فقط بررسی توکن
    python main.py --once          # یک دور دریافت آپدیت
    python main.py --webhook URL   # تنظیم وب‌هوک
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from astra import config                                    # noqa: E402
from astra.core.bot import AstraBot                         # noqa: E402
from astra.core.client import RubikaError                   # noqa: E402

LOG_FILE = config.DATA_DIR / "astra.log"


def setup_logging(verbose: bool = False) -> None:
    handlers = [logging.StreamHandler(sys.stdout)]
    try:
        handlers.append(logging.FileHandler(LOG_FILE, encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )


def check_token() -> int:
    from astra.core.client import RubikaClient
    if not config.BOT_TOKEN:
        print("❌ توکن ربات تنظیم نشده است.\n"
              "   فایل .env را در کنار main.py بساز و BOT_TOKEN را وارد کن.")
        return 1
    client = RubikaClient()
    try:
        info = client.get_me()
        bot = info.get("bot") or info
        print(f"✅ اتصال برقرار است: {bot.get('name', '؟')} (@{bot.get('username', '؟')})")
        return 0
    except RubikaError as exc:
        print(f"❌ خطا: {exc}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="ربات چندکاره‌ی آسترا برای روبیکا")
    parser.add_argument("--once", action="store_true", help="فقط یک دور آپدیت بگیر و خارج شو")
    parser.add_argument("--check", action="store_true", help="بررسی توکن و خروج")
    parser.add_argument("--webhook", metavar="URL", help="تنظیم وب‌هوک روی آدرس داده‌شده")
    parser.add_argument("-v", "--verbose", action="store_true", help="لاگ کامل")
    args = parser.parse_args()

    setup_logging(args.verbose)

    if args.check:
        return check_token()

    if not config.BOT_TOKEN:
        print("❌ BOT_TOKEN تنظیم نشده است. فایل .env را کامل کن (نمونه: .env.example)")
        return 1

    bot = AstraBot()
    if args.webhook:
        print(f"🔗 تنظیم وب‌هوک روی {args.webhook}: {bot.set_webhook(args.webhook)}")
        return 0
    if args.once:
        print(f"📥 تعداد آپدیت‌های پردازش‌شده: {bot.poll_once()}")
        return 0

    bot.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
