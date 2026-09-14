#!/usr/bin/env python3
"""شبیه‌ساز کامل ربات بدون نیاز به اینترنت یا توکن.

همه‌ی دکمه‌های همه‌ی منوها را به‌صورت خودکار پیمایش می‌کند تا مطمئن شویم:
    • هیچ مسیری بن‌بست نیست (همه‌ی callbackها handler دارند)
    • هیچ handlerی کرش نمی‌کند
    • پیام‌های خالی یا بی‌محتوا ارسال نمی‌شود

اجرا:
    python simulate.py              # حالت آفلاین (سریع و قطعی)
    python simulate.py --online     # با اجازه‌ی فراخوانی سرویس‌های واقعی
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from astra import config                                   # noqa: E402
from astra.core.bot import AstraBot                        # noqa: E402
from astra.core.client import DryRunClient                 # noqa: E402
from astra.core.context import Context, parse_update       # noqa: E402
from astra.core.db import Database                         # noqa: E402
from astra.core.keyboards import main_menu                 # noqa: E402
from astra.core.router import (CALLBACK_PREFIXES,          # noqa: E402
                               CALLBACK_ROUTES, STATE_ROUTES,
                               TEXT_HANDLERS, COMMAND_ROUTES)

TMP_DB = Path(__file__).resolve().parent / "data" / "simulate.db"
USER_ID = "u0SIMULATION0000"
CHAT_ID = USER_ID
GROUP_ID = "g0SIMULATION0000"

# مسیرهایی که در حالت آفلاین نباید فراخوانی شوند (فقط در حالت --online)
SKIP_OFFLINE = ("ai:", "fun:stk", "tools:qr", "tools:short")


# --------------------------------------------------------------------------- #
# ابزار شبیه‌سازی
# --------------------------------------------------------------------------- #
class Simulator:
    def __init__(self, online: bool = False) -> None:
        self.online = online
        # در شبیه‌سازی، کاربرِ آزمایشی ادمین هم هست تا مسیرهای پنل هم پوشش داده شوند
        config.ADMIN_IDS = [USER_ID]
        config.SUPPORT_ID = USER_ID
        self.db = Database(TMP_DB)
        self.db._conn.execute("DELETE FROM states")
        self.db._conn.execute("DELETE FROM logs")
        self.db._conn.commit()
        self.client = DryRunClient(token="SIMULATION")
        self.bot = AstraBot(db=self.db, client=self.client)
        self.visited: set[str] = set()
        self.dead_ends: list[str] = []
        self.transcript: list[dict] = []
        self.errors: list[dict] = []
        self.graceful: list[dict] = []

    # ------------------------------------------------------------------ #
    def send_text(self, text: str, chat_id: str = CHAT_ID, sender: str = USER_ID) -> None:
        raw = {"update": {"type": "NewMessage", "chat_id": chat_id,
                          "new_message": {"message_id": str(int(time.time() * 1000)),
                                          "text": text, "sender_id": sender,
                                          "sender_type": "User",
                                          "aux_data": {"button_id": None}}}}
        self._run(raw)

    def click(self, button_id: str, chat_id: str = CHAT_ID, sender: str = USER_ID) -> None:
        raw = {"inline_message": {"sender_id": sender, "chat_id": chat_id,
                                  "message_id": str(int(time.time() * 1000)),
                                  "text": "", "aux_data": {"button_id": button_id}}}
        self._run(raw)

    def _run(self, raw: dict) -> None:
        before = len(self.client.sent)
        update = parse_update(raw)
        if update is None:
            return
        ctx = Context(self.client, self.db, update)
        from astra.core.router import handle
        handle(ctx)
        # پیام‌های جدید این مرحله
        for record in self.client.sent[before:]:
            method = record.get("method")
            payload = record.get("payload") or {}
            if method not in ("sendMessage", "editMessageText", "sendFile"):
                continue
            text = payload.get("text") or payload.get("caption") or ""
            self.transcript.append({
                "text": text,
                "keyboard": payload.get("inline_keypad"),
                "trigger": update.button_id or update.text,
            })
            if not text.strip():
                self.errors.append({"issue": "پیام خالی",
                                    "trigger": update.button_id or update.text})
        for log in self.db.recent_logs("ERROR", limit=50):
            entry = {"issue": f"لاگ خطا: {log['where_']}",
                     "detail": log["message"][:160]}
            if entry in self.errors or entry in self.graceful:
                continue
            # در حالت آفلاین، خطای سرویس‌های خارجی رفتارِ درست (مدیریت نرم) است
            offline_expected = ("شبیه‌سازی" in entry["detail"]
                                 or any(w in entry["issue"] for w in ("weather", "market")))
            if not self.online and offline_expected:
                self.graceful.append(entry)
            else:
                self.errors.append(entry)

    # ------------------------------------------------------------------ #
    def collect_buttons(self, keyboard: dict | None) -> list[str]:
        if not keyboard:
            return []
        return [b["id"] for row in keyboard.get("rows", []) for b in row.get("buttons", [])
                if b.get("type") in (None, "", "Simple")
                if b.get("id")]

    def walk(self, start_callbacks: list[str], max_steps: int = 400) -> None:
        queue = list(start_callbacks)
        steps = 0
        while queue and steps < max_steps:
            callback = queue.pop(0)
            steps += 1
            if callback in self.visited:
                continue
            self.visited.add(callback)

            if not self.online and any(callback.startswith(p) for p in SKIP_OFFLINE):
                continue

            before = len(self.client.sent)
            self.click(callback)
            # دکمه‌های جدیدی که در پیام‌های این مرحله ظاهر شده‌اند
            for record in self.client.sent[before:]:
                for button_id in self.collect_buttons(
                        (record.get("payload") or {}).get("inline_keypad")):
                    if button_id not in self.visited and button_id not in queue:
                        queue.append(button_id)
            self.check_route(callback)

    def check_route(self, callback: str) -> None:
        """بررسی اینکه این callback اصلاً handler دارد یا نه."""
        from astra.core.router import find_callback_route
        handler, _, _ = find_callback_route(callback)
        if handler is None:
            self.dead_ends.append(callback)

    # ------------------------------------------------------------------ #
    def report(self) -> dict:
        return {
            "routes": len(CALLBACK_ROUTES) + len(CALLBACK_PREFIXES),
            "states": len(STATE_ROUTES),
            "commands": len(COMMAND_ROUTES),
            "text_rules": len(TEXT_HANDLERS),
            "visited_callbacks": len(self.visited),
            "messages_sent": len(self.transcript),
            "dead_ends": self.dead_ends,
            "errors": self.errors[:10],
            "graceful_degradations": len(self.graceful),
        }


# --------------------------------------------------------------------------- #
def offline_services() -> None:
    """در حالت آفلاین، سرویس‌های اینترنتی خطای کنترل‌شده می‌دهند."""
    from astra.services import http

    def fake_request(*args, **kwargs):
        raise http.ServiceError("حالت شبیه‌سازی: ارتباط غیرفعال است")
    http.request = fake_request          # type: ignore[assignment]
    http.get_json = fake_request         # type: ignore[assignment]
    http.get_bytes = fake_request         # type: ignore[assignment]
    http.get_text = fake_request          # type: ignore[assignment]


# --------------------------------------------------------------------------- #
def main() -> int:
    online = "--online" in sys.argv
    if not online:
        offline_services()

    sim = Simulator(online=online)
    print("🚀 شروع شبیه‌سازی آسترا...\n")

    # ۱) شروع و دستورات پایه
    for cmd in ["/start", "/help", "/id", "/ping", "/vip", "/admin"]:
        sim.send_text(cmd)
    print(f"✓ دستورات پایه اجرا شد ({len(sim.transcript)} پیام)")

    # ۲) پیمایش خودکار همه‌ی منوها
    sim.walk([b["id"] for row in main_menu()["rows"] for b in row["buttons"]])
    print(f"✓ پیمایش منوها انجام شد ({len(sim.visited)} دکمه)")

    # ۳) سناریوهای متنی (زبان طبیعی)
    scenarios = [
        "سلام", "آب و هوا تهران", "قیمت دلار", "فونت آسترا", "12*8",
        "10 کیلومتر به متر", "جوک بگو", "ساعت", "مرسی",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "چی کار می‌تونی بکنی؟",
    ]
    for text in scenarios:
        sim.send_text(text)
    print(f"✓ سناریوهای متنی اجرا شد ({len(scenarios)} مورد)")

    # ۴) سناریوهای گروهی
    sim.send_text("/start", chat_id=GROUP_ID)
    sim.send_text("سلام بچه‌ها", chat_id=GROUP_ID)
    sim.click("menu:group", chat_id=GROUP_ID)
    print("✓ سناریوهای گروه اجرا شد")

    report = sim.report()
    print("\n" + "─" * 46)
    print("📊 نتیجه‌ی شبیه‌سازی")
    print("─" * 46)
    for key in ("routes", "states", "commands", "text_rules",
                "visited_callbacks", "messages_sent"):
        print(f"▫️ {key:<20} {report[key]}")
    print(f"▫️ {'بن‌بست‌ها':<20} {len(report['dead_ends'])}")
    if report["dead_ends"]:
        print("   ⚠️ مسیرهای بدون handler:")
        for item in report["dead_ends"]:
            print(f"     - {item}")
    print(f"▫️ {'خطاها':<20} {len(report['errors'])}")
    for err in report["errors"]:
        print(f"     - {err.get('issue')} | {err.get('detail', '')[:110]}")

    ok = not report["dead_ends"] and not report["errors"]
    print("\n" + ("✅ همه‌ی مسیرها سالم و بدون بن‌بست هستند." if ok
                  else "⚠️ مواردی نیاز به بررسی دارد (بالا را ببین)."))

    # ذخیره‌ی رونوشت برای ساخت پیش‌نمایش
    out = Path(__file__).resolve().parent / "data" / "transcript.json"
    out.write_text(json.dumps(sim.transcript, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"📝 رونوشت گفتگوها در {out.relative_to(Path.cwd())} ذخیره شد.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
