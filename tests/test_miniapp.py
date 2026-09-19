"""بررسیِ خودکارِ مینی‌اپ (docs/index.html).

این تست‌ها جلوی خطاهای رایجِ رابط را می‌گیرند:
  • syntaxِ جاوااسکریپت (در صورتِ در دسترس بودنِ node)
  • آیدی‌های استفاده‌شده در JS که در HTML تعریف نشده‌اند
  • آیکون‌های SVG‌ی ارجاع‌شده بدونِ symbol
  • کامل بودنِ متغیرهای تمِ روشن
  • موجود بودنِ توابعِ کلیدی (تم، فونت‌ساز، چت، بازی)
"""
from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
SCRIPT = re.findall(r"<script>(.*?)</script>", HTML, re.S)[0]
STYLE = re.search(r"<style>(.*?)</style>", HTML, re.S).group(1)


class TestMiniApp(unittest.TestCase):
    def test_javascript_syntax(self):
        if not shutil.which("node"):
            self.skipTest("node در دسترس نیست")
        tmp = Path("/tmp/_miniapp_check.js")
        tmp.write_text(SCRIPT, encoding="utf-8")
        proc = subprocess.run(["node", "--check", str(tmp)],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr[:400])

    def test_referenced_ids_exist(self):
        defined = set(re.findall(r'id="([A-Za-z0-9_-]+)"', HTML))
        used = set(re.findall(r"\$\('#([A-Za-z0-9_-]+)'\)", SCRIPT))
        # chTyping به‌صورت پویا ساخته می‌شود
        missing = sorted(used - defined - {"chTyping"})
        self.assertEqual(missing, [], f"آیدی‌های تعریف‌نشده: {missing}")

    def test_no_emoji_in_the_interface(self):
        """هیچ ایموجی‌ای در رابط نمانده باشد (همه چیز SVG)."""
        PIC = re.compile("[\U0001F000-\U0001FAFF\u2600-\u26FF\u2700-\u27BF\u2B00-\u2BFF]")
        found = [c for c in PIC.findall(HTML) if c not in "\u2500"]
        self.assertEqual([], found, f"ایموجی‌های باقیمانده: {sorted(set(found))}")

    def test_svg_is_never_put_into_text_content(self):
        """SVG در textContent به‌صورت متن دیده می‌شود؛ باید innerHTML باشد."""
        bad = re.findall(r"\.textContent\s*=\s*[^;\n]*<svg", SCRIPT)
        self.assertEqual([], bad, "SVG نباید با textContent ست شود")

    def test_every_icon_has_a_symbol(self):
        used = set(re.findall(r'href="#(i-[a-z0-9-]+)"', HTML))
        symbols = set(re.findall(r'<symbol id="(i-[a-z0-9-]+)"', HTML))
        self.assertEqual(sorted(used - symbols), [], "آیکون بدون symbol")

    def test_light_theme_defines_all_colours(self):
        root = STYLE[STYLE.index(":root{"):STYLE.index("}", STYLE.index(":root{"))]
        light = STYLE[STYLE.index('[data-theme="light"]{'):
                      STYLE.index("}", STYLE.index('[data-theme="light"]{'))]
        root_vars = set(re.findall(r"--([\w-]+):", root))
        light_vars = set(re.findall(r"--([\w-]+):", light))
        # e / e2 / r مربوط به زمان‌بندی و شعاع هستند و به تم وابسته نیستند
        untouched = sorted(root_vars - light_vars - {"e", "e2", "r"})
        self.assertEqual(untouched, [], f"متغیرهای بازتعریف‌نشده: {untouched}")

    def test_key_functions_exist(self):
        for name in ("function themeInit(", "function wikiAnswer(", "function chHas(",
                     "function dzWinLine(", "function initNameFont(", "function fitChat("):
            self.assertIn(name, SCRIPT, f"{name} یافت نشد")

    def test_font_maker_supports_both_languages(self):
        self.assertIn("const FA_STYLES=[", SCRIPT)
        self.assertIn("const EN_STYLES=[", SCRIPT)
        self.assertIn("FINGLISH", SCRIPT)

    def test_theme_toggle_is_wired(self):
        self.assertIn('id="themeBtn"', HTML)
        self.assertIn("localStorage.setItem('theme'", SCRIPT)

    def test_every_send_action_has_a_server_handler(self):
        """هر send('x') در مینی‌اپ باید هندلر داشته باشد (هیچ بن‌بستی مجاز نیست)."""
        import sys as _sys
        from pathlib import Path as _P
        root = _P(__file__).resolve().parent.parent
        _sys.path.insert(0, str(root))
        from astra.handlers import miniapp
        actions = set(re.findall(r"send\(\s*'([a-z_]+)'", SCRIPT))
        self.assertTrue(actions, "هیچ send() ای یافت نشد")
        missing = sorted(a for a in actions if a not in miniapp.ACTIONS)
        self.assertEqual([], missing, f"این actionها در سرور هندلر ندارند: {missing}")

    def test_pro_player_present(self):
        """پلیرِ حرفه‌ای: شیتِ بزرگ، ویژوالایزر، نوارِ مینی."""
        for part in ('id="muSheet"', 'id="muViz"', 'id="muArtInner"',
                     'id="muPlayMini"', 'id="muPlayer"'):
            self.assertIn(part, HTML, f"{part} یافت نشد")
        for fn in ("function muExpand(", "function muReact(", "function muGraph(",
                   "function muPaint(", "function muAutoRise(", "function muBindPlayer("):
            self.assertIn(fn, SCRIPT, f"{fn} یافت نشد")

    def test_player_rises_behind_the_dock(self):
        """شیت باید z-index پایین‌تر از منوی موبایلی داشته باشد (از پشتِ آن بالا بیاید)."""
        def z(sel):
            i = STYLE.index(sel)
            return int(re.search(r"z-index:(\d+)", STYLE[i:i + 400]).group(1))
        zs, zt = z(".mu-sheet{"), z("\n.tabs{")
        self.assertLess(zs, zt, "شیت باید پشتِ منوی موبایلی باشد")

    def test_support_id_is_everywhere(self):
        self.assertIn("AmirZed4", HTML)
        self.assertIn("function openSupport(", SCRIPT)
        self.assertIn("data-support", HTML)

    def test_home_hero_and_quick_rail(self):
        for part in ('id="homeHero"', 'id="rail"', 'id="greet"', 'id="stTools"'):
            self.assertIn(part, HTML, f"{part} یافت نشد")
        for fn in ("function initHome(", "function greetText(", "function faDate("):
            self.assertIn(fn, SCRIPT, f"{fn} یافت نشد")

    def test_new_tools_are_registered(self):
        """BMI، تایمر و ثانیه‌شمار باید واقعاً در اپ باشند."""
        for part in ("k:'bmi'", "k:'timer'", "k:'stopwatch'",
                     "function initBmi(", "function initTimer(",
                     "function initStopwatch(", "function bmiCalc("):
            self.assertIn(part, SCRIPT, f"{part} یافت نشد")

    def test_bmi_bands_cover_all_ranges(self):
        body = SCRIPT[SCRIPT.index("const BMI_BANDS=["):]
        body = body[:body.index("\n];")]
        self.assertIn("18.5", body)
        self.assertIn("25", body)
        self.assertIn("30", body)
        self.assertIn("چاقی", body)

    def test_design_system_uses_the_new_palette(self):
        """رنگ‌هایِ هویت: مشکیِ مات، آبی‌یخی، قرمزِ جیغ، ترکیبیِ ویژه."""
        self.assertIn("#0b0d10", STYLE)   # مشکیِ مات
        self.assertIn("#38bdf8", STYLE)   # آبی‌یخی
        self.assertIn("#ff2d4b", STYLE)   # قرمزِ جیغ
        self.assertIn("#818cf8", STYLE)   # ترکیبیِ ویژه

    def test_price_board_has_dollar_theme(self):
        self.assertIn("function pxBoard(", SCRIPT)
        self.assertIn(".px-hero{", STYLE)
        self.assertIn("px-hero:before", STYLE)   # بافتِ دلاری

    def test_grouped_list_rows_exist(self):
        self.assertIn("function rowHtml(", SCRIPT)
        self.assertIn(".lgroup{", STYLE)

    def test_timer_and_stopwatch_keep_running(self):
        """بازگشت به ابزار نباید تایمر/ثانیه‌شمار را صفر کند."""
        self.assertIn("TM.started", SCRIPT)
        self.assertIn("if(TM.total && TM.started){", SCRIPT)
        self.assertIn("if(SW.running && !SW.raf)", SCRIPT)

    def test_win_line_survives_empty_winner(self):
        """خطِ پیروزی نباید هنگامِ نبودِ برنده خطا بدهد (باگِ قبلی)."""
        body = SCRIPT[SCRIPT.index("function dzWinLine("):]
        body = body[:body.index("\nfunction ")]
        self.assertIn("if(!L", body.replace(" ", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
