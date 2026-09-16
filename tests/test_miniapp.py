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

    def test_win_line_survives_empty_winner(self):
        """خطِ پیروزی نباید هنگامِ نبودِ برنده خطا بدهد (باگِ قبلی)."""
        body = SCRIPT[SCRIPT.index("function dzWinLine("):]
        body = body[:body.index("\nfunction ")]
        self.assertIn("if(!L", body.replace(" ", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
