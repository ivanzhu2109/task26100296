"""Explanation data structures for password analysis results.

An explanation is a tree that covers every character of the analyzed
password and allows an independent recomputation of the total cost.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Substitution:
    """A single leet-style replacement inside a dictionary match."""

    offset: int  # position inside the segment (0-based)
    original: str  # character as it appears in the password segment
    replacement: str  # character used to form the dictionary word


@dataclass(frozen=True, slots=True)
class SegmentExplanation:
    """How one contiguous segment of the password is billed.

    ``start``/``end`` are offsets relative to the string this segment's
    analysis covers (the whole password at top level, the repeat unit
    inside a repeat explanation).
    """

    start: int
    end: int
    text: str
    method: str  # "brute_force" | "dictionary" | "repeat"
    cost: int
    # dictionary fields
    word: str | None = None
    rank: int | None = None
    reversed: bool = False
    uppercase_count: int = 0
    substitutions: tuple[Substitution, ...] = ()
    multiplier: int = 0  # 2 ** exponent for dictionary matches
    # repeat fields
    repeat_count: int = 0
    unit: str = ""
    unit_analysis: "AnalysisResult | None" = None


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Result of analyzing a password (or a repeat unit).

    ``cost`` equals ``factorial(len(segments))`` times the product of the
    segment costs.
    """

    text: str
    cost: int
    segments: tuple[SegmentExplanation, ...] = field(default_factory=tuple)

    @property
    def segment_count(self) -> int:
        return len(self.segments)
