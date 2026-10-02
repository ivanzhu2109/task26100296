"""Performance and memory acceptance test.

Loads a 100k-word dictionary and analyzes 100 distinct 128-character
passwords (random, leet/digit-heavy and multi-period repetitive),
asserting the 30 s / 512 MiB budget and verifying every explanation.
"""

from __future__ import annotations

import resource
import sys
import time
from pathlib import Path

from cyberquest import Analyzer, Dictionary, verify_analysis
from perfdata import make_passwords, make_words

TIME_BUDGET_SECONDS = 30
MEMORY_BUDGET_BYTES = 512 * 1024 * 1024


def _peak_rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux reports KiB, macOS reports bytes.
    if sys.platform == "darwin":
        return peak
    return peak * 1024


def test_performance_budget(tmp_path: Path) -> None:
    words = make_words(100_000)
    dictionary_path = tmp_path / "words.txt"
    dictionary_path.write_text("\n".join(words) + "\n", encoding="utf-8")
    dictionary = Dictionary.load(str(dictionary_path))
    assert len(dictionary) == 100_000

    passwords = make_passwords(words)
    analyzer = Analyzer(dictionary)

    start = time.perf_counter()
    results = [analyzer.analyze(password) for password in passwords]
    elapsed = time.perf_counter() - start

    for result in results:
        assert verify_analysis(result, dictionary) == result.cost

    peak = _peak_rss_bytes()
    print(
        f"\nanalyzed 100 x 128-char passwords in {elapsed:.2f}s "
        f"(budget {TIME_BUDGET_SECONDS}s), peak RSS "
        f"{peak / 1024 / 1024:.0f} MiB "
        f"(budget {MEMORY_BUDGET_BYTES // 1024 // 1024} MiB)"
    )
    assert elapsed <= TIME_BUDGET_SECONDS
    assert peak <= MEMORY_BUDGET_BYTES
