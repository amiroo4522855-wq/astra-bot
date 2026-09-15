"""بازی «دوز» (❌⭕️): مقابل ربات در چهار سطح، یا دونفره در گروه.

منبعِ واحدِ حقیقت در اینجا «تاریخچه‌ی حرکت‌ها» است؛ تابلو همیشه از
تاریخچه بازسازی می‌شود تا هیچ ناهماهنگی‌ای (هم‌زمانی، دکمه‌ی قدیمی،
برگشت به عقب) پیش نیاید. همه چیز با دکمه انجام می‌شود و هیچ مسیری
بن‌بست ندارد.
"""
from __future__ import annotations

import json
import time

from ..core.context import Context
from ..core.keyboards import btn, kb, main_menu
from ..core.router import command, route
from ..core.utils import SEPARATOR, en_to_fa
from ..services import dooz
from .common import enter, guarded, header, tip

BOARD_PREFIX = "dooz:p"
MAX_IDLE = 3 * 3600            # بازی‌های قدیمی‌تر از ۳ ساعت پاک می‌شوند


# --------------------------------------------------------------------------- #
# ابزارها
# --------------------------------------------------------------------------- #
def _players(raw: str) -> dict:
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}


def _history(raw: str) -> list[int]:
    try:
        items = json.loads(raw or "[]")
        return [int(i) for i in items if isinstance(i, (int, str)) and str(i).isdigit()]
    except json.JSONDecodeError:
        return []


def _state(game: dict) -> tuple[str, list[int], str, str]:
    """برگرداندن (تابلو، تاریخچه، نوبت، مهره‌ی شروع‌کننده)."""
    history = _history(game.get("history"))
    first = dooz.X if str(game.get("first") or "user") in ("user", "x", dooz.X) else dooz.O
    board = dooz.apply_history(dooz.new_board(), history, first)
    return board, history, dooz.turn_of(history, first), first


def _fresh(game: dict | None) -> bool:
    if not game:
        return False
    started = int(game.get("started") or 0)
    return started > time.time() - MAX_IDLE


def _save(ctx: Context, game: dict, **fields) -> None:
    payload = {
        "board": fields.get("board", game.get("board", dooz.new_board())),
        "turn": fields.get("turn", game.get("turn", dooz.X)),
        "level": fields.get("level", game.get("level", "hard")),
        "mode": fields.get("mode", game.get("mode", "bot")),
        "players": fields.get("players", game.get("players", "{}")),
        "history": fields.get("history", game.get("history", "[]")),
        "started": fields.get("started", game.get("started", 0)),
        "first": fields.get("first", game.get("first", "user")),
    }
    ctx.db.save_game(ctx.chat_id, **payload)


def _keyboard(game: dict, board: str, finished: bool, history: list[int],
              mode: str) -> dict:
    """کیبوردِ تابلو + دکمه‌های کنترل."""
    result = dooz.win_line(board)
    rows = dooz.board_keyboard(board, disabled=finished, prefix=BOARD_PREFIX)
    controls: list[dict] = []
    if not finished:
        if mode == "bot":
            if len(history) >= 2:
                controls.append(btn("↩️ برگشت", "dooz:undo"))
            elif len(history) == 1:
                controls.append(btn("↩️ برگشت", "dooz:undo"))
        elif history:
            controls.append(btn("↩️ برگشت", "dooz:undo"))
    controls.append(btn("🔄 دوباره", "dooz:again"))
    rows.append(controls)
    rows.append([btn("🎮 منوی دوز", "menu:dooz"), btn("🏠 منوی اصلی", "nav:home")])
    keyboard = kb()
    keyboard.rows = rows
    return keyboard.build()


def _render(ctx: Context, note: str = "", edit: bool = True) -> None:
    """نمایش تابلو، وضعیت، آمار و زمان."""
    game = ctx.db.load_game(ctx.chat_id)
    if not game or not _fresh(game):
        if game:
            ctx.db.clear_game(ctx.chat_id)
        ctx.send("🎮 بازیی در جریان نیست؛ یکی از پایین شروع کن 👇",
                 kb().row(btn("❌⭕️ دوز تازه", "menu:dooz"),
                          btn("🏠 منوی اصلی", "nav:home")).build())
        return

    board, history, turn, first = _state(game)
    result = dooz.win_line(board)
    finished = bool(result) or dooz.is_full(board)
    mode = game.get("mode") or "bot"
    level = game.get("level") or "hard"
    players = _players(game.get("players"))

    level_name = dooz.LEVELS.get(level, dooz.LEVELS["hard"])[0]
    if mode == "bot":
        title = f"🎮 دوز · {level_name}"
        opener = "🤖 من شروع کردم" if first == dooz.O else "🙋 تو شروع کردی"
    else:
        title = "🎮 دوز · دونفره 👥"
        opener = "👥 نوبتی"

    if result:
        if mode == "bot":
            status = "🎉 تو بردی!" if result[0] == dooz.X else "🤖 من بردم!"
        else:
            winner = players.get(result[0] + "n", "برنده")
            status = f"🏆 {winner} برنده شد!"
    elif finished:
        status = "🤝 مساوی شد!"
    elif mode == "bot":
        status = "❌ نوبت تو"
    else:
        who = players.get(turn + "n", "")
        status = f"{'❌' if turn == dooz.X else '⭕️'} نوبت {who}".strip()

    score = ctx.db.game_score(ctx.sender_id, "dooz")
    played = score["win"] + score["lose"] + score["draw"]
    percent = round(score["win"] * 100 / played) if played else 0
    elapsed = max(0, int(time.time() - int(game.get("started") or 0)))

    lines = [
        f"{title} · {opener}",
        SEPARATOR,
        dooz.pretty(board, result[1] if result else None),
        f"▫️ {status}",
        f"🎯 حرکت {en_to_fa(len(history))} از ۹"
        f" · ⏱ {en_to_fa(elapsed // 60)}:{en_to_fa(elapsed % 60).rjust(2, '۰')}",
        f"🏆 {en_to_fa(score['win'])} برد · 💀 {en_to_fa(score['lose'])} باخت · "
        f"🤝 {en_to_fa(score['draw'])} مساوی"
        + (f" ({en_to_fa(percent)}٪ برد)" if played else ""),
    ]
    if note:
        lines.append(f"{SEPARATOR}\n{note}")
    else:
        lines.append(tip("روی شماره‌ی خانه بزن تا بازی کنی 🔹"))

    text = "\n".join(lines)
    if edit:
        ctx.answer(text, _keyboard(game, board, finished, history, mode))
    else:
        ctx.send(text, _keyboard(game, board, finished, history, mode))


def _start_game(ctx: Context, level: str, mode: str = "bot",
                first: str = "user") -> None:
    name = ctx.update.first_name or "بازیکن"
    players = {"x": str(ctx.sender_id), "xn": name}
    history: list[int] = []
    note = ""

    first_mark = dooz.O if (mode == "bot" and first == "bot") else dooz.X
    if mode == "bot" and first == "bot":
        move = dooz.bot_move(dooz.new_board(), level, ai=dooz.O, human=dooz.X)
        history = [move]
        note = "🤖 من شروع کردم؛ حالا نوبت تو ❌"

    ctx.db.save_game(
        ctx.chat_id,
        board=dooz.apply_history(dooz.new_board(), history, first_mark),
        turn=dooz.turn_of(history, first_mark),
        level=level, mode=mode,
        players=json.dumps(players, ensure_ascii=False),
        history=json.dumps(history),
        started=int(time.time()),
        first=first,
    )
    if mode == "duo":
        note = "👥 دونفره: نفر اول ❌ و نفر دوم ⭕️ — هر کس لمس کند نقشش ثابت می‌شود."
    elif level == "pro" and not note:
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
    played = score["win"] + score["lose"] + score["draw"]
    percent = round(score["win"] * 100 / played) if played else 0
    ctx.answer(
        header("🎮 دوز (❌⭕️)",
               "تابلوی ۳×۳، قوانین ساده، رقابت واقعی 😎\n"
               f"{SEPARATOR}\n"
               f"🏆 {en_to_fa(score['win'])} برد · 💀 {en_to_fa(score['lose'])} باخت · "
               f"🤝 {en_to_fa(score['draw'])} مساوی\n"
               f"📈 نرخ برد: {en_to_fa(percent)}٪\n"
               f"{SEPARATOR}\n"
               "▪️ مقابل ربات: ۴ سطح 🌱⚡🔥👑 و انتخابِ شروع‌کننده\n"
               "▪️ دونفره: در گروه، نوبتی با دوستت 👥\n"
               "▪️ برگشت به حرکت قبل ↩️ و آمار دقیق"),
        kb().row(btn("🤖 بازی با ربات", "dooz:bot"), btn("👥 دونفره", "dooz:duo"))
             .row(btn("📖 قوانین", "dooz:rules"), btn("🎲 بازی‌های دیگر", "fun:games"))
             .row(btn("🎮 سرگرمی", "menu:fun"), btn("🏠 منوی اصلی", "nav:home"))
             .build(),
    )


@route("dooz:bot")
@guarded("dooz.bot")
def dooz_levels(ctx: Context) -> None:
    enter(ctx, "dooz:bot")
    game = ctx.db.load_game(ctx.chat_id)
    first = (game or {}).get("first", "user") or "user"
    keyboard = kb()
    keyboard.grid([(f"{name} — {desc}", f"dooz:start:{key}")
                   for key, (name, desc, _) in dooz.LEVELS.items()], per_row=1)
    keyboard.row(btn(f"🙋 {'✓ ' if first == 'user' else ''}تو شروع کن", "dooz:first:user"),
                 btn(f"🤖 {'✓ ' if first == 'bot' else ''}ربات شروع کنه", "dooz:first:bot"))
    keyboard.row(btn("🎮 منوی دوز", "menu:dooz"), btn("🏠 منوی اصلی", "nav:home"))
    ctx.answer(
        header("🤖 انتخاب سطح و شروع‌کننده",
               "هرچه بالاتر، باهوش‌تر!\n"
               f"{SEPARATOR}\n"
               + tip("سطح «حرفه‌ای» قابل شکست دادن نیست 👑")),
        keyboard.build(),
    )


@route("dooz:first", prefix=True)
@guarded("dooz.first")
def dooz_first(ctx: Context) -> None:
    """انتخابِ شروع‌کننده (تو / ربات)."""
    game = ctx.db.load_game(ctx.chat_id)
    level = (game or {}).get("level", "hard") or "hard"
    first = (ctx.arg or "user").strip()
    ctx.db.save_game(ctx.chat_id, level=level, mode="bot", first=first,
                     history="[]", started=int(time.time()),
                     board=dooz.new_board())
    dooz_levels(ctx)


@route("dooz:start", prefix=True)
@guarded("dooz.start")
def dooz_start(ctx: Context) -> None:
    level = (ctx.arg or "hard").strip()
    if level not in dooz.LEVELS:
        level = "hard"
    game = ctx.db.load_game(ctx.chat_id)
    first = (game or {}).get("first", "user") or "user"
    _start_game(ctx, level, mode="bot", first=first)


@route("dooz:duo")
@guarded("dooz.duo")
def dooz_duo(ctx: Context) -> None:
    if ctx.is_private:
        ctx.answer(
            header("👥 بازی دونفره",
                   "دونفره فقط در «گروه» معنا دارد 😊\n"
                   f"{SEPARATOR}\n"
                   "ربات را به گروه اضافه کن و ‎/dooz‎ را بزن.\n"
                   f"{SEPARATOR}\n"
                   + tip("در پی‌وی می‌توانی مقابل ربات بازی کنی 👇")),
            kb().row(btn("🤖 بازی با ربات", "dooz:bot"))
                 .row(btn("🎮 منوی دوز", "menu:dooz"), btn("🏠 منوی اصلی", "nav:home"))
                 .build(),
        )
        return
    _start_game(ctx, "hard", mode="duo", first="user")


# --------------------------------------------------------------------------- #
# حرکت‌ها
# --------------------------------------------------------------------------- #
@route("dooz:p", prefix=True)
@guarded("dooz.play")
def dooz_play(ctx: Context) -> None:
    game = ctx.db.load_game(ctx.chat_id)
    if not game or not _fresh(game):
        dooz_menu(ctx)
        return

    board, history, turn, first = _state(game)
    mode = game.get("mode") or "bot"
    level = game.get("level") or "hard"
    players = _players(game.get("players"))
    name = ctx.update.first_name or "بازیکن"

    if dooz.win_line(board) or dooz.is_full(board):
        _render(ctx, "🏁 این بازی تمام شده؛ یکی دیگر شروع کن 👇")
        return

    try:
        index = int(ctx.arg)
    except (TypeError, ValueError):
        _render(ctx, "🤔 خانه نامعتبر!")
        return
    if not 0 <= index < 9:
        _render(ctx, "🤔 خانه نامعتبر!")
        return
    if board[index] != dooz.EMPTY:
        ctx.answer("🚧 این خانه پر است؛ خانه‌ی خالی دیگری را بزن 👇")
        _render(ctx, edit=False)
        return

    # در حالت دونفره: نوبت را به بازیکن اختصاص می‌دهیم
    if mode == "duo":
        owner = players.get(turn)
        other = dooz.opponent(turn)
        if not owner:
            players[turn] = str(ctx.sender_id)
            players[turn + "n"] = name
        elif str(owner) != str(ctx.sender_id):
            if not players.get(other):
                players[other] = str(ctx.sender_id)
                players[other + "n"] = name
            else:
                ctx.answer(f"⏳ صبر کن؛ نوبت {players.get(turn + 'n', 'حریف')} است 🙂")
                return

    history = history + [index]
    board = dooz.apply_history(dooz.new_board(), history, first)
    result = dooz.win_line(board)

    if not result and not dooz.is_full(board) and mode == "bot":
        move = dooz.bot_move(board, level, ai=dooz.O, human=dooz.X)
        if move >= 0:
            history = history + [move]
            board = dooz.apply_history(dooz.new_board(), history, first)
        result = dooz.win_line(board)

    _save(ctx, game, board=board, turn=dooz.turn_of(history, first),
          players=json.dumps(players, ensure_ascii=False),
          history=json.dumps(history))

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
            note = f"🏆 {players.get(result[0] + 'n', 'برنده')} برنده شد!"
    elif dooz.is_full(board):
        if mode == "bot":
            ctx.db.bump_score(ctx.sender_id, "draw", "dooz")
        note = "🤝 مساوی! تابلو پر شد."

    _render(ctx, note)


@route("dooz:undo")
@guarded("dooz.undo")
def dooz_undo(ctx: Context) -> None:
    game = ctx.db.load_game(ctx.chat_id)
    if not game or not _fresh(game):
        dooz_menu(ctx)
        return
    _, history, _, first = _state(game)
    mode = game.get("mode") or "bot"
    if not history:
        _render(ctx, "↩️ هنوز حرکتی انجام نشده!")
        return
    if dooz.win_line(dooz.apply_history(dooz.new_board(), history, first)):
        _render(ctx, "🏁 بازی تمام شده؛ امکان برگشت نیست.")
        return

    count = 2 if (mode == "bot" and len(history) >= 2) else 1
    history = dooz.pop_moves(history, count)
    board = dooz.apply_history(dooz.new_board(), history, first)
    _save(ctx, game, board=board, turn=dooz.turn_of(history, first),
          history=json.dumps(history))
    _render(ctx, "↩️ یک حرکت برگشت داده شد.")


@route("dooz:again")
@guarded("dooz.again")
def dooz_again(ctx: Context) -> None:
    game = ctx.db.load_game(ctx.chat_id)
    level = (game or {}).get("level", "hard") or "hard"
    mode = (game or {}).get("mode", "bot") or "bot"
    first = (game or {}).get("first", "user") or "user"
    _start_game(ctx, level, mode, first)


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
               "▪️ تابلو ۳×۳ است؛ تو ❌ و حریف ⭕️\n"
               "▪️ نوبتی خانه‌ها را پر می‌کنید\n"
               "▪️ اولین کسی که یک ردیف، ستون یا قطر را کامل کند برنده است 🏆\n"
               "▪️ اگر تابلو پر شود و کسی نبرد → مساوی 🤝\n"
               "▪️ با «↩️ برگشت» می‌توانی حرکت قبلی را پس بگیری\n"
               "▪️ می‌توانی انتخاب کنی ربات بازی را شروع کند 🤖\n"
               f"{SEPARATOR}\n"
               + tip("در گروه با /dooz می‌توانی دونفره بازی کنی 👥")),
        kb().row(btn("🤖 شروع بازی", "dooz:bot"), btn("👥 دونفره", "dooz:duo"))
             .row(btn("🎮 منوی دوز", "menu:dooz"), btn("🏠 منوی اصلی", "nav:home"))
             .build(),
    )


@route("dooz:info")
@guarded("dooz.info")
def dooz_info(ctx: Context) -> None:
    ctx.answer("ℹ️ این خانه قبلاً انتخاب شده؛ خانه‌ی خالی دیگری را بزن 👇")
    _render(ctx, edit=False)
