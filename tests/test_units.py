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
        self.assertEqual(len(menu["rows"]), 7)
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


class TestCities(unittest.TestCase):
    """فهرست شهرهای ایران (داده‌ی محلی برای آب‌وهوا)."""

    def test_cities_loaded(self):
        from astra.services import weather
        cities = weather.cities()
        self.assertGreaterEqual(len(cities), 150)
        self.assertGreaterEqual(len(weather.provinces()), 25)

    def test_find_local_exact(self):
        from astra.services import weather
        place = weather.find_local("کرمانشاه")
        self.assertIsNotNone(place)
        self.assertEqual(place.name, "کرمانشاه")
        self.assertEqual(place.country, "IR")

    def test_find_local_partial(self):
        from astra.services import weather
        place = weather.find_local("بندر")
        self.assertIsNotNone(place)
        self.assertIn("بندر", place.name)

    def test_geocode_uses_local_first(self):
        """بدون اینترنت هم باید شهرهای ایران پیدا شوند."""
        from astra.services import weather
        real_get, weather.get_json = weather.get_json, None   # قطع دسترسی شبکه
        try:
            place = weather.geocode("شیراز")
            self.assertIsNotNone(place)
            self.assertEqual(place.name, "شیراز")
        finally:
            weather.get_json = real_get

    def test_all_province_capitals_exist(self):
        """مرکز هر ۳۱ استان باید در فهرست باشد."""
        from astra.services import weather
        caps = ["تهران","مشهد","اصفهان","شیراز","تبریز","کرج","قم","اهواز","کرمانشاه",
                "ارومیه","رشت","زاهدان","همدان","کرمان","یزد","اردبیل","بندرعباس","بوشهر",
                "زنجان","قزوین","سنندج","ساری","گرگان","خرم‌آباد","بیرجند","ایلام","یاسوج",
                "شهرکرد","بجنورد","سمنان"]
        missing = [c for c in caps if weather.find_local(c) is None]
        self.assertEqual(missing, [], f"جا مانده: {missing}")
        self.assertEqual(len(weather.provinces()), 31)

    def test_unknown_city(self):
        from astra.services import weather
        self.assertIsNone(weather.find_local("شهرخیالینداره"))


class TestChannelPrices(unittest.TestCase):
    """استخراج قیمت از پیام کانال (بدون نیاز به اینترنت)."""

    SAMPLE = (
        "نرخ فروش #دلار، #ارز، #سکه و #طلا در بازار\n"
        "💵 دلار: 233,700 تومان  4010\U0001f53a %1.75+\n"
        "💶 یورو: 268,820 تومان\n"
        "&rlm;\U0001f1e6\U0001f1ea درهم: 63,500 تومان\n"
        "\U0001f539 مثقال طلا: 104,190,000 تومان\n"
        "💸 دلار فردایی تهران \U0001f4b5 233,300 معامله ✅"
    )

    def test_extract_summary_lines(self):
        from astra.services import currency
        rows = dict((label, value) for label, value, _ in currency.extract_channel_rows(self.SAMPLE))
        self.assertIn("💵 دلار", rows)
        self.assertEqual(rows["💵 دلار"], 233700)
        self.assertIn("💶 یورو", rows)
        self.assertIn("🕌 درهم", rows)
        self.assertIn("⚖️ مثقال طلا", rows)

    def test_extract_futures_line(self):
        from astra.services import currency
        rows = dict((label, value) for label, value, _ in currency.extract_channel_rows(self.SAMPLE))
        self.assertIn("💸 دلار فردایی", rows)
        self.assertEqual(rows["💸 دلار فردایی"], 233300)

    def test_rejects_out_of_range(self):
        from astra.services import currency
        rows = currency.extract_channel_rows("💵 دلار: 300 تومان")
        self.assertEqual(rows, [])

    def test_number_with_zwnj(self):
        from astra.services import currency
        self.assertEqual(currency._clean_number("23\u200c\u200c4,\u200c100"), 234100)
        self.assertEqual(currency._clean_number("۱۲۳,۴۵۶"), 123456)

    def test_crypto_unit_is_dollar(self):
        from astra.services import currency
        rows = dict((label, unit) for label, _, unit
                    in currency.extract_channel_rows("🟠 بیت\u200cکوین: 78,794"))
        self.assertEqual(rows.get("🟠 بیت\u200cکوین"), "دلار")


# --------------------------------------------------------------------------- #
# بازی دوز و چت ناشناس
# --------------------------------------------------------------------------- #
class TestDooz(unittest.TestCase):
    """منطق بازی دوز."""

    def test_bot_blocks_immediate_threat(self):
        from astra.services import dooz
        board = dooz.place(dooz.place(dooz.new_board(), 0, dooz.X), 1, dooz.X)
        move = dooz.best_move(board, ai=dooz.O, human=dooz.X)
        self.assertEqual(move, 2)

    def test_bot_takes_the_win(self):
        from astra.services import dooz
        board = dooz.place(dooz.place(dooz.place(dooz.new_board(), 0, dooz.O), 1, dooz.O),
                           4, dooz.X)
        self.assertEqual(dooz.best_move(board, ai=dooz.O, human=dooz.X), 2)

    def test_win_line_detection(self):
        from astra.services import dooz
        board = dooz.place(dooz.place(dooz.place(dooz.new_board(), 0, dooz.X),
                                      4, dooz.X), 8, dooz.X)
        result = dooz.win_line(board)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], dooz.X)

    def test_pro_level_never_loses(self):
        """در ۴۰ بازی تصادفی، رباتِ «حرفه‌ای» هرگز نباید ببازد."""
        from astra.services import dooz
        import random
        for _ in range(40):
            board = dooz.new_board()
            turn = dooz.X
            while not dooz.win_line(board) and not dooz.is_full(board):
                if turn == dooz.X:
                    board = dooz.place(board, random.choice(dooz.free_cells(board)), dooz.X)
                else:
                    board = dooz.place(board, dooz.bot_move(board, "pro"), dooz.O)
                turn = dooz.opponent(turn)
            result = dooz.win_line(board)
            self.assertNotEqual(result and result[0], dooz.X)


class _FakeClient:
    """کلاینت ساختگی برای تستِ جریان‌های گفتگو."""

    def __init__(self):
        self.sent: list[tuple[str, str, dict]] = []
        self.counter = 100

    def send_message(self, chat_id, text, **kwargs):
        self.counter += 1
        self.sent.append((str(chat_id), text, kwargs))
        return {"result": {"message_id": str(self.counter)}}

    def edit_message_text(self, chat_id, message_id, text, inline_keypad=None):
        self.sent.append((str(chat_id), text, {}))
        return {"result": {"message_id": message_id}}

    def send_file(self, chat_id, file_id, caption="", file_type=None, **kwargs):
        self.counter += 1
        self.sent.append((str(chat_id), caption, kwargs))
        return {"result": {"message_id": str(self.counter)}}

    def send_sticker(self, chat_id, sticker_id):
        self.counter += 1
        return {"result": {"message_id": str(self.counter)}}

    def delete_message(self, chat_id, message_id):
        return {"ok": True}

    def last_to(self, chat_id: str) -> str:
        for target, text, _ in reversed(self.sent):
            if target == str(chat_id):
                return text
        return ""


class TestAnonChat(unittest.TestCase):
    """جریان کامل چت ناشناس: ساخت لینک، اتصال، پیام، ریپلای، بستن."""

    def setUp(self):
        import tempfile
        from astra.core.context import Context, Update
        from astra.core.db import Database
        self._dir = tempfile.mkdtemp()
        self.db = Database(str(__import__("pathlib").Path(self._dir) / "t.db"))
        self.client = _FakeClient()

        def make(user_id: str, text: str = "", **kw) -> Context:
            update = Update(kind="message", chat_id=user_id, chat_type="private",
                            sender_id=user_id, text=text, message_id="555",
                            first_name=f"user{user_id}", **kw)
            return Context(self.client, self.db, update)

        self.make = make

    def tearDown(self):
        self.db.close()

    def test_link_create_join_relay_reply_and_close(self):
        from astra.handlers import anon

        # ۱) کاربر A لینک می‌سازد
        ctx_a = self.make("111")
        anon.anon_new(ctx_a)
        links = self.db.anon_owner_links("111")
        self.assertEqual(len(links), 1)
        token = links[0]["token"]

        # ۲) کاربر B با لینک می‌پیوندد
        ctx_b = self.make("222")
        anon.join_request(ctx_b, token)
        ctx_b.arg = token
        anon.anon_join(ctx_b)
        chat_row = self.db.anon_active_chat("222")
        self.assertIsNotNone(chat_row)
        self.assertEqual(str(chat_row["user_a"]), "111")

        # ۳) B پیام می‌دهد → باید به A برسد
        ctx_b = self.make("222", "سلام!")
        anon.anon_talk(ctx_b)
        self.assertIn("سلام!", self.client.last_to("111"))

        # ۴) A روی همان پیام ریپلای می‌زند → باید به B برسد (با reply درست)
        chat_row = self.db.anon_active_chat("111")
        self.assertIsNotNone(chat_row)
        received_id = [mid for (chat, mid) in
                       [(c, None) for c in []]]  # placeholder (unused)
        # شناسه‌ی پیامی که A دریافت کرد (از نگاشت پاسخ)
        rows = self.db._query_all(
            "SELECT msg_id, target FROM anon_msgs WHERE chat_id = ?", ("111",))
        self.assertTrue(rows, "نگاشت پیام ثبت نشده")
        msg_id, target = rows[0]["msg_id"], rows[0]["target"]
        self.assertEqual(target, "555")

        ctx_a = self.make("111", "علیک سلام", reply_to=str(msg_id))
        anon.anon_talk(ctx_a)
        self.assertIn("علیک سلام", self.client.last_to("222"))

        # ۵) B چت را می‌بندد → هر دو طرف آگاه می‌شوند و وضعیت پاک می‌شود
        ctx_b = self.make("222", "🚪 بستن چت")
        anon.anon_talk(ctx_b)
        self.assertIsNone(self.db.anon_active_chat("222"))
        self.assertIsNone(self.db.anon_active_chat("111"))
        self.assertEqual(self.db.get_state("222"), ("", {}))

    def test_block_prevents_reconnect(self):
        from astra.handlers import anon
        token = self.db.anon_create_link("111")
        ctx_b = self.make("222")
        ctx_b.arg = token
        anon.anon_join(ctx_b)
        ctx_b = self.make("222", "🚫 بلاک")
        anon.anon_talk(ctx_b)
        self.assertTrue(self.db.anon_is_blocked("222", "111"))

        # لینک جدیدِ A نباید برای B کار کند
        token2 = self.db.anon_create_link("111")
        ctx_b2 = self.make("222")
        anon.join_request(ctx_b2, token2)
        self.assertIn("امکان برقراری", self.client.last_to("222"))

    def test_reveal_needs_both_sides(self):
        from astra.handlers import anon
        self.db.touch_user("111", "علی", "ali")
        self.db.touch_user("222", "سارا", "sara")
        token = self.db.anon_create_link("111")
        ctx_b = self.make("222")
        ctx_b.arg = token
        anon.anon_join(ctx_b)

        anon.anon_reveal(self.make("222"))
        chat = self.db.anon_active_chat("222")
        self.assertNotEqual(bool(chat["reveal_a"]) and bool(chat["reveal_b"]),
                            True)  # هنوز فقط یک طرف

        anon.anon_reveal(self.make("111"))
        chat = self.db.anon_active_chat("111")
        self.assertTrue(chat["reveal_a"] and chat["reveal_b"])
        self.assertIn("ali", self.client.last_to("111"))
        self.assertIn("sara", self.client.last_to("222"))

    def test_revoked_link_is_dead(self):
        from astra.handlers import anon
        token = self.db.anon_create_link("111")
        ctx = self.make("111")
        ctx.arg = token
        anon.anon_revoke(ctx)
        self.assertEqual(self.db.anon_link(token)["status"], "banned")
        anon.join_request(self.make("222"), token)
        self.assertIn("باطل", self.client.last_to("222"))


class TestBrain(unittest.TestCase):
    """مغزِ آسترا: تشخیص نیت و پاسخ‌های مؤدبانه."""

    def test_normalize_unifies_arabic(self):
        from astra.services import brain
        self.assertEqual(brain.normalize("علي"), "علی")

    def test_greeting_is_detected(self):
        from astra.services import brain
        for text in ("سلام", "درود", "صبح بخیر", "hello"):
            result = brain.analyze(text)
            self.assertEqual(result["kind"], "text", text)
            self.assertTrue(result["text"])

    def test_math_detection(self):
        from astra.services import brain
        for text in ("حاصل ۱۲ ضرب ۵", "۲+۳*۴", "۱۲ تقسیم بر ۴"):
            result = brain.analyze(text)
            self.assertEqual(result["kind"], "calc", text)
            self.assertTrue(result["slots"].get("expr"))

    def test_price_beats_time_when_currency_named(self):
        from astra.services import brain
        self.assertEqual(brain.analyze("قیمت دلار چنده")["kind"], "price")
        self.assertEqual(brain.analyze("ساعت چنده")["kind"], "time")

    def test_conversion_slots(self):
        from astra.services import brain
        result = brain.analyze("۱۰ کیلومتر به متر")
        self.assertEqual(result["kind"], "convert")
        self.assertEqual(result["slots"]["source"], "کیلومتر")
        self.assertEqual(result["slots"]["target"], "متر")

    def test_weather_extracts_city(self):
        from astra.services import brain
        result = brain.analyze("آب و هوا کرمانشاه")
        self.assertEqual(result["kind"], "weather")
        self.assertEqual(result["slots"]["city"], "کرمانشاه")

    def test_bitcoin_is_price_not_poem(self):
        """«بیت‌کوین» نباید به‌خاطر شباهت با «بیت» شعر تلقی شود."""
        from astra.services import brain
        self.assertNotEqual(brain.analyze("بیت\u200cکوین چیست")["kind"], "poem")

    def test_local_summary_picks_key_sentences(self):
        from astra.handlers.ai import _local_summary
        text = ("اقتصاد ایران در سال گذشته رشد داشت. رشد اقتصادی مهم است. "
                "تورم نیز کاهش یافت. کاهش تورم خبر خوبی است. "
                "در پایان باید گفت وضعیت بازار بهتر شد. این متن یک آزمایش است.")
        result = _local_summary(text, lines=2)
        self.assertIn("خلاصه", result)
        self.assertLessEqual(len(result.split("\n")), 7)

    def test_translation_target_detection(self):
        from astra.services import brain
        result = brain.analyze("ترجمه کن good morning")
        self.assertEqual(result["kind"], "translate")
        self.assertEqual(result["slots"]["text"], "good morning")


class TestBrainPrecision(unittest.TestCase):
    """دقتِ مغز: مرزِ واژه‌ها، ارتباطِ دانش و توصیه‌ها."""

    def test_partial_word_is_not_a_currency(self):
        """«اصطلاح» نباید به‌خاطر شباهت با «طلا» قیمت تلقی شود."""
        from astra.services import brain
        self.assertNotEqual(brain.analyze("اصطلاح عجیب")["kind"], "price")

    def test_bitcoin_word_still_detected(self):
        from astra.services import brain
        self.assertEqual(brain.analyze("بیت\u200cکوین چنده")["kind"], "price")

    def test_advice_for_howto_questions(self):
        from astra.services import brain
        self.assertTrue(brain.advice("چطور تمرکزم را بیشتر کنم"))
        self.assertTrue(brain.advice("رمز عبور قوی چطور بسازم"))
        self.assertFalse(brain.advice("عدد بیست و سه"))

    def test_wiki_relevance_check(self):
        from astra.services import brain
        self.assertTrue(brain._relevant("کوانتوم", "کوانتوم"))
        self.assertFalse(brain._relevant("تمرکز حواس", "امیررضا معصومی"))

    def test_greeting_depends_on_hour(self):
        from astra.services import brain
        self.assertIn("صبح", brain.greeting_for(8))
        self.assertIn("شب", brain.greeting_for(23))

    def test_two_word_query_goes_to_knowledge(self):
        from astra.services import brain
        result = brain.analyze("Albert Einstein")
        self.assertEqual(result["kind"], "wiki")


class TestMeaningsAndRouting(unittest.TestCase):
    """معنیِ واژه و مسیریابیِ درستِ ترجمه."""

    def test_meaning_returns_persian_or_empty(self):
        from astra.services import brain
        result = brain.meaning("کتاب")
        if result:                       # در صورت نبودِ اینترنت تست رد نمی‌شود
            self.assertTrue(any("\u0600" <= c <= "\u06ff" for c in result))
            self.assertNotIn("انگلیسی", result.split()[0])

    def test_meaning_rejects_nonsense(self):
        from astra.services import brain
        self.assertEqual(brain.meaning(""), "")
        self.assertEqual(brain.meaning("x"), "")

    def test_translation_target_follows_the_text(self):
        from astra.services import brain
        result = brain.analyze("ترجمه کن good morning")
        self.assertEqual(result["kind"], "translate")
        self.assertEqual(result["slots"]["target"], "فارسی")

    def test_explicit_translation_target_wins(self):
        from astra.services import brain
        result = brain.analyze("ترجمه کن به فرانسوی book")
        self.assertEqual(result["kind"], "translate")
        self.assertEqual(result["slots"]["target"], "فرانسوی")

    def test_persian_meaning_is_definition_not_translation(self):
        from astra.services import brain
        result = brain.analyze("معنی مهربانی")
        self.assertNotEqual(result["kind"], "translate")

    def test_greeting_after_translate_keyword_is_translation(self):
        from astra.services import brain
        self.assertEqual(brain.analyze("ترجمه کن سلام")["kind"], "translate")

    def test_advice_covers_many_topics(self):
        from astra.services import brain
        self.assertGreaterEqual(len(brain.ADVICE), 20)
        for question in ("باتری گوشی زود خالی میشه", "گیاهام خشک شدن",
                         "چطور خلاق‌تر باشم", "سفر ارزان"):
            self.assertTrue(brain.advice(question), question)


class TestBroadcast(unittest.TestCase):
    """ارسالِ پیامِ همگانیِ یک‌باره."""

    def test_pending_file_is_read(self):
        from astra.services import broadcast
        data = broadcast.pending()
        if data is None:
            self.skipTest("پیامِ در انتظاری نیست")
        self.assertTrue(str(data.get("text", "")).strip())

    def test_markdown_becomes_entities(self):
        from astra.services.broadcast import split_markdown
        text, entities = split_markdown("سلام **آسترا** جان")
        self.assertEqual(text, "سلام آسترا جان")
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0]["type"], "bold")
        self.assertEqual(text.encode("utf-16-le")[entities[0]["offset"] * 2:
                                                   (entities[0]["offset"] +
                                                    entities[0]["length"]) * 2]
                         .decode("utf-16-le"), "آسترا")

    def test_emoji_offsets_are_utf16(self):
        from astra.services.broadcast import split_markdown
        text, entities = split_markdown("🎉 **بُردی** عالی")
        raw = text.encode("utf-16-le")
        chunk = raw[entities[0]["offset"] * 2:(entities[0]["offset"] +
                                               entities[0]["length"]) * 2]
        self.assertEqual(chunk.decode("utf-16-le"), "بُردی")

    def test_plain_text_has_no_markers(self):
        from astra.services.broadcast import split_markdown
        text, _ = split_markdown("**الف** و **ب**")
        self.assertNotIn("**", text)


class TestMessageMaker(unittest.TestCase):
    """پیام‌ساز: دسته‌ها، لحن‌ها و ساختِ متن."""

    def test_data_loaded(self):
        from astra.services import messages
        self.assertGreaterEqual(len(messages.categories()), 5)
        self.assertGreaterEqual(len(messages.tones()), 5)

    def test_every_category_has_all_tones(self):
        from astra.services import messages
        data = messages.load()
        for cid, block in (data.get("messages") or {}).items():
            for tone in [t["id"] for t in messages.tones()]:
                self.assertIn(tone, block["openers"], f"{cid}/{tone}")
                self.assertIn(tone, block["closers"], f"{cid}/{tone}")
            self.assertGreaterEqual(len(block["lines"]), 10, cid)

    def test_build_respects_line_count(self):
        from astra.services import messages
        for n in (3, 8, 14, 20):
            lines = messages.build("tabrik", "ejtemaei", n)
            self.assertLessEqual(len(lines), n, f"تعداد خط برای {n}")
            self.assertGreaterEqual(len(lines), 3)

    def test_names_are_inserted(self):
        from astra.services import messages
        lines = messages.build("tabrik", "ejtemaei", 6, to="مژگان", from_="امیر")
        self.assertIn("مژگان", lines[0])
        self.assertIn("امیر", lines[-1])

    def test_no_signature_without_sender(self):
        from astra.services import messages
        lines = messages.build("tabrik", "ejtemaei", 6, to="مژگان", from_="")
        self.assertNotIn("{", " ".join(lines))

    def test_poem_added_when_requested(self):
        from astra.services import messages
        lines = messages.build("asheghane", "shaerane", 16, poem=True)
        self.assertTrue(any("«" in line for line in lines))

    def test_find_category(self):
        from astra.services import messages
        self.assertEqual(messages.find_cat("تبریک"), "tabrik")
        self.assertEqual(messages.find_cat("یک پیام عاشقانه"), "asheghane")
        self.assertIsNone(messages.find_cat(""))

    def test_render_has_header(self):
        from astra.services import messages
        text = messages.render("tabrik", "ejtemaei", 5)
        self.assertIn("✍️", text)
        self.assertIn("───────────────", text)


class TestMusicService(unittest.TestCase):
    """جستجوی واقعیِ موسیقی (بدون اتکا به شبکه در تست)."""

    def test_translit_persian_to_latin(self):
        from astra.services import music
        self.assertEqual(music.translit("ابی"), "abi")
        self.assertTrue(music.translit("گوگوش").startswith("g"))

    def test_relevant_accepts_mixed_scripts(self):
        from astra.services import music
        item = {"title": "Iran", "artist": "Homayoun Shajarian"}
        self.assertTrue(music.relevant(item, "همایون شجریان"))   # فارسی ↔ لاتین

    def test_relevant_rejects_unrelated(self):
        from astra.services import music
        item = {"title": "Cheap Thrills", "artist": "Sia"}
        self.assertTrue(music.relevant(item, "sia"))            # تطبیقِ مستقیم
        same = {"title": "Harighe Sabz", "artist": "Ebi"}
        self.assertFalse(music.relevant(same, "همایون شجریان"))  # بی‌ربط
        self.assertTrue(music.relevant(same, "ابی"))             # اسکلتِ هم‌خوان
        self.assertTrue(music.relevant(same, "ebi"))             # تطبیقِ مستقیم

    def test_merge_prefers_deezer_and_removes_duplicates(self):
        from astra.services import music
        calls = []

        def fake_deezer(q, limit):
            calls.append(("dz", q))
            return [{"id": "dz-1", "title": "Harighe Sabz", "artist": "Ebi",
                     "album": "A", "cover": "", "preview": "http://x/1.mp3",
                     "duration": 200, "link": "", "source": "deezer",
                     "source_name": "Deezer"}]

        def fake_itunes(q, limit):
            calls.append(("it", q))
            return [{"id": "it-1", "title": "harighe sabz", "artist": "ebi",
                     "album": "A", "cover": "", "preview": "http://x/2.m4a",
                     "duration": 200, "link": "", "source": "itunes",
                     "source_name": "Apple Music"}]

        music.deezer_search = fake_deezer
        music.itunes_search = fake_itunes
        try:
            rows = music._merge("ebi", 10, ("deezer", "itunes"))
            self.assertEqual(len(rows), 1)              # تکراری حذف شد
            self.assertEqual(rows[0]["source"], "deezer")
        finally:
            import importlib
            importlib.reload(music)

    def test_line_and_caption(self):
        from astra.services import music
        item = {"title": "Iran", "artist": "Homayoun", "album": "Iran",
                "duration": 200, "source_name": "Deezer"}
        self.assertIn("Iran", music.line(item, 1))
        self.assertIn("Homayoun", music.caption(item))

    def test_youtube_link_is_encoded(self):
        from astra.services import music
        link = music.youtube_search_link("همایون شجریان")
        self.assertTrue(link.startswith("https://www.youtube.com/results"))
        self.assertNotIn(" ", link)


class TestStickerService(unittest.TestCase):
    """ساختِ استیکر واقعی (WebP)."""

    def setUp(self):
        from astra.services import sticker
        if not sticker.available():
            self.skipTest("Pillow نصب نیست")

    def test_text_sticker_is_webp(self):
        from astra.services import sticker
        data = sticker.text_sticker("تولدت مبارک", "violet")
        self.assertGreater(len(data), 1000)
        self.assertEqual(data[:4], b"RIFF")
        self.assertEqual(data[8:12], b"WEBP")

    def test_photo_sticker_is_square_webp(self):
        from astra.services import sticker
        from PIL import Image
        import io
        buf = io.BytesIO()
        Image.new("RGB", (800, 600), "red").save(buf, "PNG")
        data = sticker.photo_sticker(buf.getvalue())
        self.assertEqual(data[8:12], b"WEBP")
        img = Image.open(io.BytesIO(data))
        self.assertEqual(img.size, (512, 512))

    def test_styles_are_valid(self):
        from astra.services import sticker
        styles = sticker.styles_list()
        self.assertGreaterEqual(len(styles), 6)
        for key, name, preview in styles:
            self.assertTrue(key)
            self.assertTrue(name)
            self.assertIn("→", preview)

    def test_shape_keeps_text(self):
        from astra.services import sticker
        out = sticker.shape("آسترا")
        self.assertIsInstance(out, str)
        self.assertTrue(len(out) >= 5)
        self.assertEqual(sticker.shape(""), "")
