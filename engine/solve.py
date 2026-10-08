"""平衡化判定、构造和多见证搜索。

上游数据负责已发布的有限分类；这里新生成的每条方案由 verify.py 独立复核。
搜索有资源上限时只报告“尚未完成”，绝不据此报告“无解”。
"""

from __future__ import annotations

import ast
import importlib.util
from collections import defaultdict
from fractions import Fraction
from functools import lru_cache
from typing import Callable

from .data import published, ROOT
from .verify import InvalidEquation, verify_equation

MAX_VALUES_PER_PART = 150_000


class SearchLimit(Exception):
    """值集达到保护上限；不能据此判定无解。"""

_core_spec = importlib.util.spec_from_file_location("sst_core", ROOT / "vendor/upstream/sst_core.py")
assert _core_spec and _core_spec.loader
_core = importlib.util.module_from_spec(_core_spec)
import sys
sys.modules[_core_spec.name] = _core
_core_spec.loader.exec_module(_core)


def validate_number(number: object) -> str:
    if not isinstance(number, str):
        raise ValueError("请输入十进制整数")
    number = number.strip()
    if not number or len(number) > 256 or not number.isascii() or not number.isdecimal():
        raise ValueError("请输入不超过 256 位的非负十进制整数")
    if len(number) > 1 and number[0] == "0":
        raise ValueError("多位数不能以 0 开头")
    return number


def known_existence(number: str, mode: str, allow_multiple: bool) -> tuple[str, str]:
    """返回存在性与来源；strict 的多等号弱串保留未知状态。"""
    if len(number) < 2:
        return "no", "至少需要两个数字才能形成等式"
    data = published()
    if number in data.non_single:
        if not allow_multiple:
            return "no", "上游单等号反例表"
        if number in data.strong:
            return "no", "上游完全无解表"
        if mode == "segment":
            return "yes", "上游多等号分类表"
        return "unknown", "严格规则需重新搜索多等号方案"
    if len(number) <= 7:
        return "yes", "上游完整单等号反例表"
    return "yes", "依据上游平衡化定理"


@lru_cache(maxsize=4096)
def _zero_exprs(s: str) -> tuple[str, ...]:
    """为短素可归零串生成多种严格规则见证，只计算短子串值映射。"""
    if s == "0":
        return ("0",)
    found: list[str] = []
    for i in sorted(range(1, len(s)), key=lambda pos: abs(pos - len(s) / 2)):
        left = _core._strict_expr_map(s[:i])
        right = _core._strict_expr_map(s[i:])
        for a, (a_expr, _) in left.items():
            if a in right:
                expression = f"({a_expr})-({right[a][0]})"
                if _core.eval_fraction(expression) == 0 and expression not in found:
                    found.append(expression)
            if -a in right:
                expression = f"({a_expr})+({right[-a][0]})"
                if _core.eval_fraction(expression) == 0 and expression not in found:
                    found.append(expression)
            if len(found) >= 4:
                return tuple(found)
        if 0 in left:
            found.append(f"({left[Fraction(0)][0]})*({next(iter(right.values()))[0]})")
        if 0 in right:
            found.append(f"({next(iter(left.values()))[0]})*({right[Fraction(0)][0]})")
        if len(found) >= 4:
            return tuple(found[:4])
    return tuple(found)


def _zero_sides(side: str, limit: int = 5) -> list[str]:
    """找多种素可归零子串与见证，并让其余数字作为乘法因子。"""
    primes = published().prime_zeroable
    found: list[str] = []
    for size in range(1, min(7, len(side)) + 1):
        for i in range(len(side) - size + 1):
            sub = side[i:i + size]
            if sub not in primes:
                continue
            for middle in _zero_exprs(sub):
                # 单个数字因子避免剩余部分出现非法先导零；所有数字恰好保留一次。
                factors = [*side[:i], f"({middle})", *side[i + size:]]
                candidate = "*".join(factors)
                if candidate not in found:
                    found.append(candidate)
                if len(found) >= limit:
                    return found
    return found


def _split_order(length: int):
    return sorted(range(1, length), key=lambda i: (abs(2 * i - length), i))


def _canonical(expression: str) -> str:
    # 去除空白与冗余的外围括号；更复杂的结构差异由原表达式保留。
    return "".join(expression.split())


def _readable(expression: str) -> str:
    """仅删去多余括号；数字完整性仍交给独立验证器检查。"""
    try:
        return "=".join(ast.unparse(ast.parse(part, mode="eval").body)
                        for part in expression.split("="))
    except SyntaxError:
        return expression


def _score(expression: str) -> tuple[int, int, int]:
    operations = sum(expression.count(op) for op in "+-*/")
    return (operations, expression.count("("), len(expression))


def _search_maps(s: str, mode: str, max_per_value: int = 3):
    """短串值表：每个值保留多个表达式，但保留完整可达值集合。"""
    @lru_cache(maxsize=None)
    def build(part: str):
        result: dict[Fraction, list[str]] = defaultdict(list)
        if len(part) == 1 or part[0] != "0":
            n = Fraction(int(part))
            result[n].append(part)
            if mode == "segment" and n != 0:
                result[-n].append("-" + part)
        for i in range(1, len(part)):
            left = build(part[:i])
            # 段首负号仅能出现在整个表达式的最左数词。
            right = build(part[i:]) if mode == "strict" else strict_build(part[i:])
            for a, a_exprs in left.items():
                for b, b_exprs in right.items():
                    operations = [(a + b, "+"), (a - b, "-"), (a * b, "*")]
                    if b:
                        operations.append((a / b, "/"))
                    for value, operator in operations:
                        bucket = result[value]
                        if len(result) > MAX_VALUES_PER_PART:
                            raise SearchLimit
                        if len(bucket) >= max_per_value:
                            continue
                        for ae in a_exprs:
                            for be in b_exprs:
                                candidate = f"({ae}){operator}({be})"
                                if candidate not in bucket:
                                    bucket.append(candidate)
                                if len(bucket) >= max_per_value:
                                    break
                            if len(bucket) >= max_per_value:
                                break
        return result

    @lru_cache(maxsize=None)
    def strict_build(part: str):
        # 这一支禁止在非首数词出现一元负号。
        result: dict[Fraction, list[str]] = defaultdict(list)
        if len(part) == 1 or part[0] != "0":
            result[Fraction(int(part))].append(part)
        for i in range(1, len(part)):
            for a, aes in strict_build(part[:i]).items():
                for b, bes in strict_build(part[i:]).items():
                    operations = [(a + b, "+"), (a - b, "-"), (a * b, "*")]
                    if b:
                        operations.append((a / b, "/"))
                    for value, op in operations:
                        bucket = result[value]
                        if len(result) > MAX_VALUES_PER_PART:
                            raise SearchLimit
                        if len(bucket) >= max_per_value:
                            continue
                        for ae in aes:
                            for be in bes:
                                candidate = f"({ae}){op}({be})"
                                if candidate not in bucket:
                                    bucket.append(candidate)
                                if len(bucket) >= max_per_value:
                                    break
                            if len(bucket) >= max_per_value:
                                break
        return result

    return build


def _generate(number: str, mode: str, allow_multiple: bool, target: int,
              emit: Callable[[dict], None]) -> str:
    """逐条发送已验证方案，返回搜索结束原因。

    调用者应置于可终止的独立进程中；8–15 位困难串可能耗时较久。
    """
    found: set[str] = set()

    def add(expression: str) -> bool:
        expression = _readable(expression)
        key = _canonical(expression)
        if key in found:
            return False
        try:
            record = verify_equation(number, expression, mode, allow_multiple)
        except InvalidEquation:
            return False
        # 单字数段的整体取负只是同一条等式的镜像，不计为新增方案。
        if all(part.startswith("-") and part[1:].isdigit() for part in expression.split("=")):
            positive = "=".join(part[1:] for part in expression.split("="))
            if _canonical(positive) in found:
                return False
        found.add(key)
        emit(record)
        return len(found) >= target

    if len(number) < 2:
        return "complete"
    data = published()
    if allow_multiple and mode == "segment" and number in data.weak:
        witness = data.classification[number]
        if witness and add(witness):
            return "target"
    if number in data.strong or number in data.non_single and not allow_multiple:
        return "complete"

    # 短串先枚举简洁的普通等式。长串先走归零构造，以便及时显示首条见证。
    if len(number) <= 7:
        maps = _search_maps(number, mode)
        candidates = []
        for i in _split_order(len(number)):
            left, right = maps(number[:i]), maps(number[i:])
            for value in left.keys() & right.keys():
                for ae in left[value]:
                    for be in right[value]:
                        candidates.append(_readable(f"{ae}={be}"))
        for candidate in sorted(set(candidates), key=_score):
            if add(candidate):
                return "target"

    # 构造性 0=0 只需要很短的归零子串，不枚举整个长串的值集。
    if len(number) >= 8 or len(found) < target:
        for i in _split_order(len(number)):
            if len(number) >= 16 and (i < 8 or len(number) - i < 8):
                continue
            lefts = _zero_sides(number[:i])
            rights = _zero_sides(number[i:])
            # 轮流改变左右构造，让前几条方案展示不同的写法。
            pairs = sorted(((a, b) for a in range(len(lefts)) for b in range(len(rights))),
                           key=lambda pair: (pair[0] + pair[1], pair[0]))
            for a, b in pairs:
                left, right = lefts[a], rights[b]
                if add(f"{left}={right}"):
                    return "target"
    if len(number) >= 16:
        return "complete" if found else "incomplete"

    # 8–15 位继续精确二分搜索；这个阶段可由外层进程时限中止。
    if len(number) >= 8:
        maps = _search_maps(number, mode, 2)
        for i in _split_order(len(number)):
            if max(i, len(number) - i) > 8:
                continue
            left, right = maps(number[:i]), maps(number[i:])
            for value in left.keys() & right.keys():
                for ae in left[value]:
                    for be in right[value]:
                        if add(f"{ae}={be}"):
                            return "target"

    if allow_multiple and len(number) <= 7:
        # 精确枚举每个切分；前面建的每个可达值仍完整保留。
        for mask in range(1, 1 << (len(number) - 1)):
            cuts = [0, *[i for i in range(1, len(number)) if mask & (1 << (i - 1))], len(number)]
            if len(cuts) <= 3:
                continue
            segments = [number[cuts[j]:cuts[j + 1]] for j in range(len(cuts) - 1)]
            segment_maps = [maps(segment) for segment in segments]
            shared = set(segment_maps[0])
            for item in segment_maps[1:]:
                shared.intersection_update(item)
            for value in shared:
                expression = "=".join(item[value][0] for item in segment_maps)
                if add(expression):
                    return "target"

    # 完整证明无解只对短串与当前规则、当前等号设置成立。
    return "complete" if len(number) <= 7 else "incomplete"


def generate(number: str, mode: str, allow_multiple: bool, target: int,
             emit: Callable[[dict], None]) -> str:
    try:
        return _generate(number, mode, allow_multiple, target, emit)
    except SearchLimit:
        return "incomplete"
