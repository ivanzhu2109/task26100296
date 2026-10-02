"""Independent exhaustive reference implementation for cross-checking.

Deliberately naive: enumerates every partition, every leet variant and
every repeat unit directly from the rules, without sharing code with
the library under test.
"""

from __future__ import annotations

from functools import lru_cache
from itertools import product
from math import factorial

LEET = {"0": ("o",), "1": ("i", "l"), "3": ("e",), "4": ("a",), "5": ("s",), "7": ("t",)}


def _compositions(n: int):
    """All ordered partitions of n into positive parts."""
    if n == 0:
        yield []
        return
    for first in range(1, n + 1):
        for rest in _compositions(n - first):
            yield [first] + rest


class ReferenceScorer:
    def __init__(self, words: list[str]) -> None:
        self.ranks = {word: index + 1 for index, word in enumerate(words)}

    def segment_cost(self, segment: str) -> int:
        best = 95 ** len(segment)
        best = min(best, self._dictionary_cost(segment))
        best = min(best, self._repeat_cost(segment))
        return best

    def _dictionary_cost(self, segment: str) -> int:
        upper = sum(1 for ch in segment if "A" <= ch <= "Z")
        options = []
        for ch in segment:
            lowered = ch.lower()
            choices = [lowered]
            choices.extend(LEET.get(lowered, ()))
            options.append(choices)
        best = None
        for combo in product(*options):
            substitutions = sum(
                1 for orig, chosen in zip(segment, combo) if chosen != orig.lower()
            )
            variant = "".join(combo)
            for reversed_flag, candidate in ((0, variant), (1, variant[::-1])):
                rank = self.ranks.get(candidate)
                if rank is None:
                    continue
                cost = rank * 2 ** (upper + substitutions + reversed_flag)
                if best is None or cost < best:
                    best = cost
        return best if best is not None else 95 ** len(segment)

    def _repeat_cost(self, segment: str) -> int:
        best = 95 ** len(segment)
        n = len(segment)
        for k in range(2, n + 1):
            if n % k:
                continue
            unit = segment[: n // k]
            if unit * k == segment:
                best = min(best, k * self.full_cost(unit))
        return best

    @lru_cache(maxsize=None)
    def full_cost(self, text: str) -> int:
        n = len(text)
        best = None
        for parts in _compositions(n):
            product_cost = 1
            offset = 0
            for part in parts:
                product_cost *= self.segment_cost(text[offset : offset + part])
                offset += part
            total = factorial(len(parts)) * product_cost
            if best is None or total < best:
                best = total
        return best
