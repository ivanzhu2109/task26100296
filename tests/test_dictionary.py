"""Dictionary loading and password validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from cyberquest import Analyzer, Dictionary, validate_password


def test_load_ranks_follow_line_numbers(tmp_path: Path) -> None:
    path = tmp_path / "words.txt"
    path.write_text("apple\nbanana\ncherry\n", encoding="utf-8")
    dictionary = Dictionary.load(str(path))
    assert len(dictionary) == 3
    assert dictionary.rank_of("apple") == 1
    assert dictionary.rank_of("banana") == 2
    assert dictionary.rank_of("cherry") == 3
    assert dictionary.rank_of("missing") is None


def test_load_utf8_and_trailing_newline(tmp_path: Path) -> None:
    path = tmp_path / "words.txt"
    path.write_text("word\n", encoding="utf-8")
    assert len(Dictionary.load(str(path))) == 1


def test_duplicate_word_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        Dictionary(["one", "two", "one"])


def test_uppercase_word_rejected() -> None:
    with pytest.raises(ValueError, match="lowercase"):
        Dictionary(["Word"])


def test_empty_line_rejected() -> None:
    with pytest.raises(ValueError, match="empty"):
        Dictionary(["one", "", "two"])


def test_overlong_word_rejected() -> None:
    with pytest.raises(ValueError, match="32"):
        Dictionary(["x" * 33])


def test_non_ascii_word_rejected() -> None:
    with pytest.raises(ValueError, match="lowercase"):
        Dictionary(["café"])


def test_dictionary_immutable_source() -> None:
    words = ["one", "two"]
    dictionary = Dictionary(words)
    words.append("three")
    assert len(dictionary) == 2
    assert dictionary.rank_of("three") is None


def test_password_validation() -> None:
    validate_password("a")  # shortest legal password
    validate_password("".join(chr(c) for c in range(32, 127)))
    validate_password("x" * 128)  # longest legal password
    with pytest.raises(ValueError):
        validate_password("")
    with pytest.raises(ValueError):
        validate_password("x" * 129)
    with pytest.raises(ValueError):
        validate_password("tab\there")
    with pytest.raises(ValueError):
        validate_password("unicodeé")
    with pytest.raises(ValueError):
        validate_password("del\x7f")


def test_analyzer_rejects_invalid_password() -> None:
    analyzer = Analyzer(Dictionary([]))
    with pytest.raises(ValueError):
        analyzer.analyze("bad\npassword")


def test_brute_force_only_without_dictionary() -> None:
    analyzer = Analyzer(Dictionary([]))
    result = analyzer.analyze("xY9!")
    assert result.cost == 95**4
    assert result.segments[0].method == "brute_force"
