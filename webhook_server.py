#!/usr/bin/env python3
"""سرور دریافت وب‌هوک برای ربات آسترا (بدون وابستگی اضافی).

روبیکا فقط به آدرس‌های HTTPS متصل می‌شود، بنابراین این سرور را معمولاً
پشت Nginx/Cloudflare (با SSL) اجرا می‌کنیم.

اجرا:
    python webhook_server.py --port 8443 --path /astra-webhook
سپس در ربات:
    python main.py --webhook https://example.com/astra-webhook
"""
from __future__ import annotations

import argparse
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from astra import config
from astra.core.bot import AstraBot

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
BOT = AstraBot()


class WebhookHandler(BaseHTTPRequestHandler):
    """دریافت POST از روبیکا و تحویل به هسته‌ی ربات."""

    path_expected = "/webhook"

    def _reply(self, code: int, body: str = "ok") -> None:
        payload = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # ------------------------------------------------------------------ #
    def do_POST(self) -> None:                              # noqa: N802
        if self.path.rstrip("/") != self.path_expected.rstrip("/"):
            self._reply(404, "not found")
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self._reply(400, "bad json")
            return
        # پاسخ سریع به روبیکا، پردازش در ادامه انجام می‌شود
        self._reply(200, "ok")
        try:
            BOT.process(data)
        except Exception as exc:                            # ربات نباید به‌خاطر یک پیام ببندد
            BOT.db.log("ERROR", "webhook", f"{type(exc).__name__}: {exc}")
            logging.exception("خطا در پردازش وب‌هوک")

    def do_GET(self) -> None:                               # noqa: N802
        self._reply(200, "آسترا آماده است ✨")

    def log_message(self, fmt: str, *args) -> None:         # لاگ خلوت‌تر
        logging.info("%s - %s", self.address_string(), fmt % args)


def main() -> int:
    parser = argparse.ArgumentParser(description="وب‌هوک ربات آسترا")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(config.env("WEBHOOK_PORT", "8443")),
                        help="پورت سرور (پیش‌فرض ۸۴۴۳)")
    parser.add_argument("--path", default="/webhook", help="مسیر دریافت آپدیت‌ها")
    args = parser.parse_args()

    if not config.BOT_TOKEN:
        print("❌ BOT_TOKEN تنظیم نشده است (فایل .env را کامل کن).")
        return 1

    WebhookHandler.path_expected = args.path
    server = ThreadingHTTPServer((args.host, args.port), WebhookHandler)
    print(f"🌐 وب‌هوک آسترا روی http://{args.host}:{args.port}{args.path} گوش می‌دهد")
    print("   یادت باشد روبیکا فقط HTTPS قبول می‌کند → از Nginx/Cloudflare استفاده کن.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 سرور متوقف شد.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
