"""Scenario tests pinning the business rules with exact costs."""

from __future__ import annotations

from cyberquest import Analyzer, Dictionary, verify_analysis


def test_segment_count_factorial_penalty() -> None:
    # Splitting "aabb" into the locally cheapest pieces "aa" (rank 1)
    # and "bb" (rank 2) has the cheaper product (1 * 2 = 2 < 3), but
    # the 2! penalty makes it 4, so the single segment "aabb" (rank 3)
    # is the global optimum.
    analyzer = Analyzer(Dictionary(["aa", "bb", "aabb"]))
    result = analyzer.analyze("aabb")
    assert result.cost == 3
    assert len(result.segments) == 1
    assert result.segments[0].method == "dictionary"
    assert result.segments[0].word == "aabb"
    assert verify_analysis(result) == 3


def test_single_segment_beats_split_via_factorial() -> None:
    # "abc" as one dictionary word (rank 1) costs 1; any split pays the
    # factorial penalty and costs at least 2.
    analyzer = Analyzer(Dictionary(["abc", "ab", "bc", "a", "b", "c"]))
    result = analyzer.analyze("abc")
    assert result.cost == 1
    assert len(result.segments) == 1
    assert result.segments[0].method == "dictionary"


def test_same_digit_maps_to_different_words() -> None:
    # "1" may restore to "i" or "l"; the cheaper rank must win.
    analyzer = Analyzer(Dictionary(["i", "l"]))
    result = analyzer.analyze("1")
    assert result.cost == 1 * 2  # rank 1, one substitution
    segment = result.segments[0]
    assert segment.method == "dictionary"
    assert segment.word == "i"
    assert verify_analysis(result) == result.cost

    # Flip the ranks: now "l" is the cheap restoration.
    analyzer = Analyzer(Dictionary(["l", "i"]))
    result = analyzer.analyze("1")
    assert result.cost == 2
    assert result.segments[0].word == "l"


def test_reversal_case_and_substitution_stacking() -> None:
    # "0LL3H" -> lower "0ll3h" -> substitute "olleh" -> reverse "hello".
    # exponent = 3 uppercase + 2 substitutions + 1 reversed = 6.
    analyzer = Analyzer(Dictionary(["hello"]))
    result = analyzer.analyze("0LL3H")
    assert result.cost == 1 * 2**6
    segment = result.segments[0]
    assert segment.method == "dictionary"
    assert segment.word == "hello"
    assert segment.reversed is True
    assert segment.uppercase_count == 3
    assert len(segment.substitutions) == 2
    assert verify_analysis(result) == result.cost


def test_longer_repeat_unit_wins_via_top_ranked_word() -> None:
    # "abcabc" * 2 with "abcabc" at rank 1 beats "abc" * 4 because the
    # short unit only matches a high (expensive) rank.
    words = ["abcabc"] + [f"w{i:02d}" for i in range(48)] + ["abc"]
    analyzer = Analyzer(Dictionary(words))
    result = analyzer.analyze("abcabcabcabc")
    # repeat "abcabc" x 2 -> 2 * 1 = 2; repeat "abc" x 4 -> 4 * 50 = 200.
    assert result.cost == 2
    segment = result.segments[0]
    assert segment.method == "repeat"
    assert segment.unit == "abcabc"
    assert segment.repeat_count == 2
    assert segment.unit_analysis is not None
    assert segment.unit_analysis.segments[0].method == "dictionary"
    assert verify_analysis(result) == 2


def test_shortest_repeat_unit_wins_when_cheap() -> None:
    analyzer = Analyzer(Dictionary(["ab"]))
    result = analyzer.analyze("ababab")
    assert result.cost == 3  # 3 * F("ab") = 3 * 1
    segment = result.segments[0]
    assert segment.method == "repeat"
    assert segment.unit == "ab"
    assert segment.repeat_count == 3


def test_nested_repeat_inside_repeat() -> None:
    # "aaaa" as "a" x 4 costs 4 * 95; as "aa" x 2 it costs
    # 2 * F("aa") = 2 * (2 * 95) -- identical, either is legal.
    analyzer = Analyzer(Dictionary([]))
    result = analyzer.analyze("aaaa")
    assert result.cost == 4 * 95
    segment = result.segments[0]
    assert segment.method == "repeat"
    assert verify_analysis(result) == result.cost


def test_mixed_methods_in_one_password() -> None:
    # "Hello" dictionary + "!!" repeat ("!" x 2), factorial 2! applies.
    analyzer = Analyzer(Dictionary(["hello"]))
    result = analyzer.analyze("Hello!!")
    hello_cost = 1 * 2**1  # one uppercase letter
    bang_cost = 2 * 95  # repeat "!" x 2
    assert result.cost == 2 * (hello_cost * bang_cost)
    methods = [s.method for s in result.segments]
    assert methods == ["dictionary", "repeat"]
    assert verify_analysis(result) == result.cost
