"""用独立于搜索算法的 AST 白名单与 Fraction 复核等式。"""

from __future__ import annotations

import ast
import re
from fractions import Fraction


class InvalidEquation(ValueError):
    """等式不符合当前数字串或规则。"""


_TOKEN = re.compile(r"\d+|[()+\-*/]")
_ALLOWED = re.compile(r"[0-9()+\-*/\s]+\Z")


def _evaluate(node: ast.AST, leading_minus_at: int | None) -> Fraction:
    if isinstance(node, ast.Constant) and type(node.value) is int and node.value >= 0:
        return Fraction(node.value)
    if isinstance(node, ast.UnaryOp):
        if not (
            isinstance(node.op, ast.USub)
            and leading_minus_at == node.col_offset
            and isinstance(node.operand, ast.Constant)
            and type(node.operand.value) is int
        ):
            raise InvalidEquation("一元负号只允许放在本段首个数词前")
        return -_evaluate(node.operand, None)
    if isinstance(node, ast.BinOp):
        left = _evaluate(node.left, leading_minus_at)
        right = _evaluate(node.right, leading_minus_at)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise InvalidEquation("不能除以零")
            return left / right
    raise InvalidEquation("含有不允许的运算")


def value_of(segment: str, mode: str) -> Fraction:
    if not segment or not _ALLOWED.fullmatch(segment):
        raise InvalidEquation("含有非法字符或空等号段")
    tokens = _TOKEN.findall(segment)
    if "".join(tokens) != re.sub(r"\s+", "", segment):
        raise InvalidEquation("表达式中存在无法解析的字符")
    if any(len(token) > 1 and token[0] == "0" for token in tokens if token[0].isdigit()):
        raise InvalidEquation("数词不能带前导零")
    if mode not in {"segment", "strict"}:
        raise InvalidEquation("未知规则")
    # AST 的 col_offset 是字符偏移；此处输入限定为 ASCII 数学符号。
    first_digit = next((i for i, ch in enumerate(segment) if ch.isdigit()), None)
    if first_digit is None:
        raise InvalidEquation("表达式缺少数字")
    prefix = segment[:first_digit].rstrip()
    leading_minus = prefix.rfind("-") if mode == "segment" else -1
    leading_minus_at = leading_minus if leading_minus >= 0 else None
    try:
        tree = ast.parse(segment, mode="eval")
    except SyntaxError as exc:
        raise InvalidEquation("表达式语法错误") from exc
    return _evaluate(tree.body, leading_minus_at)


def verify_equation(number: str, expression: str, mode: str, allow_multiple: bool) -> dict:
    """验证语法、数字重建和等号两侧的精确值。"""
    if not isinstance(expression, str):
        raise InvalidEquation("等式不是文本")
    parts = expression.split("=")
    if len(parts) < 2 or (not allow_multiple and len(parts) != 2):
        raise InvalidEquation("等号数量不符合设置")
    digits = "".join(ch for ch in expression if ch.isdigit())
    if digits != number:
        raise InvalidEquation("等式未完整保留原数字顺序")
    values = [value_of(part, mode) for part in parts]
    if any(value != values[0] for value in values[1:]):
        raise InvalidEquation("等号各段的值不同")
    value = values[0]
    return {
        "expression": expression,
        "common_value": str(value),
        "equals_count": len(parts) - 1,
        "verified": True,
    }
