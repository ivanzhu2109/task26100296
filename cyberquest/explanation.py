"""分析解释的数据结构，以及供调用方独立复算总成本的校验函数。"""
from __future__ import annotations

from dataclasses import dataclass
from math import factorial

from .wordlist import LEET_MAP

BRUTE_ALPHABET_SIZE = 95  # ASCII 32..126


class ExplanationError(ValueError):
    """解释内容不自洽或无法复算出所声明的成本。"""


@dataclass(frozen=True)
class Substitution:
    """一次数字 -> 字母替换。position 是完成小写化与可选反转后的串内下标。"""

    position: int
    digit: str
    letter: str


@dataclass
class SegmentExplanation:
    """一个连续片段的计费解释。start/end 为所属字符串内的偏移（end 开区间）。"""

    start: int
    end: int
    text: str
    method: str  # "brute" | "dictionary" | "repeat"
    cost: int
    # method == "dictionary"
    word: str | None = None
    rank: int | None = None
    substitutions: tuple[Substitution, ...] = ()
    reversed: bool = False
    uppercase_count: int = 0
    exponent: int = 0
    # method == "repeat"
    repeat_count: int | None = None
    unit: str | None = None
    unit_explanation: "PasswordExplanation | None" = None


@dataclass
class PasswordExplanation:
    """一次完整分析：把 text 拆成连续不重叠的非空片段。"""

    text: str
    segments: tuple[SegmentExplanation, ...]
    segment_count: int
    factorial_multiplier: int
    total_cost: int


def _fail(message: str) -> None:
    raise ExplanationError(message)


def _verify_password(explanation: PasswordExplanation, wordlist) -> int:
    text = explanation.text
    if explanation.segment_count != len(explanation.segments):
        _fail("segment_count 与片段列表长度不一致")
    if explanation.factorial_multiplier != factorial(explanation.segment_count):
        _fail("factorial_multiplier 不等于片段数的阶乘")
    position = 0
    product = 1
    for segment in explanation.segments:
        if segment.start != position:
            _fail(f"片段未连续覆盖：期望起点 {position}，实际 {segment.start}")
        if segment.end <= segment.start or segment.end > len(text):
            _fail(f"片段区间非法：[{segment.start}, {segment.end})")
        if text[segment.start : segment.end] != segment.text:
            _fail(f"片段文本与原文不符：[{segment.start}, {segment.end})")
        product *= _verify_segment(segment, wordlist)
        position = segment.end
    if position != len(text):
        _fail("片段未覆盖全部字符")
    total = explanation.factorial_multiplier * product
    if total != explanation.total_cost:
        _fail(f"复算总成本 {total} 与声明的 {explanation.total_cost} 不一致")
    return total


def _verify_segment(segment: SegmentExplanation, wordlist) -> int:
    text = segment.text
    if segment.method == "brute":
        cost = BRUTE_ALPHABET_SIZE ** len(text)
    elif segment.method == "dictionary":
        cost = _verify_dictionary(segment, wordlist)
    elif segment.method == "repeat":
        cost = _verify_repeat(segment, wordlist)
    else:
        _fail(f"未知计费方式：{segment.method!r}")
    if cost != segment.cost:
        _fail(f"片段 {text!r} 复算成本 {cost} 与声明的 {segment.cost} 不一致")
    return cost


def _verify_dictionary(segment: SegmentExplanation, wordlist) -> int:
    if segment.word is None or segment.rank is None:
        _fail("词库匹配缺少 word 或 rank")
    try:
        rank = wordlist.rank_of(segment.word)
    except KeyError:
        _fail(f"单词 {segment.word!r} 不在词库中")
    if rank != segment.rank:
        _fail(f"单词 {segment.word!r} 排名应为 {rank}，声明为 {segment.rank}")
    transformed = segment.text.lower()
    if segment.reversed:
        transformed = transformed[::-1]
    if len(transformed) != len(segment.word):
        _fail("变换后的长度与单词不一致")
    substitutions: list[Substitution] = []
    for position, (have, want) in enumerate(zip(transformed, segment.word)):
        if have == want:
            continue
        targets = LEET_MAP.get(have)
        if targets is None or want not in targets:
            _fail(f"位置 {position}：{have!r} 无法替换为 {want!r}")
        substitutions.append(Substitution(position, have, want))
    if tuple(substitutions) != tuple(segment.substitutions):
        _fail("替换清单与实际变换不符")
    uppercase = sum(1 for ch in segment.text if "A" <= ch <= "Z")
    if uppercase != segment.uppercase_count:
        _fail("大写字母数不符")
    exponent = uppercase + len(substitutions) + (1 if segment.reversed else 0)
    if exponent != segment.exponent:
        _fail("指数不符")
    return rank * (1 << exponent)


def _verify_repeat(segment: SegmentExplanation, wordlist) -> int:
    k = segment.repeat_count
    unit = segment.unit
    if k is None or k < 2 or not unit:
        _fail("重复结构需要非空单元且重复次数至少为 2")
    if unit * k != segment.text:
        _fail("片段不是单元连续重复 k 次")
    inner = segment.unit_explanation
    if inner is None or inner.text != unit:
        _fail("缺少重复单元的内部分析")
    return k * _verify_password(inner, wordlist)


def verify_explanation(explanation: PasswordExplanation, wordlist) -> int:
    """独立复算解释的总成本；不自洽时抛出 ExplanationError。"""
    return _verify_password(explanation, wordlist)
