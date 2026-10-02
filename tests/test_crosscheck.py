"""Cross-check the library against exhaustive enumeration."""

from __future__ import annotations

import random

import pytest

from cyberquest import Analyzer, Dictionary, verify_analysis
from reference import ReferenceScorer

WORDS = [
    "a",
    "ab",
    "abc",
    "b",
    "ba",
    "cab",
    "i",
    "l",
    "o",
    "s",
    "so",
    "sol",
    "to",
    "01",
]


@pytest.fixture(scope="module")
def analyzer() -> Analyzer:
    return Analyzer(Dictionary(WORDS))


@pytest.fixture(scope="module")
def reference() -> ReferenceScorer:
    return ReferenceScorer(WORDS)


@pytest.mark.parametrize("seed", range(120))
def test_random_short_passwords_match_exhaustive(
    analyzer: Analyzer, reference: ReferenceScorer, seed: int
) -> None:
    rng = random.Random(seed)
    alphabet = "abcols01AB3!"
    length = rng.randint(1, 9)
    password = "".join(rng.choice(alphabet) for _ in range(length))
    result = analyzer.analyze(password)
    assert result.cost == reference.full_cost(password), password
    assert verify_analysis(result, analyzer._dictionary) == result.cost


def test_repeat_heavy_passwords_match_exhaustive(
    analyzer: Analyzer, reference: ReferenceScorer
) -> None:
    for password in ["ababab", "abcabc", "aaaaaa", "ababa", "aabbaabb", "s0s0s0"]:
        result = analyzer.analyze(password)
        assert result.cost == reference.full_cost(password), password
        assert verify_analysis(result) == result.cost
