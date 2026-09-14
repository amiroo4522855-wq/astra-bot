#!/usr/bin/env python3
"""نقطه‌ی ورود ربات آسترا.

نمونه استفاده:
    python main.py                 # اجرا با Long Polling
    python main.py --check         # فقط بررسی توکن
    python main.py --once          # یک دور دریافت آپدیت
    python main.py --webhook URL   # تنظیم وب‌هوک
    python main.py --platform telegram   # اجرا روی تلگرام
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
from astra.core.factory import (active_token, create_client,  # noqa: E402
                                resolve_platform)

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


def check_token(platform: str | None = None) -> int:
    resolved = resolve_platform(platform)
    token = active_token(resolved)
    if not token:
        key = "TELEGRAM_BOT_TOKEN" if resolved == "telegram" else "BOT_TOKEN"
        print(f"❌ توکن تنظیم نشده است ({key}).\n"
              "   فایل .env را در کنار main.py بساز و مقدار را وارد کن.")
        return 1
    client = create_client(resolved)
    label = "تلگرام" if resolved == "telegram" else "روبیکا"
    try:
        info = client.get_me()
        bot = info.get("bot") or info
        print(f"✅ اتصال به {label} برقرار است: "
              f"{bot.get('name', '؟')} (@{bot.get('username', '؟')})")
        return 0
    except RubikaError as exc:
        print(f"❌ خطا در اتصال به {label}: {exc}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="ربات چندکاره‌ی آسترا برای روبیکا")
    parser.add_argument("--once", action="store_true", help="فقط یک دور آپدیت بگیر و خارج شو")
    parser.add_argument("--check", action="store_true", help="بررسی توکن و خروج")
    parser.add_argument("--webhook", metavar="URL", help="تنظیم وب‌هوک روی آدرس داده‌شده")
    parser.add_argument("--platform", choices=["auto", "rubika", "telegram"],
                        default="auto", help="پلتفرم مقصد (پیش‌فرض: تشخیص خودکار از توکن)")
    parser.add_argument("-v", "--verbose", action="store_true", help="لاگ کامل")
    args = parser.parse_args()

    setup_logging(args.verbose)

    if args.check:
        return check_token(args.platform)

    platform = resolve_platform(args.platform)
    if not active_token(platform):
        key = "TELEGRAM_BOT_TOKEN" if platform == "telegram" else "BOT_TOKEN"
        print(f"❌ {key} تنظیم نشده است. فایل .env را کامل کن (نمونه: .env.example)")
        return 1

    bot = AstraBot(platform=platform)
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
