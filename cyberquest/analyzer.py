"""口令分析器：在所有合法拆分方案上求最小猜测成本。"""
from __future__ import annotations

from math import factorial

from .explanation import (
    BRUTE_ALPHABET_SIZE,
    PasswordExplanation,
    SegmentExplanation,
    Substitution,
)
from .wordlist import MAX_WORD_LENGTH, Wordlist, load_wordlist

MAX_PASSWORD_LENGTH = 128
PRINTABLE_MIN = 32
PRINTABLE_MAX = 126

# 阶乘（片段数惩罚）与 95 的幂（暴力猜测成本）预算表
_FACTORIALS = [factorial(i) for i in range(MAX_PASSWORD_LENGTH + 1)]
_POW95 = [BRUTE_ALPHABET_SIZE ** i for i in range(MAX_PASSWORD_LENGTH + 1)]

# 每个长度的真因子（用于重复结构：单元长度 d，重复次数 k = length / d >= 2）
_PROPER_DIVISORS = [
    tuple(d for d in range(1, length) if length % d == 0)
    for length in range(MAX_PASSWORD_LENGTH + 1)
]


class PasswordAnalyzer:
    """加载词库后反复使用；分析状态仅保存在内存中。"""

    def __init__(self, wordlist: Wordlist) -> None:
        self._wordlist = wordlist
        # 重复单元（及已分析过的串）-> 其最优解释，跨调用共享
        self._memo: dict[str, PasswordExplanation] = {}

    @classmethod
    def from_file(cls, path: str) -> "PasswordAnalyzer":
        return cls(load_wordlist(path))

    def analyze(self, password: str) -> PasswordExplanation:
        """返回最小成本方案的解释；total_cost 即最小成本。"""
        if not isinstance(password, str) or not 1 <= len(password) <= MAX_PASSWORD_LENGTH:
            raise ValueError(f"口令长度须为 1..{MAX_PASSWORD_LENGTH}")
        for ch in password:
            code = ord(ch)
            if code < PRINTABLE_MIN or code > PRINTABLE_MAX:
                raise ValueError(f"口令含非法字符（ASCII {code}）")
        return self._analyze(password)

    # ---- 内部实现 ----

    def _analyze(self, text: str) -> PasswordExplanation:
        cached = self._memo.get(text)
        if cached is not None:
            return cached
        n = len(text)
        segment_table = self._build_segment_table(text, n)
        explanation = self._dynamic_program(text, n, segment_table)
        self._memo[text] = explanation
        return explanation

    def _build_segment_table(self, text: str, n: int) -> list[list[tuple]]:
        """seg[j][i] = (cost, kind, payload)，即片段 text[j:i] 的最优计费。"""
        seg: list[list[tuple | None]] = [
            [None] * (n + 1) for _ in range(n + 1)
        ]
        for length in range(1, n + 1):
            brute = _POW95[length]
            divisors = _PROPER_DIVISORS[length]
            for j in range(0, n - length + 1):
                i = j + length
                piece = text[j:i]
                best_cost = brute
                best_kind = "brute"
                best_payload = None
                if length <= MAX_WORD_LENGTH:
                    found = self._dictionary_best(piece, best_cost)
                    if found is not None:
                        best_cost = found[0]
                        best_kind = "dictionary"
                        best_payload = found[1]
                for unit_len in divisors:
                    k = length // unit_len
                    unit = text[j : j + unit_len]
                    if unit * k == piece:
                        candidate = k * self._analyze(unit).total_cost
                        if candidate < best_cost:
                            best_cost = candidate
                            best_kind = "repeat"
                            best_payload = (k, unit)
                seg[j][i] = (best_cost, best_kind, best_payload)
        return seg

    def _dictionary_best(self, piece: str, limit: int):
        """片段按词库匹配计费的最优候选；成本须严格小于 limit。"""
        lower = piece.lower()
        uppercase = sum(1 for ch in piece if "A" <= ch <= "Z")
        best = None
        for reversed_flag in (False, True):
            transformed = lower[::-1] if reversed_flag else lower
            shift = uppercase + (1 if reversed_flag else 0)
            # 只可能接受 rank * 2**subs * 2**shift < limit 的匹配
            sub_limit = -(-limit >> shift)  # ceil(limit / 2**shift)
            matched = self._wordlist.best_match(transformed, sub_limit)
            if matched is None:
                continue
            rank, word, substitutions = matched
            cost = rank << (shift + substitutions)
            if cost < limit and (best is None or cost < best[0]):
                best = (cost, (word, rank, substitutions, reversed_flag))
                limit = cost
        return best

    def _dynamic_program(
        self, text: str, n: int, seg: list[list[tuple]]
    ) -> PasswordExplanation:
        """dp[i] 为前缀 text[:i] 的帕累托最优 (片段数, 片段成本积, 回溯指针) 列表。"""
        cap = _POW95[n]  # 任何不低于整体暴力猜测的状态都不可能最优
        dp: list[list[tuple]] = [[] for _ in range(n + 1)]
        dp[0] = [(0, 1, -1, -1)]
        for i in range(1, n + 1):
            candidates = []
            for j in range(i):
                seg_cost = seg[j][i][0]
                for index, state in enumerate(dp[j]):
                    value = state[1] * seg_cost
                    candidates.append((state[0] + 1, min(value, cap), j, index))
            candidates.sort()
            front: list[tuple] = []
            best_product = None
            for state in candidates:
                # 片段数更少且成本积更小的状态支配其余状态
                if best_product is None or state[1] < best_product:
                    front.append(state)
                    best_product = state[1]
            dp[i] = front
        best_total = None
        best_state = None
        for state in dp[n]:
            total = state[1] * _FACTORIALS[state[0]]
            if best_total is None or total < best_total:
                best_total = total
                best_state = state
        # 回溯取得一条达到最小成本的拆分
        chosen = []
        i, state = n, best_state
        while i > 0:
            _, _, j, index = state
            chosen.append((j, i))
            i = j
            state = dp[j][index]
        chosen.reverse()
        segments = tuple(
            self._build_segment(text, j, i, seg[j][i]) for j, i in chosen
        )
        return PasswordExplanation(
            text=text,
            segments=segments,
            segment_count=len(segments),
            factorial_multiplier=_FACTORIALS[len(segments)],
            total_cost=best_total,
        )

    def _build_segment(
        self, text: str, j: int, i: int, entry: tuple
    ) -> SegmentExplanation:
        cost, kind, payload = entry
        piece = text[j:i]
        if kind == "brute":
            return SegmentExplanation(j, i, piece, "brute", cost)
        if kind == "dictionary":
            word, rank, _, reversed_flag = payload
            transformed = piece.lower()
            if reversed_flag:
                transformed = transformed[::-1]
            substitutions = tuple(
                Substitution(pos, have, want)
                for pos, (have, want) in enumerate(zip(transformed, word))
                if have != want
            )
            uppercase = sum(1 for ch in piece if "A" <= ch <= "Z")
            exponent = (
                uppercase + len(substitutions) + (1 if reversed_flag else 0)
            )
            return SegmentExplanation(
                j,
                i,
                piece,
                "dictionary",
                cost,
                word=word,
                rank=rank,
                substitutions=substitutions,
                reversed=reversed_flag,
                uppercase_count=uppercase,
                exponent=exponent,
            )
        # kind == "repeat"
        k, unit = payload
        return SegmentExplanation(
            j,
            i,
            piece,
            "repeat",
            cost,
            repeat_count=k,
            unit=unit,
            unit_explanation=self._memo[unit],
        )
