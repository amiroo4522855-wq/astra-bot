"""تست‌های واحد ربات آسترا (بدون نیاز به اینترنت یا توکن).

اجرا:
    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astra import config                                    # noqa: E402
from astra.core import db as db_module                      # noqa: E402
from astra.core.context import parse_update                 # noqa: E402
from astra.core.keyboards import InlineKeyboard, btn, main_menu  # noqa: E402
from astra.core.router import find_callback_route           # noqa: E402
from astra.core import utils                                # noqa: E402
from astra.services import calculator, convert, fonts, media, radio  # noqa: E402
from astra.services.clock import city_time, now_report, tehran_time  # noqa: E402

import astra.handlers  # noqa: E402,F401  — برای ثبت مسیرها


# --------------------------------------------------------------------------- #
class TestUtils(unittest.TestCase):
    def test_digits(self):
        self.assertEqual(utils.en_to_fa("1234567890"), "۱۲۳۴۵۶۷۸۹۰")
        self.assertEqual(utils.fa_to_en("۱۲۳"), "123")
        self.assertEqual(utils.fa_to_en("١٢٣"), "123")

    def test_money(self):
        self.assertIn("\u066c", utils.money(1234567))   # جداکننده‌ی هزارگانِ فارسی
        self.assertTrue(utils.money(1000).startswith("۱"))

    def test_jalali(self):
        self.assertEqual(utils.gregorian_to_jalali(2024, 3, 20), (1403, 1, 1))
        self.assertEqual(utils.gregorian_to_jalali(2025, 3, 21), (1404, 1, 1))

    def test_chunk_text(self):
        text = "خط اول\n" * 2000
        chunks = utils.chunk_text(text, 1000)
        self.assertTrue(chunks)
        self.assertTrue(all(len(c) <= 1000 for c in chunks))

    def test_url_detection(self):
        self.assertEqual(utils.extract_url("سلام https://rubika.ir چه خبر"),
                         "https://rubika.ir")
        self.assertTrue(utils.is_url("https://example.com"))
        self.assertFalse(utils.is_url("سلام"))

    def test_clean_and_size(self):
        self.assertEqual(utils.clean("  سلام   دنیا  "), "سلام دنیا")
        self.assertTrue(utils.format_size(2048).endswith("کیلوبایت"))


class TestCalculator(unittest.TestCase):
    def test_basic(self):
        self.assertAlmostEqual(calculator.calculate("2+3*4"), 14.0)
        self.assertAlmostEqual(calculator.calculate("(2+3)*4"), 20.0)
        self.assertAlmostEqual(calculator.calculate("10/4"), 2.5)

    def test_functions(self):
        self.assertAlmostEqual(calculator.calculate("sqrt(16)"), 4.0)
        self.assertAlmostEqual(calculator.calculate("2**10"), 1024.0)
        self.assertAlmostEqual(calculator.calculate("abs(-7)"), 7.0)

    def test_persian_digits(self):
        self.assertAlmostEqual(calculator.calculate("۱۲+۸"), 20.0)

    def test_unsafe_blocked(self):
        for bad in ("__import__('os').system('ls')", "open('x')", "a + b"):
            with self.assertRaises(Exception):
                calculator.calculate(bad)


class TestConvert(unittest.TestCase):
    def test_length(self):
        self.assertAlmostEqual(convert.convert(1, "km", "m"), 1000.0)
        self.assertAlmostEqual(convert.convert(100, "cm", "m"), 1.0)

    def test_temperature(self):
        self.assertAlmostEqual(convert.convert(100, "f", "c"), 37.777, places=2)
        self.assertAlmostEqual(convert.convert(0, "c", "f"), 32.0)

    def test_text_form(self):
        out = convert.convert_text("10 کیلومتر به متر")
        self.assertIn("تبدیل واحد", out)
        self.assertIn("۱۰۰۰۰", out)

    def test_mismatch_raises(self):
        with self.assertRaises(ValueError):
            convert.convert(1, "km", "kg")


class TestFonts(unittest.TestCase):
    def test_latin_bold(self):
        result = fonts.apply("Hello", "bold")
        self.assertNotEqual(result, "Hello")
        self.assertEqual(len(result), len("Hello"))

    def test_persian_styles(self):
        for style in ("underline", "strike", "overline", "spaced", "glitter"):
            result = fonts.apply("سلام", style)
            self.assertTrue(result, f"سبک {style} خروجی نداشت")
            self.assertIn("س", result)

    def test_all_styles_non_empty(self):
        for style in fonts.ORDER:
            self.assertTrue(fonts.apply("Astra 1403", style), style)

    def test_style_count(self):
        self.assertGreaterEqual(len(fonts.ORDER), 10)


class TestKeyboards(unittest.TestCase):
    def test_main_menu_structure(self):
        menu = main_menu()
        self.assertEqual(len(menu["rows"]), 6)
        for row in menu["rows"]:
            self.assertLessEqual(len(row["buttons"]), 3)

    def test_grid_columns(self):
        keyboard = InlineKeyboard()
        keyboard.grid([(f"b{i}", f"x:{i}") for i in range(7)], per_row=3)
        built = keyboard.build()
        self.assertEqual(len(built["rows"][0]["buttons"]), 3)
        self.assertEqual(len(built["rows"][-1]["buttons"]), 1)

    def test_button_shape(self):
        button = btn("سلام", "a:b")
        self.assertEqual(button["type"], "Simple")
        self.assertEqual(button["id"], "a:b")


class TestRouter(unittest.TestCase):
    def test_dynamic_routes_resolve(self):
        for callback, arg in (("music:q:320", "320"), ("vip:buy:6", "6"),
                              ("group:toggle:anti_link", "anti_link"),
                              ("tools:city:3", "3")):
            handler, _, found_arg = find_callback_route(callback)
            self.assertIsNotNone(handler, f"{callback} بدون handler است")
            self.assertEqual(found_arg, arg)

    def test_unknown_callback(self):
        handler, _, _ = find_callback_route("nothing:here:at:all")
        self.assertIsNone(handler)

    def test_simple_routes(self):
        for callback in ("nav:home", "menu:music", "menu:admin" if False else "menu:vip"):
            handler, _, _ = find_callback_route(callback)
            self.assertIsNotNone(handler, callback)


class TestParsing(unittest.TestCase):
    def test_message(self):
        raw = {"update": {"type": "NewMessage", "chat_id": "u0ABC",
                          "new_message": {"message_id": "1", "text": "سلام",
                                          "sender_id": "u0ABC", "aux_data": {}}}}
        update = parse_update(raw)
        self.assertEqual(update.kind, "message")
        self.assertEqual(update.text, "سلام")
        self.assertEqual(update.chat_type, "private")

    def test_callback(self):
        raw = {"inline_message": {"chat_id": "u0ABC", "sender_id": "u0ABC",
                                  "message_id": "2", "text": "",
                                  "aux_data": {"button_id": "menu:music"}}}
        update = parse_update(raw)
        self.assertEqual(update.kind, "callback")
        self.assertEqual(update.button_id, "menu:music")

    def test_group_chat(self):
        raw = {"update": {"type": "NewMessage", "chat_id": "g0XYZ",
                          "new_message": {"message_id": "3", "text": "hi",
                                          "sender_id": "u0ABC"}}}
        self.assertEqual(parse_update(raw).chat_type, "group")


class TestClock(unittest.TestCase):
    def test_tehran_offset(self):
        now = tehran_now = tehran_time()
        self.assertEqual(now.utcoffset().total_seconds(), 3.5 * 3600)

    def test_city_time(self):
        info = city_time("تهران")
        self.assertIsNotNone(info)
        self.assertRegex(info[1], r"^[۰-۹]+:[۰-۹]+$")

    def test_now_report(self):
        self.assertIn("تهران", now_report())


class TestMiscServices(unittest.TestCase):
    def test_search_link(self):
        self.assertTrue(media.youtube_search_link("آهنگ").startswith("https://"))

    def test_radio_station(self):
        self.assertIsNotNone(radio.station(1))
        self.assertIsNone(radio.station(999))

    def test_vip_plans(self):
        self.assertEqual(len(config.VIP_PLANS), 3)
        self.assertIn("1", config.VIP_PLANS)


class TestDatabase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = db_module.Database(self.tmp.name)

    def tearDown(self) -> None:
        self.db.close()
        Path(self.tmp.name).unlink(missing_ok=True)

    def test_user_flow(self):
        self.db.touch_user("u1", "علی", "ali")
        self.db.touch_user("u1")
        user = self.db.get_user("u1")
        self.assertEqual(user["first_name"], "علی")
        self.assertGreaterEqual(user["msg_count"], 1)
        self.assertEqual(self.db.count_users(), 1)

    def test_vip(self):
        self.db.grant_vip("u2", 30)
        self.assertGreater(self.db.vip_until("u2"), 0)
        self.assertEqual(self.db.count_vip(), 1)
        self.db.revoke_vip("u2")
        self.assertEqual(self.db.count_vip(), 0)

    def test_state_and_nav(self):
        self.db.set_state("u3", "await_city", {"x": 1})
        self.assertEqual(self.db.get_state("u3")[0], "await_city")
        self.db.push_nav("u3", "nav:home")
        self.db.push_nav("u3", "menu:music")
        self.assertEqual(self.db.pop_nav("u3"), "nav:home")
        self.db.clear_state("u3")
        self.assertEqual(self.db.get_state("u3")[0], "")

    def test_limits_and_usage(self):
        self.assertEqual(self.db.bump_daily("u4", "ai_chat"), 1)
        self.assertEqual(self.db.bump_daily("u4", "ai_chat"), 2)
        self.assertEqual(self.db.daily_count("u4", "ai_chat"), 2)
        self.db.bump_usage("music")
        self.assertTrue(self.db.usage_stats())

    def test_playlist(self):
        self.assertTrue(self.db.playlist_add("u5", "آهنگ", "خواننده"))
        self.assertEqual(self.db.playlist_count("u5"), 1)
        items = self.db.playlist_list("u5")
        self.db.playlist_remove("u5", items[0]["id"])
        self.assertEqual(self.db.playlist_count("u5"), 0)

    def test_sections_and_logs(self):
        self.assertTrue(self.db.section_enabled("music"))
        self.db.set_section("music", False)
        self.assertFalse(self.db.section_enabled("music"))
        self.db.set_section("music", True)
        self.db.log("ERROR", "test", "یک خطای تستی")
        self.assertTrue(self.db.recent_logs("ERROR"))

    def test_group_and_warns(self):
        self.db.ensure_group("g1", "گروه تست")
        self.db.set_group("g1", anti_link=1)
        self.assertTrue(self.db.get_group("g1")["anti_link"])
        self.assertEqual(self.db.add_warn("g1", "u9"), 1)
        self.assertEqual(self.db.get_warn("g1", "u9"), 1)
        self.db.reset_warn("g1", "u9")
        self.assertEqual(self.db.get_warn("g1", "u9"), 0)

    def test_payments(self):
        payment_id = self.db.add_payment("u7", "3", "۱۲۹,۰۰۰ تومان")
        self.assertEqual(self.db.get_payment(payment_id)["status"], "pending")
        self.assertEqual(len(self.db.pending_payments()), 1)
        self.db.set_payment(payment_id, "approved")
        self.assertEqual(self.db.get_payment(payment_id)["status"], "approved")


if __name__ == "__main__":
    unittest.main(verbosity=2)
