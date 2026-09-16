"""استیکر‌سازِ واقعی: متن یا عکس → استیکرِ WebP."""
from __future__ import annotations

import tempfile
from pathlib import Path

from ..core.context import Context
from ..core.keyboards import btn, kb
from ..core.router import command, route, state
from ..core.utils import SEPARATOR
from ..services import sticker as svc


def _key(ctx: Context, name: str) -> str:
    return f"sticker_{name}:{ctx.update.sender_id or ctx.update.chat_id or '0'}"


def _get(ctx: Context, name: str, default: str = "") -> str:
    try:
        return str(ctx.db.get_setting(_key(ctx, name)) or default)
    except Exception:
        return default


def _set(ctx: Context, name: str, value: str) -> None:
    try:
        ctx.db.set_setting(_key(ctx, name), value)
    except Exception:
        pass


def _send(ctx: Context, data: bytes, note: str = "") -> None:
    tmp = Path(tempfile.gettempdir()) / f"astra_sticker_{abs(hash(data)) % 10**8}.webp"
    tmp.write_bytes(data)
    try:
        sender = getattr(ctx.client, "send_sticker_path", None)
        if sender:
            sender(chat_id=ctx.chat_id, path=str(tmp))
        else:                                   # پلتفرم‌های دیگر: به‌صورت تصویر
            ctx.client.send_file(ctx.chat_id, f"local:{tmp}", note, "Image")
    except Exception as exc:
        ctx.log_error("sticker.send", exc)
        ctx.send("🙈 نتوانستم استیکر را بفرستم؛ دوباره امتحان کن 🙏")
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def _menu(ctx: Context) -> dict:
    style = _get(ctx, "style", "violet")
    names = dict((k, n) for k, n, _ in svc.styles_list())
    return (
        kb()
        .row(btn("✍️ متن به استیکر", "sticker:text"),
             btn("🖼 عکس به استیکر", "sticker:photo"))
        .row(btn(f"🎨 سبک: {names.get(style, style)}", "sticker:style"))
        .row(btn("🏠 منوی اصلی", "nav:home"))
        .build()
    )


@command("/sticker", "/stikcer")
@route("menu:sticker")
def sticker_menu(ctx: Context) -> None:
    if not svc.available():
        ctx.send("🎨 بخشِ استیکر‌ساز فعلاً روی این سرور در دسترس نیست 🙏\n"
                 f"{SEPARATOR}\n"
                 "بقیه‌ی بخش‌ها مثل همیشه کار می‌کنند ✨",
                 kb().row(btn("🏠 منوی اصلی", "nav:home")).build())
        return
    ctx.send(
        "🎨 استیکر‌سازِ آسترا\n"
        f"{SEPARATOR}\n"
        "یک متن بنویس یا یک عکس بفرست؛ من آن را به استیکرِ واقعی\n"
        "(WebP با فونتِ فارسی و پس‌زمینه‌ی گرادیانی) تبدیل می‌کنم ✨\n"
        f"{SEPARATOR}\n"
        "یکی را انتخاب کن 👇",
        _menu(ctx),
    )


@route("sticker:text")
def sticker_text(ctx: Context) -> None:
    ctx.state = "sticker_text"
    ctx.send(
        "✍️ متنِ استیکر را بنویس\n"
        f"{SEPARATOR}\n"
        "مثال: «تولدت مبارک مژگان جان» یا «دلم برات تنگ شده بود»\n"
        f"{SEPARATOR}\n"
        "برای لغو: «لغو» را بنویس.",
    )


@state("sticker_text")
def sticker_text_make(ctx: Context) -> None:
    text = (ctx.text or "").strip()
    ctx.state = ""
    if not svc.available():
        ctx.send("🎨 استیکر‌ساز روی این سرور فعال نیست 🙏")
        return
    if text in ("لغو", "/cancel", "❌ انصراف"):
        ctx.send("لغو شد 🙏", _menu(ctx))
        return
    if len(text) < 2:
        ctx.send("✍️ متن خیلی کوتاه است؛ دوباره بنویس 🙏")
        ctx.state = "sticker_text"
        return
    if len(text) > 160:
        text = text[:160]
    style = _get(ctx, "style", "violet")
    try:
        data = svc.text_sticker(text, style)
    except Exception as exc:
        ctx.log_error("sticker.text", exc)
        ctx.send("🙈 در ساختِ استیکر مشکلی پیش آمد؛ دوباره امتحان کن 🙏", _menu(ctx))
        return
    _send(ctx, data)
    ctx.send("✅ استیکر آماده شد — می‌توانی در تلگرام به استیکرها اضافه‌اش کنی 🎨",
             _menu(ctx))


@route("sticker:photo")
def sticker_photo(ctx: Context) -> None:
    ctx.state = "sticker_photo"
    ctx.send(
        "🖼 یک عکس بفرست تا استیکرش کنم\n"
        f"{SEPARATOR}\n"
        "عکس را به‌صورتِ معمولی (بدون فشرده‌سازی) بفرست تا کیفیت حفظ شود.\n"
        f"{SEPARATOR}\n"
        "برای لغو: «لغو» را بنویس.",
    )


@state("sticker_photo")
def sticker_photo_make(ctx: Context) -> None:
    update = ctx.update
    if (ctx.text or "").strip() in ("لغو", "/cancel", "❌ انصراف"):
        ctx.state = ""
        ctx.send("لغو شد 🙏", _menu(ctx))
        return
    file_id = getattr(update, "file_id", "") or ""
    if not file_id:
        ctx.send("🖼 هنوز عکسی نفرستادی؛ یک عکس بفرست یا «لغو» بنویس 🙏")
        return
    ctx.state = ""
    try:
        url = ctx.client.get_file(file_id)
        import requests
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = svc.photo_sticker(response.content)
    except Exception as exc:
        ctx.log_error("sticker.photo", exc)
        ctx.send("🙈 نتوانستم این عکس را به استیکر تبدیل کنم؛ عکسِ دیگری بفرست 🙏",
                 _menu(ctx))
        return
    _send(ctx, data)
    ctx.send("✅ استیکرِ عکست آماده شد 🖼", _menu(ctx))


@route("sticker:style")
def sticker_style(ctx: Context) -> None:
    rows = []
    items = svc.styles_list()
    for i in range(0, len(items), 2):
        pair = items[i:i + 2]
        rows.append([(f"🎨 {p[1]}", f"sticker:set:{p[0]}") for p in pair])
    rows.append([("🏠 منوی اصلی", "nav:home")])
    board = kb()
    for row in rows:
        board = board.row(*[btn(t, d) for t, d in row])
    ctx.send("🎨 سبکِ پس‌زمینه را انتخاب کن:", board.build())


@route("sticker:set:", prefix=True)
def sticker_set_style(ctx: Context) -> None:
    key = (ctx.arg or "").split(":")[-1].strip()
    valid = {k for k, _, _ in svc.styles_list()}
    if key not in valid:
        key = "violet"
    _set(ctx, "style", key)
    names = dict((k, n) for k, n, _ in svc.styles_list())
    ctx.send(f"✅ سبکِ «{names.get(key, key)}» انتخاب شد.", _menu(ctx))
