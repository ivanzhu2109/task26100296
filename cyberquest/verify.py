"""Independent recomputation of analysis explanations.

``verify_analysis`` walks an explanation tree and recomputes the total
cost from the stored details alone, raising ``ValueError`` on any
inconsistency. It never consults the analyzer's internal state, so a
caller can confirm that the returned cost is reproducible.
"""

from __future__ import annotations

from .analysis import FACTORIAL, POW95
from .dictionary import Dictionary
from .explanation import AnalysisResult, SegmentExplanation


def verify_analysis(
    result: AnalysisResult, dictionary: Dictionary | None = None
) -> int:
    """Recompute and return the total cost of ``result``.

    Raises ValueError if the explanation does not cover every character
    exactly once or if any stored detail fails to recompute.
    """
    if not result.segments:
        raise ValueError("analysis has no segments")
    expected_start = 0
    product = 1
    for segment in result.segments:
        if segment.start != expected_start:
            raise ValueError(
                f"segment gap or overlap at offset {expected_start}"
            )
        if segment.end <= segment.start:
            raise ValueError("empty segment in explanation")
        if result.text[segment.start : segment.end] != segment.text:
            raise ValueError(
                f"segment text mismatch at {segment.start}:{segment.end}"
            )
        product *= _verify_segment(segment, dictionary)
        expected_start = segment.end
    if expected_start != len(result.text):
        raise ValueError("segments do not cover the whole text")
    total = FACTORIAL[len(result.segments)] * product
    if total != result.cost:
        raise ValueError(
            f"recomputed cost {total} != reported cost {result.cost}"
        )
    return total


def _verify_segment(
    segment: SegmentExplanation, dictionary: Dictionary | None
) -> int:
    if segment.method == "brute_force":
        cost = POW95[len(segment.text)]
    elif segment.method == "dictionary":
        cost = _verify_dictionary(segment, dictionary)
    elif segment.method == "repeat":
        cost = _verify_repeat(segment, dictionary)
    else:
        raise ValueError(f"unknown billing method: {segment.method!r}")
    if cost != segment.cost:
        raise ValueError(
            f"segment {segment.text!r} cost {segment.cost} recomputes to {cost}"
        )
    return cost


def _verify_dictionary(
    segment: SegmentExplanation, dictionary: Dictionary | None
) -> int:
    if segment.word is None or segment.rank is None:
        raise ValueError("dictionary segment misses word or rank")
    chars = list(segment.text.lower())
    for substitution in segment.substitutions:
        pos = substitution.offset
        if not 0 <= pos < len(chars):
            raise ValueError("substitution offset out of range")
        if segment.text[pos] != substitution.original:
            raise ValueError("substitution original char mismatch")
        chars[pos] = substitution.replacement
    transformed = "".join(chars)
    if segment.reversed:
        transformed = transformed[::-1]
    if transformed != segment.word:
        raise ValueError(
            f"transformed segment {transformed!r} != word {segment.word!r}"
        )
    uppercase = sum(1 for ch in segment.text if "A" <= ch <= "Z")
    if uppercase != segment.uppercase_count:
        raise ValueError("uppercase count mismatch")
    exponent = (
        uppercase + len(segment.substitutions) + (1 if segment.reversed else 0)
    )
    if segment.multiplier != 1 << exponent:
        raise ValueError("multiplier mismatch")
    if dictionary is not None and dictionary.rank_of(segment.word) != segment.rank:
        raise ValueError(f"rank mismatch for word {segment.word!r}")
    return segment.rank * segment.multiplier


def _verify_repeat(
    segment: SegmentExplanation, dictionary: Dictionary | None
) -> int:
    if segment.repeat_count < 2 or not segment.unit:
        raise ValueError("illegal repeat structure")
    if segment.unit * segment.repeat_count != segment.text:
        raise ValueError("segment is not unit repeated k times")
    if segment.unit_analysis is None:
        raise ValueError("repeat segment misses unit analysis")
    if segment.unit_analysis.text != segment.unit:
        raise ValueError("unit analysis text mismatch")
    unit_cost = verify_analysis(segment.unit_analysis, dictionary)
    return segment.repeat_count * unit_cost
