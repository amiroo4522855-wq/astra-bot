"""بازی «دوز» (❌⭕️): مقابل ربات در چهار سطح، یا دونفره در گروه.

همه چیز با دکمه‌های شیشه‌ای انجام می‌شود؛ هیچ ورودی متنی لازم نیست
و هیچ مسیری بن‌بست ندارد (همیشه «بازی دوباره» و «منوی اصلی» هست).
"""
from __future__ import annotations

import json

from ..core.context import Context
from ..core.keyboards import btn, kb, main_menu
from ..core.router import command, route
from ..core.utils import SEPARATOR, en_to_fa
from ..services import dooz
from .common import enter, guarded, header, tip

BOARD_PREFIX = "dooz:p"


# --------------------------------------------------------------------------- #
# ابزارها
# --------------------------------------------------------------------------- #
def _players(raw: str) -> dict:
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}


def _board_rows(board: str, finished: bool) -> list[list[dict]]:
    return dooz.board_keyboard(board, disabled=finished, prefix=BOARD_PREFIX)


def _build(rows: list[list[dict]], *extra_rows: list[dict]) -> dict:
    keyboard = kb()
    keyboard.rows = list(rows) + [row for row in extra_rows if row]
    return keyboard.build()


def _render(ctx: Context, note: str = "", edit: bool = True) -> None:
    """نمایش تابلو + وضعیت + امتیاز."""
    game = ctx.db.load_game(ctx.chat_id)
    if not game:
        ctx.send("🎮 بازیی در جریان نیست. یکی از پایین شروع کن 👇",
                 kb().row(btn("🎮 دوز تازه", "menu:dooz"),
                          btn("🏠 منوی اصلی", "nav:home")).build())
        return

    board = game["board"] or dooz.new_board()
    level = game["level"] or "hard"
    mode = game["mode"] or "bot"
    result = dooz.win_line(board)
    finished = bool(result) or dooz.is_full(board)
    players = _players(game["players"])

    level_name = dooz.LEVELS.get(level, dooz.LEVELS["hard"])[0]
    title = f"🎮 دوز · {level_name}" if mode == "bot" else "🎮 دوز · دونفره 👥"

    if result:
        status = ("🎉 تو بردی!" if result[0] == dooz.X else
                  ("🤖 من بردم!" if mode == "bot" else "⭕️ بازیکن دوم برد!"))
    elif finished:
        status = "🤝 مساوی شد!"
    elif mode == "bot":
        status = "❌ نوبت تو"
    else:
        who = players.get(game["turn"] + "n", "")
        status = f"❌ نوبت {who}" if game["turn"] == dooz.X else f"⭕️ نوبت {who}"

    score = ctx.db.game_score(ctx.sender_id, "dooz")
    lines = [
        title,
        SEPARATOR,
        dooz.pretty(board, result[1] if result else None),
        f"▫️ {status}",
        f"🏆 {en_to_fa(score['win'])} برد · "
        f"💀 {en_to_fa(score['lose'])} باخت · "
        f"🤝 {en_to_fa(score['draw'])} مساوی",
    ]
    if note:
        lines.append(f"{SEPARATOR}\n{note}")
    lines.append(tip("برای بازی، روی شماره‌ی خانه بزن 🔹"))

    rows = _board_rows(board, finished)
    if finished:
        actions = [btn("🔄 بازی دوباره", "dooz:again"), btn("⚙️ تغییر سطح", "dooz:bot")]
        rows.append(actions)
        rows.append([btn("🎮 منوی دوز", "menu:dooz"), btn("🏠 منوی اصلی", "nav:home")])
    else:
        rows.append([btn("🔄 شروع دوباره", "dooz:again"), btn("🚪 خروج", "dooz:exit")])
        rows.append([btn("🎮 منوی دوز", "menu:dooz"), btn("🏠 منوی اصلی", "nav:home")])

    text = "\n".join(line for line in lines if line is not None)
    if edit:
        ctx.answer(text, _build(rows))
    else:
        ctx.send(text, _build(rows))


def _start_game(ctx: Context, level: str, mode: str = "bot") -> None:
    name = ctx.update.first_name or "بازیکن"
    ctx.db.save_game(
        ctx.chat_id,
        board=dooz.new_board(),
        turn=dooz.X,
        level=level,
        mode=mode,
        players=json.dumps({"x": str(ctx.sender_id), "xn": name}, ensure_ascii=False),
    )
    note = ""
    if mode == "duo":
        note = ("👥 حالت دونفره: نفر اول ❌ و نفر دوم ⭕️\n"
                "هر کس خانه‌ای را لمس کند، نقش او ثابت می‌شود.")
    elif level == "pro":
        note = "👑 سطح حرفه‌ای: شکست‌ناپذیرم؛ مساوی هم بردِ توست 😉"
    _render(ctx, note)


# --------------------------------------------------------------------------- #
# منوها
# --------------------------------------------------------------------------- #
@route(("menu:dooz", "fun:dooz", "game:dooz"))
@command("/dooz", "/دوز")
@guarded("dooz.menu")
def dooz_menu(ctx: Context) -> None:
    enter(ctx, "menu:dooz")
    score = ctx.db.game_score(ctx.sender_id, "dooz")
    ctx.answer(
        header("🎮 دوز (❌⭕️)",
               "یک بازی ساده، سریع و اعتیادآور 😎\n"
               f"{SEPARATOR}\n"
               f"🏆 برد: {en_to_fa(score['win'])} · "
               f"💀 باخت: {en_to_fa(score['lose'])} · "
               f"🤝 مساوی: {en_to_fa(score['draw'])}\n"
               f"{SEPARATOR}\n"
               "▪️ مقابل ربات: چهار سطح هوش 🌱⚡🔥👑\n"
               "▪️ دونفره: در گروه، نوبتی با دوستت 👥"),
        kb().row(btn("🤖 بازی با ربات", "dooz:bot"), btn("👥 دونفره", "dooz:duo"))
             .row(btn("📖 قوانین", "dooz:rules"), btn("🎲 بازی‌های دیگر", "fun:games"))
             .row(btn("🎮 سرگرمی", "menu:fun"), btn("🏠 منوی اصلی", "nav:home"))
             .build(),
    )


@route("dooz:bot")
@guarded("dooz.bot")
def dooz_levels(ctx: Context) -> None:
    enter(ctx, "dooz:bot")
    keyboard = kb()
    keyboard.grid([(f"{name} — {desc}", f"dooz:start:{key}")
                   for key, (name, desc, _) in dooz.LEVELS.items()], per_row=1)
    keyboard.row(btn("🎮 منوی دوز", "menu:dooz"), btn("🏠 منوی اصلی", "nav:home"))
    ctx.answer(header("🤖 انتخاب سطح دشواری",
                      "هرچه بالاتر، باهوش‌تر!\n"
                      f"{SEPARATOR}\n"
                      + tip("سطح «حرفه‌ای» قابل شکست دادن نیست 👑")),
               keyboard.build())


@route("dooz:start", prefix=True)
@guarded("dooz.start")
def dooz_start(ctx: Context) -> None:
    level = (ctx.arg or "hard").strip()
    if level not in dooz.LEVELS:
        level = "hard"
    _start_game(ctx, level, mode="bot")


@route("dooz:duo")
@guarded("dooz.duo")
def dooz_duo(ctx: Context) -> None:
    if ctx.is_private:
        ctx.answer(
            header("👥 بازی دونفره",
                   "دونفره فقط در «گروه» معنا دارد 😊\n"
                   f"{SEPARATOR}\n"
                   "ربات را به یک گروه اضافه کن و دستور زیر را بزن:\n"
                   "‎/dooz‎\n"
                   f"{SEPARATOR}\n"
                   + tip("در پی‌وی می‌توانی مقابل ربات بازی کنی 👇")),
            kb().row(btn("🤖 بازی با ربات", "dooz:bot"))
                 .row(btn("🎮 منوی دوز", "menu:dooz"), btn("🏠 منوی اصلی", "nav:home"))
                 .build(),
        )
        return
    _start_game(ctx, "hard", mode="duo")


# --------------------------------------------------------------------------- #
# حرکت‌ها
# --------------------------------------------------------------------------- #
@route("dooz:p", prefix=True)
@guarded("dooz.play")
def dooz_play(ctx: Context) -> None:
    game = ctx.db.load_game(ctx.chat_id)
    if not game:
        dooz_menu(ctx)
        return

    board = game["board"] or dooz.new_board()
    mode = game["mode"] or "bot"
    level = game["level"] or "hard"
    result = dooz.win_line(board)
    if result or dooz.is_full(board):
        _render(ctx, "🏁 این بازی تمام شده؛ یکی دیگر شروع کن 👇")
        return

    try:
        index = int(ctx.arg)
    except (TypeError, ValueError):
        _render(ctx, "🤔 خانه نامعتبر!")
        return
    if not 0 <= index < 9 or board[index] != dooz.EMPTY:
        ctx.answer("🚧 این خانه پر است! یکی دیگر را انتخاب کن 👇")
        _render(ctx, edit=False)
        return

    players = _players(game["players"])
    mark = game["turn"] or dooz.X
    name = ctx.update.first_name or "بازیکن"

    # در حالت دونفره: نقش‌ها را بر اساس اولین لمس‌ها مشخص می‌کنیم
    if mode == "duo":
        owner = players.get(mark)
        other = dooz.opponent(mark)
        if not owner:
            players[mark] = str(ctx.sender_id)
            players[mark + "n"] = name
        elif str(owner) != str(ctx.sender_id):
            if not players.get(other) and str(players.get(other)) != str(ctx.sender_id):
                players[other] = str(ctx.sender_id)
                players[other + "n"] = name
            else:
                holder = players.get(mark + "n", "حریف")
                ctx.answer(f"⏳ صبر کن؛ نوبت {holder} است 🙂")
                return
        # اگر نوبتِ o است و بازیکن x دوباره زد
        if other in (dooz.X, dooz.O) and players.get(other) and \
                str(players.get(other)) != str(ctx.sender_id):
            pass

    board = dooz.place(board, index, mark)
    result = dooz.win_line(board)

    if not result and not dooz.is_full(board) and mode == "bot":
        move = dooz.bot_move(board, level, ai=dooz.O, human=dooz.X)
        if move >= 0:
            board = dooz.place(board, move, dooz.O)
        result = dooz.win_line(board)

    next_turn = dooz.opponent(mark)
    ctx.db.save_game(ctx.chat_id, board=board, turn=next_turn, level=level,
                     mode=mode, players=json.dumps(players, ensure_ascii=False))

    note = ""
    if result:
        if mode == "bot":
            if result[0] == dooz.X:
                ctx.db.bump_score(ctx.sender_id, "win", "dooz")
                note = "🎉 آفرین! تو بردی 🏆"
            else:
                ctx.db.bump_score(ctx.sender_id, "lose", "dooz")
                note = "🤖 این دست رو من بردم! دوباره؟ 😄"
        else:
            winner = players.get(result[0] + "n", "برنده")
            note = f"🏆 {winner} برنده شد!"
    elif dooz.is_full(board):
        if mode == "bot":
            ctx.db.bump_score(ctx.sender_id, "draw", "dooz")
        note = "🤝 مساوی! تابلو پر شد."

    _render(ctx, note)


@route("dooz:again")
@guarded("dooz.again")
def dooz_again(ctx: Context) -> None:
    game = ctx.db.load_game(ctx.chat_id)
    level = (game or {}).get("level", "hard") or "hard"
    mode = (game or {}).get("mode", "bot") or "bot"
    _start_game(ctx, level, mode)


@route("dooz:exit")
@guarded("dooz.exit")
def dooz_exit(ctx: Context) -> None:
    ctx.db.clear_game(ctx.chat_id)
    score = ctx.db.game_score(ctx.sender_id, "dooz")
    ctx.answer(
        header("🚪 خروج از بازی",
               f"بازی بسته شد.\\n{SEPARATOR}\\n"
               f"🏆 برد: {en_to_fa(score['win'])} · "
               f"💀 باخت: {en_to_fa(score['lose'])} · "
               f"🤝 مساوی: {en_to_fa(score['draw'])}\\n"
               f"{SEPARATOR}\nهر وقت خواستی دوباره بیا 😊"),
        kb().row(btn("🎮 دوز تازه", "dooz:bot"), btn("🎲 بازی‌های دیگر", "fun:games"))
             .row(btn("🎮 سرگرمی", "menu:fun"), btn("🏠 منوی اصلی", "nav:home"))
             .build(),
    )


@route("dooz:rules")
@guarded("dooz.rules")
def dooz_rules(ctx: Context) -> None:
    ctx.answer(
        header("📖 قوانین دوز",
               "▪️ تابلو ۳×۳ است؛ تو ❌ هستی و حریف ⭕️\n"
               "▪️ نوبتی خانه‌ها را پر می‌کنید\n"
               "▪️ اولین نفری که یک ردیف، ستون یا قطر را کامل کند برنده است 🏆\n"
               "▪️ اگر تابلو پر شود و کسی نبرد → مساوی 🤝\n"
               f"{SEPARATOR}\n"
               + tip("در حالت دونفره، ربات را به گروه اضافه کن و /dooz بزن.")),
        kb().row(btn("🤖 شروع بازی", "dooz:bot"), btn("👥 دونفره", "dooz:duo"))
             .row(btn("🎮 منوی دوز", "menu:dooz"), btn("🏠 منوی اصلی", "nav:home"))
             .build(),
    )


@route("dooz:info")
@guarded("dooz.info")
def dooz_info(ctx: Context) -> None:
    ctx.answer("ℹ️ این خانه قبلاً انتخاب شده؛ خانه‌ی خالی دیگری را بزن 👇")
    _render(ctx, edit=False)
