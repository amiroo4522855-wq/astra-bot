"""بخش آشپزی ایرانی: ۱۰۰ غذای اصیل با دستورِ کامل."""
from __future__ import annotations

from ..core.context import Context
from ..core.keyboards import btn, kb, main_menu
from ..core.router import command, route, state
from ..core.utils import SEPARATOR, en_to_fa
from ..services import recipes
from .common import tip


def _menu_keyboard():
    """کیبوردِ دسته‌های غذا."""
    rows = []
    cats = recipes.categories()
    for i in range(0, len(cats), 2):
        pair = cats[i:i + 2]
        rows.append([btn(c["name"], f"food:cat:{c['id']}") for c in pair])
    rows.append([btn("🎲 یک پیشنهاد شانسی", "food:random"),
                 btn("🔎 جستجوی نام غذا", "food:ask")])
    rows.append([btn("🏠 منوی اصلی", "nav:home")])
    return _build(rows)


def _build(rows):
    board = kb()
    for row in rows:
        board = board.row(*row)
    return board.build()


@command("/food", "/ghaza", "/ashpazi")
@route("menu:food")
def food_menu(ctx: Context) -> None:
    """منوی آشپزی ایرانی."""
    items = recipes.all_items()
    if not items:
        ctx.send("🍲 مجموعه‌ی دستورها در دسترس نیست؛ کمی بعد دوباره امتحان کنید 🙏",
                 main_menu())
        return
    ctx.send(
        f"🍲 آشپزی ایرانی · {en_to_fa(len(items))} غذای اصیل\n"
        f"{SEPARATOR}\n"
        "دستورِ کاملِ هر غذا: مواد لازم با مقدار، مراحلِ مرحله‌به‌مرحله و یک نکته‌ی طلایی.\n"
        f"{SEPARATOR}\n"
        "یک دسته را انتخاب کنید، یا نامِ غذا را بنویسید\n"
        "مثال: «دستور پخت قورمه‌سبزی»",
        _menu_keyboard(),
    )


@route("food:cat:", prefix=True)
def food_category(ctx: Context) -> None:
    cat = (ctx.arg or "").split(":")[-1].strip()
    pool = recipes.by_category(cat)
    if not pool:
        ctx.send("این دسته خالی است؛ یکی دیگر را انتخاب کنید 🙏", _menu_keyboard())
        return
    name = cat
    for c in recipes.categories():
        if c["id"] == cat:
            name = c["name"]
            break
    rows = []
    for i in range(0, len(pool), 2):
        rows.append([btn(pool[j]["name"], f"food:show:{pool[j]['id']}")
                     for j in range(i, min(i + 2, len(pool)))])
    rows.append([btn("↩️ دسته‌ها", "menu:food"), btn("🏠 منوی اصلی", "nav:home")])
    ctx.send(
        f"{name}\n{SEPARATOR}\n"
        f"{en_to_fa(len(pool))} غذا در این دسته — روی هر کدام بزنید:",
        _build(rows),
    )


@route("food:show:", prefix=True)
def food_show(ctx: Context) -> None:
    rid = (ctx.arg or "").split(":")[-1].strip()
    item = next((i for i in recipes.all_items() if i["id"] == rid), None)
    if not item:
        ctx.send("این غذا پیدا نشد 🤔", _menu_keyboard())
        return
    ctx.send(recipes.render(item) + "\n" + SEPARATOR + "\n" +
             tip("دستورِ غذای بعدی را بپرسید یا «🎲 پیشنهاد» را بزنید."),
             _build([[btn("🎲 پیشنهاد دیگر", "food:random"),
                      btn("🍲 دسته‌ها", "menu:food")],
                     [btn("🏠 منوی اصلی", "nav:home")]]))


@route("food:random")
def food_random(ctx: Context) -> None:
    item = recipes.random_recipe()
    if not item:
        ctx.send("🍲 دستوری در دسترس نیست 🙏", _menu_keyboard())
        return
    ctx.send(recipes.render(item) + "\n" + SEPARATOR + "\n" +
             tip("دستورِ غذای بعدی را بپرسید یا «🎲 پیشنهاد» را بزنید."),
             _build([[btn("🎲 پیشنهاد دیگر", "food:random"),
                      btn("🍲 دسته‌ها", "menu:food")],
                     [btn("🏠 منوی اصلی", "nav:home")]]))


@route("food:ask")
def food_ask(ctx: Context) -> None:
    ctx.send("🔎 نامِ غذا را بنویسید؛ مثلاً: «دستور پخت فسنجان» یا «آش رشته» 🍲")
    ctx.state = "food_query"


@state("food_query")
def food_query(ctx: Context) -> None:
    """پاسخ به نامِ غذایِ تایپ‌شده."""
    item = recipes.find(ctx.text or "")
    if not item:
        ctx.send(
            f"🍲 «{ctx.text}» را در مجموعه‌ام پیدا نکردم\n"
            f"{SEPARATOR}\n"
            "من ۱۰۰ غذای اصیل ایرانی را دارم؛ یکی از دسته‌ها را انتخاب کنید\n"
            "یا دقیق‌تر بنویسید: «دستور پخت ته‌چین»",
            _menu_keyboard(),
        )
        ctx.state = ""
        return
    ctx.send(recipes.render(item), _build([[btn("🎲 پیشنهاد دیگر", "food:random"),
                                            btn("🍲 دسته‌ها", "menu:food")],
                                           [btn("🏠 منوی اصلی", "nav:home")]]))
    ctx.state = ""
