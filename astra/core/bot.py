"""هسته‌ی اجرایی ربات: دریافت آپدیت‌ها و توزیع آن‌ها بین handlerها."""
from __future__ import annotations

import signal
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .. import config, handlers  # noqa: F401  (import برای ثبت مسیرها)
from .client import RubikaClient, RubikaError
from .factory import create_client, resolve_platform
from .context import Context, parse_update
from .db import DB, Database
from .router import handle


class AstraBot:
    """مدیر اصلی ربات: polling یا webhook، با پردازش موازی و امن."""

    def __init__(self, token: str | None = None, db: Database | None = None,
                 client: RubikaClient | None = None,
                 platform: str | None = None) -> None:
        self.db = db or DB
        self.platform = resolve_platform(platform, token) if client is None else \
            getattr(client, "platform", "rubika")
        self.client = client or create_client(self.platform, token)
        self.offset: str = self.db.get_setting("offset_id", "")
        self.running = True
        self.processed = 0
        self._pool = ThreadPoolExecutor(max_workers=config.WORKERS,
                                        thread_name_prefix="astra")

    # ------------------------------------------------------------------ #
    # پردازش
    # ------------------------------------------------------------------ #
    def process(self, raw: dict) -> None:
        """پردازش یک آپدیت خام (از polling یا webhook)."""
        try:
            update = parse_update(raw)
            if not update or not update.chat_id:
                return
            # در تلگرام باید به کلیک پاسخ داده شود تا حالتِ بارگذاری قطع شود
            if update.callback_query_id and hasattr(self.client, "answer_callback_query"):
                try:
                    self.client.answer_callback_query(update.callback_query_id)
                except Exception:
                    pass
            ctx = Context(self.client, self.db, update)
            handle(ctx)
            self.processed += 1
        except Exception:                                   # هیچ آپدیتی نباید ربات را ببندد
            self.db.log("ERROR", "bot.process", traceback.format_exc()[-800:])

    def _safe_process(self, raw: dict) -> None:
        try:
            self._pool.submit(self.process, raw)
        except RuntimeError:                                # اگر pool بسته شده بود
            self.process(raw)

    # ------------------------------------------------------------------ #
    # Polling
    # ------------------------------------------------------------------ #
    def _next_offset(self, raw: dict) -> str:
        """استخراج شناسه‌ی بعدی برای ادامه‌ی دریافت آپدیت‌ها."""
        if self.platform == "telegram" and raw.get("update_id") is not None:
            return str(int(raw["update_id"]) + 1)      # آفست تلگرام = آخرین + ۱
        for key in ("update_id", "start_id", "offset_id", "id"):
            value = raw.get(key)
            if value:
                return str(value)
        update = (raw.get("update") or {}) if isinstance(raw, dict) else {}
        message = update.get("new_message") or {}
        return str(message.get("message_id") or update.get("message_id") or "")

    def poll_once(self) -> int:
        """یک دور دریافت و پردازش آپدیت‌ها."""
        try:
            updates = self.client.get_updates(offset_id=self.offset or None)
        except RubikaError as exc:
            self.db.log("ERROR", "getUpdates", str(exc))
            time.sleep(config.POLL_INTERVAL * 2)
            return 0
        if not updates:
            return 0
        for raw in updates:
            self._safe_process(raw)
            next_offset = self._next_offset(raw)
            if next_offset:
                self.offset = next_offset
        self.db.set_setting("offset_id", str(self.offset))
        return len(updates)

    def run(self) -> None:
        """حلقه‌ی اصلی (Long Polling)."""
        self._install_signals()
        self.bootstrap()
        failures = 0
        while self.running:
            try:
                count = self.poll_once()
                failures = 0
                time.sleep(0.3 if count else config.POLL_INTERVAL)
            except KeyboardInterrupt:
                break
            except Exception as exc:                        # خطای غیرمنتظره در حلقه
                failures += 1
                self.db.log("ERROR", "bot.run", f"{type(exc).__name__}: {exc}")
                time.sleep(min(30, config.POLL_INTERVAL * (2 ** min(failures, 5))))
        self.shutdown()

    # ------------------------------------------------------------------ #
    # راه‌اندازی و پایان
    # ------------------------------------------------------------------ #
    def bootstrap(self) -> None:
        """بررسی اتصال و ثبت دستورات (در صورت امکان)."""
        label = "تلگرام 🤖" if self.platform == "telegram" else "روبیکا ✨"
        try:
            info = self.client.get_me()
            bot = info.get("bot") or info
            name = bot.get("name") or config.BOT_NAME
            username = bot.get("username") or config.BOT_USERNAME
            print(f"✨ {name} (@{username}) روی {label} آماده است — Ctrl+C برای توقف")
        except RubikaError as exc:
            print(f"⚠️ خطا در اتصال به روبیکا: {exc}\n"
                  "   توکن را در فایل .env بررسی کن.")
            return
        try:
            self.client.set_commands([
                {"command": "start", "description": "شروع و منوی اصلی"},
                {"command": "help", "description": "راهنما"},
                {"command": "vip", "description": "عضویت ویژه"},
                {"command": "admin", "description": "پنل مدیریت"},
            ])
        except RubikaError:
            pass

    def set_webhook(self, url: str) -> str:
        """تنظیم آدرس دریافت آپدیت‌ها (Webhook)."""
        result = self.client.update_bot_endpoint(url)
        self.db.set_setting("webhook_url", url)
        return str(result)

    def _install_signals(self) -> None:
        def handler(signum, _frame):                        # توقفِ تمیز
            self.running = False
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                pass

    def shutdown(self) -> None:
        self.running = False
        self._pool.shutdown(wait=True)
        print("\n👋 آسترا خاموش شد.")
