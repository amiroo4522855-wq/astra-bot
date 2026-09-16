"""تست‌های آداپتور تلگرام (بدون نیاز به اینترنت)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astra.core.context import parse_update                  # noqa: E402
from astra.core.factory import resolve_platform              # noqa: E402
from astra.core.keyboards import (btn, chat_keypad, kb, main_menu,  # noqa: E402
                                     web_app_btn)
from astra.core.telegram import (to_inline_keyboard,         # noqa: E402
                                 to_reply_keyboard, detect_platform)


class TestPlatformDetection(unittest.TestCase):
    def test_telegram_token(self):
        token = "123456789:AAF-fakeTokenForTests-1234567890abcdefgh"
        self.assertEqual(detect_platform(token), "telegram")

    def test_rubika_token(self):
        self.assertEqual(detect_platform("CEEBEG0UZLXOQQLWXWPWPDRRWZOHXDWP"), "rubika")

    def test_empty(self):
        self.assertEqual(detect_platform(""), "rubika")

    def test_resolve(self):
        self.assertEqual(resolve_platform("telegram"), "telegram")
        self.assertEqual(resolve_platform("rubika"), "rubika")


class TestKeyboardConversion(unittest.TestCase):
    def test_inline_conversion(self):
        keypad = main_menu()
        result = to_inline_keyboard(keypad)
        self.assertIn("inline_keyboard", result)
        self.assertEqual(len(result["inline_keyboard"]), len(keypad["rows"]))
        first = result["inline_keyboard"][0][0]
        self.assertIn("text", first)
        self.assertIn("callback_data", first)
        self.assertLessEqual(len(first["callback_data"].encode()), 64)

    def test_link_button(self):
        keypad = kb().row({"id": "x", "type": "Link", "button_text": "سایت",
                           "link_url": "https://example.com"}).build()
        button = to_inline_keyboard(keypad)["inline_keyboard"][0][0]
        self.assertEqual(button["url"], "https://example.com")
        self.assertNotIn("callback_data", button)

    def test_reply_keyboard(self):
        keypad = chat_keypad([[("منو", "nav:home"), ("پروفایل", "vip:profile")]])
        result = to_reply_keyboard(keypad)
        self.assertIn("keyboard", result)
        self.assertTrue(result["resize_keyboard"])
        self.assertEqual(result["keyboard"][0][0]["text"], "منو")

    def test_empty_keyboard(self):
        self.assertIsNone(to_inline_keyboard(None))
        self.assertIsNone(to_reply_keyboard({}))
        self.assertIsNone(to_inline_keyboard({"rows": []}))

    def test_main_menu_button_count(self):
        """همه‌ی دکمه‌های منوی اصلی باید به callback_data تبدیل شوند."""
        result = to_inline_keyboard(main_menu())
        total = sum(len(row) for row in result["inline_keyboard"])
        self.assertEqual(total, 11)         # ۱۰ بخش + دکمه‌ی مینی‌اپ


class TestTelegramParsing(unittest.TestCase):
    def test_callback_query(self):
        raw = {"update_id": 10,
               "callback_query": {"id": "999", "data": "menu:music",
                                  "from": {"id": 111, "first_name": "علی"},
                                  "message": {"message_id": 55,
                                              "chat": {"id": 111, "type": "private"}}}}
        update = parse_update(raw)
        self.assertEqual(update.kind, "callback")
        self.assertEqual(update.button_id, "menu:music")
        self.assertEqual(update.sender_id, "111")
        self.assertEqual(update.callback_query_id, "999")
        self.assertEqual(update.chat_type, "private")

    def test_private_message(self):
        raw = {"update_id": 11,
               "message": {"message_id": 12, "text": "سلام",
                           "from": {"id": 222, "first_name": "سارا"},
                           "chat": {"id": 222, "type": "private"}}}
        update = parse_update(raw)
        self.assertEqual(update.kind, "message")
        self.assertEqual(update.text, "سلام")
        self.assertEqual(update.chat_type, "private")

    def test_group_message(self):
        raw = {"update_id": 12,
               "message": {"message_id": 13, "text": "hi",
                           "from": {"id": 333},
                           "chat": {"id": -100123456, "type": "supergroup"}}}
        update = parse_update(raw)
        self.assertEqual(update.chat_type, "group")
        self.assertEqual(update.chat_id, "-100123456")

    def test_photo_message(self):
        raw = {"update_id": 13,
               "message": {"message_id": 14, "caption": "",
                           "from": {"id": 444},
                           "chat": {"id": 444, "type": "private"},
                           "photo": [{"file_id": "small", "width": 90},
                                     {"file_id": "big", "width": 800}]}}
        update = parse_update(raw)
        self.assertEqual(update.file_id, "big")
        self.assertEqual(update.file_type, "Image")

    def test_forwarded_message(self):
        raw = {"update_id": 14,
               "message": {"message_id": 15, "text": "فوروارد",
                           "from": {"id": 555},
                           "chat": {"id": -100999, "type": "group"},
                           "forward_origin": {"type": "user"}}}
        self.assertTrue(parse_update(raw).is_forwarded)

    def test_web_app_data(self):
        raw = {"update_id": 20,
               "message": {"message_id": 21, "text": "",
                           "from": {"id": 666},
                           "chat": {"id": 666, "type": "private"},
                           "web_app_data": {"data": '{"action":"weather","city":"شیراز"}'}}}
        update = parse_update(raw)
        self.assertEqual(update.web_app_data, '{"action":"weather","city":"شیراز"}')
        self.assertEqual(update.sender_id, "666")

    def test_web_app_button_conversion(self):
        keypad = kb().row(web_app_btn("🚀 باز کردن", "https://example.com/app")).build()
        button = to_inline_keyboard(keypad)["inline_keyboard"][0][0]
        self.assertEqual(button["web_app"]["url"], "https://example.com/app")

    def test_rubika_still_works(self):
        raw = {"inline_message": {"chat_id": "u0ABC", "sender_id": "u0ABC",
                                  "message_id": "1", "text": "",
                                  "aux_data": {"button_id": "menu:tools"}}}
        update = parse_update(raw)
        self.assertEqual(update.button_id, "menu:tools")
        self.assertEqual(update.callback_query_id, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
