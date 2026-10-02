"""Shared generators for the performance test."""

from __future__ import annotations

import random
import string

PRINTABLE = "".join(chr(c) for c in range(32, 127))
LEET_FOR = {"o": "0", "i": "1", "l": "1", "e": "3", "a": "4", "s": "5", "t": "7"}


def make_words(count: int, seed: int = 7) -> list[str]:
    rng = random.Random(seed)
    words: set[str] = set()
    while len(words) < count:
        # Mostly short words (dense, adversarial for matching) plus a
        # share of long words up to the 32-char maximum.
        length = rng.randint(2, 10) if rng.random() < 0.9 else rng.randint(11, 32)
        words.add("".join(rng.choices(string.ascii_lowercase, k=length)))
    return sorted(words)


def leetify(word: str, rng: random.Random) -> str:
    chars = []
    for ch in word:
        replacement = LEET_FOR.get(ch)
        if replacement and rng.random() < 0.7:
            chars.append(replacement)
        elif rng.random() < 0.3:
            chars.append(ch.upper())
        else:
            chars.append(ch)
    return "".join(chars)


def make_passwords(words: list[str], seed: int = 99) -> list[str]:
    rng = random.Random(seed)
    passwords: list[str] = []
    # 40 purely random printable passwords.
    for _ in range(40):
        passwords.append("".join(rng.choices(PRINTABLE, k=128)))
    # 30 leet/digit-heavy passwords built from dictionary words.
    for _ in range(30):
        parts = []
        length = 0
        while length < 128:
            piece = leetify(rng.choice(words), rng) + rng.choice("!?.#")
            parts.append(piece)
            length += len(piece)
        passwords.append("".join(parts)[:128])
    # 30 repetitive passwords with multiple repeat periods.
    bases = ["abc123!*", "P4ssw0rd", "a1b2c3", "qwerty77", "zZ9!"]
    for index in range(30):
        unit = bases[index % len(bases)] + str(index)
        repeats = 128 // len(unit)
        password = unit * repeats
        password += unit[: 128 - len(password)]
        passwords.append(password)
    assert len({p for p in passwords}) == 100
    assert all(len(p) == 128 for p in passwords)
    return passwords
