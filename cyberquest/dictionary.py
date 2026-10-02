"""Dictionary loading and lookup structures.

The dictionary file is UTF-8 text with one unique lowercase ASCII word
per line. The 1-based line number is the word's guessing rank.
"""

from __future__ import annotations

from dataclasses import dataclass

from .explanation import Substitution

MAX_WORD_LENGTH = 32

# Leet digits that may be restored to letters before matching.
LEET_MAP: dict[str, tuple[str, ...]] = {
    "0": ("o",),
    "1": ("i", "l"),
    "3": ("e",),
    "4": ("a",),
    "5": ("s",),
    "7": ("t",),
}


@dataclass(frozen=True, slots=True)
class DictionaryMatch:
    """One way a segment can be billed as a dictionary word."""

    word: str
    rank: int
    reversed: bool
    substitutions: tuple  # tuple[Substitution, ...]


class _TrieNode:
    """Node of the dictionary trie (children + optional terminal rank)."""

    __slots__ = ("children", "rank", "word")

    def __init__(self) -> None:
        self.children: dict[str, _TrieNode] = {}
        self.rank: int | None = None
        self.word: str | None = None


# Per-character expansion options, cached: char -> ((form, is_sub), ...).
_OPTION_CACHE: dict[str, tuple[tuple[str, bool], ...]] = {}


def _char_options(ch: str) -> tuple[tuple[str, bool], ...]:
    options = _OPTION_CACHE.get(ch)
    if options is None:
        lowered = ch.lower()
        choices: list[tuple[str, bool]] = [(lowered, False)]
        choices.extend((alt, True) for alt in LEET_MAP.get(lowered, ()))
        options = tuple(choices)
        _OPTION_CACHE[ch] = options
    return options


class Dictionary:
    """Immutable ranked word list with forward and reversed tries."""

    def __init__(self, words: list[str]) -> None:
        ranks: dict[str, int] = {}
        forward = _TrieNode()
        backward = _TrieNode()
        for index, word in enumerate(words, start=1):
            self._validate_word(word, index)
            if word in ranks:
                raise ValueError(f"duplicate dictionary word at line {index}: {word!r}")
            ranks[word] = index
            self._insert(forward, word, word, index)
            self._insert(backward, word[::-1], word, index)
        self._ranks = ranks
        self._forward = forward
        self._backward = backward
        self._size = len(words)

    @staticmethod
    def _validate_word(word: str, line: int) -> None:
        if not word:
            raise ValueError(f"empty word at dictionary line {line}")
        if len(word) > MAX_WORD_LENGTH:
            raise ValueError(
                f"word at dictionary line {line} exceeds {MAX_WORD_LENGTH} chars"
            )
        for ch in word:
            code = ord(ch)
            if code < 32 or code > 126 or "A" <= ch <= "Z":
                raise ValueError(
                    f"word at dictionary line {line} is not lowercase ASCII: {word!r}"
                )

    @staticmethod
    def _insert(root: _TrieNode, key: str, word: str, rank: int) -> None:
        node = root
        for ch in key:
            node = node.children.setdefault(ch, _TrieNode())
        node.rank = rank
        node.word = word

    @classmethod
    def load(cls, path: str) -> "Dictionary":
        """Load a dictionary from a UTF-8 file (one word per line)."""
        with open(path, "r", encoding="utf-8") as handle:
            words = handle.read().splitlines()
        return cls(words)

    def __len__(self) -> int:
        return self._size

    def rank_of(self, word: str) -> int | None:
        """Return the 1-based rank of ``word`` or None if absent."""
        return self._ranks.get(word)

    def match_segment(self, segment: str) -> list[DictionaryMatch]:
        """All dictionary matches for a segment.

        The segment is lowercased, leet digits may be restored
        (0->o, 1->i|l, 3->e, 4->a, 5->s, 7->t) and the result may be
        reversed as a whole. Every distinct (word, reversed,
        substitutions) combination that exactly equals a dictionary
        word is returned.
        """
        matches: list[DictionaryMatch] = []
        self._collect(segment, self._forward, False, matches)
        self._collect(segment, self._backward, True, matches)
        return matches

    @staticmethod
    def _collect(
        segment: str,
        root: _TrieNode,
        reversed_: bool,
        matches: list[DictionaryMatch],
    ) -> None:
        """DFS the trie while expanding per-character options."""
        # Stack entries: (position, node, substitutions-so-far).
        stack: list[tuple[int, _TrieNode, tuple[Substitution, ...]]] = [(0, root, ())]
        length = len(segment)
        while stack:
            pos, node, subs = stack.pop()
            if pos == length:
                if node.rank is not None:
                    matches.append(
                        DictionaryMatch(
                            word=node.word,  # type: ignore[arg-type]
                            rank=node.rank,
                            reversed=reversed_,
                            substitutions=subs,
                        )
                    )
                continue
            original = segment[pos]
            for candidate, is_substitution in _char_options(original):
                child = node.children.get(candidate)
                if child is None:
                    continue
                if not is_substitution:
                    stack.append((pos + 1, child, subs))
                else:
                    stack.append(
                        (
                            pos + 1,
                            child,
                            subs
                            + (
                                Substitution(
                                    offset=pos,
                                    original=original,
                                    replacement=candidate,
                                ),
                            ),
                        )
                    )
