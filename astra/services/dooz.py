"""منطق بازی «دوز» (X/O).

هم بازی با ربات (۴ سطح هوش) و هم حالت دونفره پشتیبانی می‌شود.
هوش ربات در سطح «حرفه‌ای» شکست‌ناپذیر است (جستجوی کامل با آلفا-بتا).
"""
from __future__ import annotations

import random
from functools import lru_cache

EMPTY = "-"
X, O = "x", "o"

WIN_LINES: tuple[tuple[int, int, int], ...] = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),      # سطرها
    (0, 3, 6), (1, 4, 7), (2, 5, 8),      # ستون‌ها
    (0, 4, 8), (2, 4, 6),                 # قطرها
)

LEVELS: dict[str, tuple[str, float, str]] = {
    # کلید: (نام فارسی، احتمال حرکتِ هوشمند، توضیح)
    "easy":   ("آسان 🌱",    0.20, "گاهی اشتباه می‌کنم"),
    "medium": ("متوسط ⚡",   0.60, "نیمی از وقت‌ها جدی‌ام"),
    "hard":   ("سخت 🔥",     0.90, "کم پیش میاد ببازی"),
    "pro":    ("حرفه‌ای 👑", 1.00, "شکست‌ناپذیر!"),
}

SYMBOLS = {X: "❌", O: "⭕️", EMPTY: "🔹"}
FA_DIGITS = "۱۲۳۴۵۶۷۸۹"


# --------------------------------------------------------------------------- #
# ابزارهای پایه
# --------------------------------------------------------------------------- #
def new_board() -> str:
    """تابلوی خالی ۳×۳."""
    return EMPTY * 9


def cells(board: str) -> list[str]:
    return list((board or EMPTY * 9).ljust(9, EMPTY)[:9])


def free_cells(board: str) -> list[int]:
    return [i for i, cell in enumerate(cells(board)) if cell == EMPTY]


def place(board: str, index: int, mark: str) -> str:
    """قرار دادن مهره و برگرداندن تابلوی جدید."""
    items = cells(board)
    if 0 <= index < 9 and items[index] == EMPTY:
        items[index] = mark
    return "".join(items)


def win_line(board: str) -> tuple[str, tuple[int, int, int]] | None:
    """برنده و خط برنده (اگر وجود داشته باشد)."""
    items = cells(board)
    for line in WIN_LINES:
        a, b, c = line
        if items[a] != EMPTY and items[a] == items[b] == items[c]:
            return items[a], line
    return None


def is_full(board: str) -> bool:
    return EMPTY not in cells(board)


def opponent(mark: str) -> str:
    return O if mark == X else X


# --------------------------------------------------------------------------- #
# هوش مصنوعی
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=60_000)
def _score(board: str, ai: str, turn: str, depth: int) -> int:
    """امتیاز تابلو از دید ‎ai‎ (مثبت = به نفع ai)."""
    result = win_line(board)
    if result:
        return 10 - depth if result[0] == ai else depth - 10
    if is_full(board):
        return 0

    human = opponent(ai)
    best = -99 if turn == ai else 99
    for index in [i for i, cell in enumerate(board) if cell == EMPTY]:
        value = _score(board[:index] + turn + board[index + 1:],
                       ai, opponent(turn), depth + 1)
        best = max(best, value) if turn == ai else min(best, value)
    return best


def best_move(board: str, ai: str = O, human: str = X) -> int:
    """بهترین حرکت ممکن (کاملاً بهینه)."""
    empty = [i for i, cell in enumerate(cells(board)) if cell == EMPTY]
    if not empty:
        return -1
    # اگر بتواند همان لحظه ببرد
    for index in empty:
        if win_line(place(board, index, ai)):
            return index
    # اگر حریف در حرکت بعد ببرد، باید بست
    for index in empty:
        if win_line(place(board, index, human)):
            return index

    best_index, best_value = empty[0], -99
    for index in empty:
        value = _score(place(board, index, ai), ai, human, 0)
        if value > best_value:
            best_index, best_value = index, value
    return best_index


def bot_move(board: str, level: str = "hard", ai: str = O, human: str = X) -> int:
    """انتخاب حرکت با توجه به سطح دشواری."""
    empty = free_cells(board)
    if not empty:
        return -1
    smart_chance = LEVELS.get(level, LEVELS["hard"])[1]
    if smart_chance >= 1.0:
        return best_move(board, ai, human)
    if random.random() < smart_chance:
        # نیمه‌هوشمند: بُرد یا بستِ فوری را می‌بیند، ولی همیشه بهینه نیست
        for index in empty:
            if win_line(place(board, index, ai)):
                return index
        if random.random() < 0.6:
            for index in empty:
                if win_line(place(board, index, human)):
                    return index
        return random.choice(empty)
    return random.choice(empty)


# --------------------------------------------------------------------------- #
# نمایش
# --------------------------------------------------------------------------- #
def pretty(board: str, highlight: tuple[int, int, int] | None = None) -> str:
    """نمایش متنیِ زیبا از تابلو (برای پیام‌ها)."""
    items = cells(board)
    rows = []
    for row in range(3):
        parts = []
        for col in range(3):
            index = row * 3 + col
            cell = items[index]
            if highlight and index in highlight and cell != EMPTY:
                parts.append("✨")
            elif cell == X:
                parts.append("❌")
            elif cell == O:
                parts.append("⭕️")
            else:
                parts.append(FA_DIGITS[index])
        rows.append("  ".join(parts))
    return "\n" + "\n".join(rows) + "\n"


def board_keyboard(board: str, disabled: bool = False,
                   prefix: str = "dooz:p") -> list[list[dict]]:
    """سه ردیف دکمه‌ی شیشه‌ای برای تابلو."""
    from ..core.keyboards import btn

    items = cells(board)
    rows: list[list[dict]] = []
    for row in range(3):
        line = []
        for col in range(3):
            index = row * 3 + col
            cell = items[index]
            if cell == X:
                label = "❌"
            elif cell == O:
                label = "⭕️"
            else:
                label = FA_DIGITS[index]
            line.append(btn(label, f"{prefix}:{index}" if not disabled else "dooz:info"))
        rows.append(line)
    return rows


def status_text(board: str, level: str = "hard") -> str:
    """یک خط وضعیتِ کوتاه برای بالای پیام."""
    result = win_line(board)
    if result:
        return "🎉 برنده شدی!" if result[0] == X else "🤖 من بردم!"
    if is_full(board):
        return "🤝 مساوی شد!"
    return "نوبت تو ❌"
