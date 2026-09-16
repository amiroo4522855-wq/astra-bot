"""پیام‌ساز: ساختِ متنِ تبریک، تسلیت، تشکر، عاشقانه و … با نامِ دلخواه."""
from __future__ import annotations

import re

from ..core.context import Context
from ..core.keyboards import btn, kb
from ..core.router import command, route, state
from ..core.utils import SEPARATOR, en_to_fa, fa_to_en
from ..services import messages


def _rows(rows: list[list[tuple]]) -> dict:
    board = kb()
    for row in rows:
        board = board.row(*[btn(t, d) for t, d in row])
    return board.build()


def _cat_keyboard():
    rows, cats = [], messages.categories()
    for i in range(0, len(cats), 2):
        pair = cats[i:i + 2]
        rows.append([(f"{c['icon']} {c['name']}", f"msg:cat:{c['id']}") for c in pair])
    rows.append([("🏠 منوی اصلی", "nav:home")])
    return _rows(rows)


def _tone_keyboard(cat: str):
    rows, tones = [], messages.tones()
    for i in range(0, len(tones), 2):
        pair = tones[i:i + 2]
        rows.append([(f"{t['icon']} {t['name']}", f"msg:tone:{cat}|{t['id']}")
                     for t in pair])
    rows.append([("↩️ مناسبت‌ها", "menu:msg")])
    return _rows(rows)


def _gen(cat: str, tone: str, lines: int, named: bool) -> str:
    return f"msg:gen:{cat}|{tone}|{lines}|{1 if named else 0}"


def _msg_keyboard(cat: str, tone: str, lines: int, named: bool):
    rows = [
        [("🎲 متنِ دیگر", _gen(cat, tone, lines, named))],
        [("➖ کوتاه‌تر", _gen(cat, tone, max(3, lines - 3), named)),
         ("➕ بلندتر", _gen(cat, tone, min(20, lines + 3), named))],
        [("📝 نامِ گیرنده و فرستنده" if not named else "✏️ تغییرِ نام‌ها",
          f"msg:ask:{cat}|{tone}|{lines}")],
        [("🎭 تغییرِ لحن", f"msg:cat:{cat}"), ("📂 مناسبتِ دیگر", "menu:msg")],
        [("✨ تنظیمِ کامل در مینی‌اپ", "app:open"), ("🏠 منوی اصلی", "nav:home")],
    ]
    return _rows(rows)


@command("/msg", "/payam", "/tabrik")
@route("menu:msg")
def msg_menu(ctx: Context) -> None:
    cats = messages.categories()
    if not cats:
        ctx.send("✍️ پیام‌ساز در دسترس نیست؛ کمی بعد دوباره امتحان کنید 🙏")
        return
    ctx.send(
        "✍️ پیام‌سازِ آسترا\n"
        f"{SEPARATOR}\n"
        "برای هر مناسبت، با ۵ لحنِ مختلف (ادبی، فرهنگی، اجتماعی، خودمانی، شاعرانه)\n"
        "و تا ۲۰ خط متنِ آماده می‌سازم.\n"
        f"{SEPARATOR}\n"
        "مناسبت را انتخاب کنید 👇",
        _cat_keyboard(),
    )


@route("msg:cat:", prefix=True)
def msg_tones(ctx: Context) -> None:
    cat = (ctx.arg or "").split(":")[-1].strip() or "tabrik"
    ctx.send(
        f"{messages.cat_name(cat)}\n{SEPARATOR}\n"
        "لحنِ پیام را انتخاب کنید:",
        _tone_keyboard(cat),
    )


def _parts(ctx: Context) -> list[str]:
    """جداسازیِ بخش‌های فشرده (cat|tone|lines|named)."""
    raw = (ctx.arg or "").strip()
    return [p.strip() for p in raw.split("|") if p.strip() != "" or True]


@route("msg:tone:", prefix=True)
def msg_generate_from_tone(ctx: Context) -> None:
    parts = _parts(ctx)
    cat = parts[0] if parts else "tabrik"
    tone = parts[1] if len(parts) > 1 else messages.DEFAULT_TONE
    _show(ctx, cat, tone, 8, False)


@route("msg:gen:", prefix=True)
def msg_generate(ctx: Context) -> None:
    parts = _parts(ctx)
    cat = parts[0] if parts else "tabrik"
    tone = parts[1] if len(parts) > 1 else messages.DEFAULT_TONE
    try:
        lines = int(fa_to_en(parts[2] or "8")) if len(parts) > 2 else 8
    except ValueError:
        lines = 8
    named = len(parts) > 3 and parts[3] == "1"
    _show(ctx, cat, tone, lines, named)


def _key(ctx: Context, name: str) -> str:
    return f"msg_{name}:{ctx.update.sender_id or ctx.update.chat_id or '0'}"


def _get(ctx: Context, name: str) -> str:
    try:
        return str(ctx.db.get_setting(_key(ctx, name)) or "")
    except Exception:
        return ""


def _set(ctx: Context, name: str, value: str) -> None:
    try:
        ctx.db.set_setting(_key(ctx, name), value)
    except Exception:
        pass


def _show(ctx: Context, cat: str, tone: str, lines: int, named: bool) -> None:
    to, frm = _get(ctx, "to"), _get(ctx, "from")
    text = messages.render(cat, tone, lines, to=to, from_=frm,
                           poem=tone in ("adabi", "shaerane"))
    if not text:
        ctx.send("✍️ متنی ساخته نشد؛ دوباره تلاش کنید 🙏", _cat_keyboard())
        return
    ctx.send(
        text + "\n" + SEPARATOR + "\n"
        f"📏 {en_to_fa(lines)} خط · برای تغییر از دکمه‌ها استفاده کنید 👇",
        _msg_keyboard(cat, tone, lines, bool(to or frm)),
    )


@route("msg:ask:", prefix=True)
def msg_ask(ctx: Context) -> None:
    parts = _parts(ctx)
    if len(parts) >= 3:                       # مناسبت و لحن را برای بعد ذخیره کن
        _set(ctx, "cat", parts[0])
        _set(ctx, "tone", parts[1])
        _set(ctx, "lines", parts[2])
    ctx.send(
        "📝 نامِ گیرنده و فرستنده را بنویسید\n"
        f"{SEPARATOR}\n"
        "مثال: «مژگان از امیر»\n"
        "یا فقط نامِ گیرنده: «مژگان»",
    )
    ctx.state = "msg_names"


@state("msg_names")
def msg_names(ctx: Context) -> None:
    """ذخیره‌ی نام‌ها و ساختِ پیام."""
    raw = (ctx.text or "").strip()
    to, frm = "", ""
    if " از " in raw:
        to, frm = [p.strip() for p in raw.split(" از ", 1)]
    else:
        to = raw
    _set(ctx, "to", to[:40])
    _set(ctx, "from", frm[:40])
    ctx.state = ""
    cat = _get(ctx, "cat") or "tabrik"
    tone = _get(ctx, "tone") or messages.DEFAULT_TONE
    try:
        lines = int(_get(ctx, "lines") or "8")
    except ValueError:
        lines = 8
    ctx.send(f"✅ نام‌ها ثبت شد: «{to or '—'}» از طرفِ «{frm or '—'}»")
    _show(ctx, cat, tone, lines, True)
