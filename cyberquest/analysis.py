"""Password analysis: minimum-cost partition with explanations.

Cost model (all costs are exact integers):

* A scheme partitions the whole password into ``m`` contiguous,
  non-overlapping, non-empty segments. Its cost is
  ``factorial(m)`` times the product of the segment costs.
* A segment may be billed three ways (the cheapest wins, ties broken
  in the order dictionary > repeat > brute force):

  - brute force: ``95 ** len(segment)``;
  - dictionary: ``rank * 2 ** (uppercase + substitutions + reversed)``;
  - repeat: if the segment is ``unit * k`` with ``k >= 2``, the cost is
    ``k * F(unit)`` where ``F(unit)`` is the minimum-cost standalone
    analysis of the unit (which may itself split, match and repeat).

* The analysis result is the minimum cost over all legal schemes plus
  one explanation tree that attains it.
"""

from __future__ import annotations

from dataclasses import replace

from .dictionary import MAX_WORD_LENGTH, Dictionary
from .explanation import AnalysisResult, SegmentExplanation

MAX_PASSWORD_LENGTH = 128
PRINTABLE_MIN = 32
PRINTABLE_MAX = 126

# Exact integer cost tables (passwords are at most 128 chars).
POW95 = [1] * (MAX_PASSWORD_LENGTH + 1)
for _i in range(1, MAX_PASSWORD_LENGTH + 1):
    POW95[_i] = POW95[_i - 1] * 95

FACTORIAL = [1] * (MAX_PASSWORD_LENGTH + 1)
for _i in range(1, MAX_PASSWORD_LENGTH + 1):
    FACTORIAL[_i] = FACTORIAL[_i - 1] * _i

# Repeat factors: REPEAT_KS[n] = [k ...] with k >= 2 and k divides n.
REPEAT_KS = [
    [k for k in range(2, n + 1) if n % k == 0]
    for n in range(MAX_PASSWORD_LENGTH + 1)
]


def validate_password(password: str) -> None:
    """Raise ValueError if the password is not printable ASCII."""
    if not password:
        raise ValueError("password must not be empty")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(
            f"password exceeds {MAX_PASSWORD_LENGTH} characters"
        )
    for ch in password:
        code = ord(ch)
        if code < PRINTABLE_MIN or code > PRINTABLE_MAX:
            raise ValueError(
                f"password contains non printable ASCII character: {ch!r}"
            )


class Analyzer:
    """Analyzes passwords against one immutable loaded dictionary."""

    def __init__(self, dictionary: Dictionary) -> None:
        self._dictionary = dictionary
        # Per-analysis memoization, recreated for every analyze() call.
        self._seg_cache: dict[str, SegmentExplanation] = {}
        self._full_cache: dict[str, AnalysisResult] = {}

    def analyze(self, password: str) -> AnalysisResult:
        """Return the minimum-cost analysis of ``password``."""
        validate_password(password)
        self._seg_cache = {}
        self._full_cache = {}
        return self._full_cost(password)

    # -- internal building blocks (per-analysis memoized) --

    def _segment_cost(self, segment: str) -> SegmentExplanation:
        """Cheapest single-segment billing for ``segment``."""
        cached = self._seg_cache.get(segment)
        if cached is not None:
            return cached

        length = len(segment)
        best = SegmentExplanation(
            start=0,
            end=length,
            text=segment,
            method="brute_force",
            cost=POW95[length],
        )

        # Repeat structure: segment == unit * k with k >= 2.
        for k in REPEAT_KS[length]:
            unit = segment[: length // k]
            if unit * k != segment:
                continue
            unit_result = self._full_cost(unit)
            cost = k * unit_result.cost
            if cost <= best.cost:
                best = SegmentExplanation(
                    start=0,
                    end=length,
                    text=segment,
                    method="repeat",
                    cost=cost,
                    repeat_count=k,
                    unit=unit,
                    unit_analysis=unit_result,
                )

        # Dictionary matches (leet restore + optional reversal). Words
        # are at most MAX_WORD_LENGTH chars, so longer segments can
        # never match.
        matches = (
            self._dictionary.match_segment(segment)
            if length <= MAX_WORD_LENGTH
            else []
        )
        if matches:
            uppercase = sum(1 for ch in segment if "A" <= ch <= "Z")
        for match in matches:
            exponent = (
                uppercase
                + len(match.substitutions)
                + (1 if match.reversed else 0)
            )
            multiplier = 1 << exponent
            cost = match.rank * multiplier
            if cost <= best.cost:
                best = SegmentExplanation(
                    start=0,
                    end=length,
                    text=segment,
                    method="dictionary",
                    cost=cost,
                    word=match.word,
                    rank=match.rank,
                    reversed=match.reversed,
                    uppercase_count=uppercase,
                    substitutions=match.substitutions,
                    multiplier=multiplier,
                )

        self._seg_cache[segment] = best
        return best

    def _full_cost(self, text: str) -> AnalysisResult:
        """Minimum-cost standalone analysis of ``text``."""
        cached = self._full_cache.get(text)
        if cached is not None:
            return cached

        length = len(text)
        # Segment cost rows: seg_rows[prev][pos - prev - 1] covers
        # text[prev:pos]. Entries are shared memoized explanations.
        seg_rows = [
            [self._segment_cost(text[prev:pos]) for pos in range(prev + 1, length + 1)]
            for prev in range(length)
        ]

        # Fast path: if every segment is billed brute force at 95**len,
        # every partition costs factorial(m) * 95**length, so the single
        # segment is optimal.
        if all(
            explanation.cost == POW95[pos - prev]
            for prev in range(length)
            for pos, explanation in enumerate(seg_rows[prev], start=prev + 1)
        ):
            result = AnalysisResult(
                text=text, cost=POW95[length], segments=(seg_rows[0][length - 1],)
            )
            self._full_cache[text] = result
            return result

        # Upper bound on the answer: the single-segment scheme. States
        # whose factorial-weighted cost cannot beat it are useless and
        # are pruned via the SENTINEL value.
        bound = seg_rows[0][length - 1].cost
        if bound == 1:
            # 1 is the smallest possible cost; nothing can tie or beat it.
            result = AnalysisResult(
                text=text, cost=1, segments=(seg_rows[0][length - 1],)
            )
            self._full_cache[text] = result
            return result
        sentinel = bound
        # A state (pos, m) with product p is useful only while
        # FACTORIAL[m] * p < bound, i.e. p <= limit[m].
        limit = [(bound - 1) // FACTORIAL[m] for m in range(length + 1)]
        m_cap = max(m for m in range(length + 1) if limit[m] >= 1)

        # dp[pos][m] = minimum product of m segment costs covering
        # text[:pos]; parent[pos][m] = (prev, segment explanation).
        dp: list[list[int]] = [[1]]
        parent: list[list[tuple[int, SegmentExplanation] | None]] = [[None]]
        row_max = [0]
        for pos in range(1, length + 1):
            width = min(pos, m_cap)
            row: list[int] = [sentinel] * (width + 1)
            prow: list[tuple[int, SegmentExplanation] | None] = [None] * (pos + 1)
            for prev in range(pos):
                explanation = seg_rows[prev][pos - prev - 1]
                cost = explanation.cost
                prev_row = dp[prev]
                hi = row_max[prev] + 1
                if hi > width:
                    hi = width
                for m in range(1, hi + 1):
                    candidate = prev_row[m - 1] * cost
                    if candidate <= limit[m] and candidate < row[m]:
                        row[m] = candidate
                        prow[m] = (prev, explanation)
            dp.append(row)
            parent.append(prow)
            top = width
            while top > 0 and row[top] >= sentinel:
                top -= 1
            row_max.append(top)

        best_cost = bound
        best_m = 1
        final_row = dp[length]
        for m in range(1, min(length, m_cap) + 1):
            candidate = FACTORIAL[m] * final_row[m]
            if candidate < best_cost:
                best_cost = candidate
                best_m = m

        if best_m == 1 and final_row[1] >= sentinel:
            # The single-segment scheme is optimal.
            result = AnalysisResult(
                text=text, cost=bound, segments=(seg_rows[0][length - 1],)
            )
            self._full_cache[text] = result
            return result

        segments: list[SegmentExplanation] = []
        pos = length
        m = best_m
        while pos > 0:
            prev, explanation = parent[pos][m]  # type: ignore[misc]
            segments.append(replace(explanation, start=prev, end=pos))
            pos = prev
            m -= 1
        segments.reverse()

        result = AnalysisResult(text=text, cost=best_cost, segments=tuple(segments))
        self._full_cache[text] = result
        return result
