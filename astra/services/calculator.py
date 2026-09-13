"""ماشین‌حساب امن (بدون استفاده از eval)."""
from __future__ import annotations

import ast
import math
import operator as op

from ..core.utils import en_to_fa, fa_to_en

# عملگرهای مجاز
_OPERATORS = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
    ast.FloorDiv: op.floordiv, ast.Mod: op.mod, ast.Pow: op.pow,
    ast.USub: op.neg, ast.UAdd: op.pos,
}

_FUNCTIONS = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log10, "ln": math.log, "abs": abs, "round": round,
    "factorial": math.factorial, "radians": math.radians, "degrees": math.degrees,
    "ceil": math.ceil, "floor": math.floor,
}

CONSTANTS = {"pi": math.pi, "e": math.e, "π": math.pi}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        name = node.func.id
        if name in _FUNCTIONS and not node.keywords:
            args = [_eval_node(a) for a in node.args]
            return float(_FUNCTIONS[name](*args))
        raise ValueError(f"تابع {name} مجاز نیست")
    if isinstance(node, ast.Name) and node.id in CONSTANTS:
        return CONSTANTS[node.id]
    raise ValueError("عبارت ریاضی نامعتبر است")


def calculate(expression: str) -> float:
    """محاسبه‌ی یک عبارت ریاضی ساده و امن."""
    text = fa_to_en(expression)
    text = text.replace("×", "*").replace("÷", "/").replace("^", "**")
    text = text.replace("٪", "/100")
    tree = ast.parse(text, mode="eval")
    return _eval_node(tree.body)


def format_result(value: float) -> str:
    if value == int(value) and abs(value) < 1e15:
        return en_to_fa(int(value))
    return en_to_fa(round(value, 6))


def render(expression: str) -> str:
    result = calculate(expression)
    return (
        "🧮 ماشین‌حساب آسترا\n"
        "───────────────\n"
        f"📥 عبارت: {en_to_fa(expression)}\n"
        f"📤 پاسخ: {format_result(result)} ✅"
    )
