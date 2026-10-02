"""CyberQuest 口令评分库自动化测试。"""
from __future__ import annotations

import os
import random
import resource
import string
import sys
import tempfile
import time
import unittest
from functools import lru_cache
from math import factorial

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cyberquest import (
    ExplanationError,
    PasswordAnalyzer,
    Wordlist,
    load_wordlist,
    verify_explanation,
)

LEET = {"0": ("o",), "1": ("i", "l"), "3": ("e",), "4": ("a",),
        "5": ("s",), "7": ("t",)}


def reference_min_cost(words, password):
    """独立穷举参照：枚举全部拆分方案，直接按规则计算最小成本。"""
    ranks = {w: i + 1 for i, w in enumerate(words)}

    @lru_cache(maxsize=None)
    def analyze(s):
        n = len(s)
        best = None

        def rec(start, count, product):
            nonlocal best
            if start == n:
                total = factorial(count) * product
                if best is None or total < best:
                    best = total
                return
            for end in range(start + 1, n + 1):
                rec(end, count + 1, product * segment_cost(s[start:end]))

        rec(0, 0, 1)
        return best

    @lru_cache(maxsize=None)
    def segment_cost(seg):
        best = 95 ** len(seg)
        lower = seg.lower()
        upper = sum(1 for c in seg if "A" <= c <= "Z")
        for word, rank in ranks.items():
            if len(word) != len(seg):
                continue
            for rev in (False, True):
                t = lower[::-1] if rev else lower
                subs = 0
                ok = True
                for a, b in zip(t, word):
                    if a != b:
                        targets = LEET.get(a)
                        if targets is None or b not in targets:
                            ok = False
                            break
                        subs += 1
                if ok:
                    best = min(best, rank * 2 ** (upper + subs + rev))
        n = len(seg)
        for d in range(1, n):
            if n % d == 0 and seg[:d] * (n // d) == seg:
                best = min(best, (n // d) * analyze(seg[:d]))
        return best

    return analyze(password)


def check_explanation(testcase, explanation, wordlist, expected_cost):
    """解释须覆盖每个字符、复算成本与返回成本一致。"""
    testcase.assertEqual(explanation.total_cost, expected_cost)
    testcase.assertEqual(verify_explanation(explanation, wordlist), expected_cost)
    pos = 0
    for seg in explanation.segments:
        testcase.assertEqual(seg.start, pos)
        pos = seg.end
    testcase.assertEqual(pos, len(explanation.text))
    testcase.assertEqual(
        "".join(s.text for s in explanation.segments), explanation.text
    )


def make_wordlist_file(words):
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(words) + "\n")
    return path


class WordlistLoadingTests(unittest.TestCase):
    def test_ranks_follow_line_numbers(self):
        path = make_wordlist_file(["alpha", "beta", "gamma"])
        try:
            wl = load_wordlist(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(wl), 3)
        self.assertEqual(wl.rank_of("alpha"), 1)
        self.assertEqual(wl.rank_of("gamma"), 3)

    def test_duplicate_word_rejected(self):
        path = make_wordlist_file(["one", "two", "one"])
        try:
            with self.assertRaises(ValueError):
                load_wordlist(path)
        finally:
            os.unlink(path)

    def test_non_printable_rejected(self):
        path = make_wordlist_file(["ok", "bad\tword"])
        try:
            with self.assertRaises(ValueError):
                load_wordlist(path)
        finally:
            os.unlink(path)

    def test_utf8_file_with_non_ascii_word_rejected(self):
        fd, path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("fine\n汉字\n")
        try:
            with self.assertRaises(ValueError):
                load_wordlist(path)
        finally:
            os.unlink(path)


class PasswordValidationTests(unittest.TestCase):
    def setUp(self):
        self.analyzer = PasswordAnalyzer(Wordlist(["abc"]))

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            self.analyzer.analyze("")

    def test_too_long_rejected(self):
        with self.assertRaises(ValueError):
            self.analyzer.analyze("a" * 129)

    def test_non_printable_rejected(self):
        for ch in ("\t", "\n", "\x7f", "é"):
            with self.assertRaises(ValueError):
                self.analyzer.analyze("ab" + ch)

    def test_space_is_significant(self):
        r1 = self.analyzer.analyze("a b")
        r2 = self.analyzer.analyze("ab")
        self.assertNotEqual(r1.total_cost, r2.total_cost)


class FactorialPenaltyTests(unittest.TestCase):
    def test_local_cheapest_split_loses_to_segment_count_penalty(self):
        # 每段单独都命中最低排名，但 2! 惩罚使整词方案更优
        words = ["x", "y", "xy"]  # 排名 1, 2, 3
        wl = Wordlist(words)
        az = PasswordAnalyzer(wl)
        result = az.analyze("xy")
        # 整词：3；拆分 "x"+"y"：2! * 1 * 2 = 4；暴力：95^2
        check_explanation(self, result, wl, 3)
        self.assertEqual(result.segment_count, 1)
        self.assertEqual(result.segments[0].method, "dictionary")
        self.assertEqual(result.segments[0].word, "xy")
        self.assertEqual(result_min_cost_check(words, "xy"), 3)


def result_min_cost_check(words, password):
    return reference_min_cost(words, password)


class DictionaryMatchTests(unittest.TestCase):
    def test_same_digit_maps_to_different_words(self):
        # "1" 既可还原为 "i" 也可还原为 "l"，两种匹配都是合法候选
        wl = Wordlist(["ill", "lll"])
        az = PasswordAnalyzer(wl)
        result = az.analyze("1ll")
        # "ill"：1*2^1=2；"lll"：2*2^1=4 -> 选 "ill"
        check_explanation(self, result, wl, 2)
        self.assertEqual(result.segments[0].word, "ill")

        wl2 = Wordlist(["lll", "ill"])
        az2 = PasswordAnalyzer(wl2)
        result2 = az2.analyze("1ll")
        # 排名对调后 "lll" 更优：1*2^1=2
        check_explanation(self, result2, wl2, 2)
        self.assertEqual(result2.segments[0].word, "lll")

    def test_reverse_case_and_substitution_stack(self):
        wl = Wordlist(["was"])
        az = PasswordAnalyzer(wl)
        result = az.analyze("5Aw")
        # 反转后 "wa5" -> 5 还原为 s；大写 1 + 替换 1 + 反转 1 -> 1*2^3=8
        check_explanation(self, result, wl, 8)
        seg = result.segments[0]
        self.assertEqual(seg.method, "dictionary")
        self.assertTrue(seg.reversed)
        self.assertEqual(seg.uppercase_count, 1)
        self.assertEqual(len(seg.substitutions), 1)
        self.assertEqual(seg.exponent, 3)

    def test_digit_can_be_kept_when_word_contains_digit(self):
        wl = Wordlist(["h3llo", "hello"])
        az = PasswordAnalyzer(wl)
        result = az.analyze("h3llo")
        # 保留 "3" 命中 "h3llo"：1*2^0=1；替换命中 "hello"：2*2^1=4
        check_explanation(self, result, wl, 1)
        self.assertEqual(result.segments[0].word, "h3llo")

    def test_uppercase_only_multiplies(self):
        wl = Wordlist(["hello"])
        az = PasswordAnalyzer(wl)
        result = az.analyze("HeLLo")
        check_explanation(self, result, wl, 1 * 2 ** 3)  # H、L、L 共 3 个大写


class RepeatStructureTests(unittest.TestCase):
    def test_longer_unit_beats_shortest_via_word_hit(self):
        # 最短单元 "abc" 不在词库，较长单元 "abcabc" 命中高排名词条
        wl = Wordlist(["abcabc"])
        az = PasswordAnalyzer(wl)
        result = az.analyze("abcabcabcabc")
        # k=2，单元 "abcabc" 词库成本 1 -> 2*1=2
        check_explanation(self, result, wl, 2)
        seg = result.segments[0]
        self.assertEqual(seg.method, "repeat")
        self.assertEqual(seg.repeat_count, 2)
        self.assertEqual(seg.unit, "abcabc")
        self.assertEqual(seg.unit_explanation.segments[0].method, "dictionary")

    def test_nested_repeat(self):
        wl = Wordlist(["ab"])
        az = PasswordAnalyzer(wl)
        result = az.analyze("abababab")
        # k=4 单元 "ab"：4*1=4；k=2 单元 "abab"（内部 k=2 单元 "ab"）：2*2=4
        check_explanation(self, result, wl, 4)

    def test_repeat_of_brute_force_unit(self):
        wl = Wordlist([])
        az = PasswordAnalyzer(wl)
        result = az.analyze("xyzxyz")
        # k=2，单元 "xyz" 暴力 95^3 -> 2*95^3，优于整段暴力 95^6
        check_explanation(self, result, wl, 2 * 95 ** 3)

    def test_all_same_character(self):
        wl = Wordlist([])
        az = PasswordAnalyzer(wl)
        result = az.analyze("aaaa")
        # k=4 单元 "a"：4*95；k=2 单元 "aa"：2*(2*95)=380 -> 380
        check_explanation(self, result, wl, 380)


class BruteForceTests(unittest.TestCase):
    def test_pure_symbols(self):
        wl = Wordlist([])
        az = PasswordAnalyzer(wl)
        result = az.analyze("#$%&")
        check_explanation(self, result, wl, 95 ** 4)
        self.assertEqual(result.segments[0].method, "brute")


class ExhaustiveCrossCheckTests(unittest.TestCase):
    def test_matches_independent_enumeration_on_short_passwords(self):
        rng = random.Random(20261002)
        alphabet = "aAbB013ilo "
        word_pool = ["a", "b", "ab", "ba", "all", "oil", "boil", "bail",
                     "lob", "boa", "a1", "silo"]
        for trial in range(60):
            words = rng.sample(word_pool, rng.randint(0, 6))
            wl = Wordlist(words)
            az = PasswordAnalyzer(wl)
            length = rng.randint(1, 8)
            password = "".join(rng.choice(alphabet) for _ in range(length))
            expected = reference_min_cost(words, password)
            result = az.analyze(password)
            check_explanation(self, result, wl, expected)


class ExplanationTamperingTests(unittest.TestCase):
    def test_tampered_cost_detected(self):
        wl = Wordlist(["hello"])
        az = PasswordAnalyzer(wl)
        result = az.analyze("h3110")
        result.total_cost += 1
        with self.assertRaises(ExplanationError):
            verify_explanation(result, wl)

    def test_wrong_word_detected(self):
        wl = Wordlist(["hello", "world"])
        az = PasswordAnalyzer(wl)
        result = az.analyze("h3110")
        result.segments[0].word = "world"
        with self.assertRaises(ExplanationError):
            verify_explanation(result, wl)


def generate_perf_passwords(words, count=100, seed=7):
    rng = random.Random(seed)
    printable = [chr(c) for c in range(32, 127)]
    passwords: set[str] = set()

    def leetify(w):
        out = []
        for ch in w:
            r = rng.random()
            if r < 0.25:
                out.append(ch.upper())
            elif r < 0.5:
                for digit, targets in LEET.items():
                    if ch in targets:
                        out.append(digit)
                        break
                else:
                    out.append(ch)
            else:
                out.append(ch)
        return "".join(out)

    # 25 条纯随机可打印字符
    while len(passwords) < 25:
        passwords.add("".join(rng.choice(printable) for _ in range(128)))
    # 25 条大量可替换数字（leet 化的词库单词拼接）
    while len(passwords) < 50:
        parts = []
        total = 0
        while total < 128:
            piece = leetify(rng.choice(words))
            parts.append(piece)
            total += len(piece)
        passwords.add("".join(parts)[:128])
    # 25 条多种重复周期（含嵌套与词库命中单元）
    periods = [1, 2, 4, 8, 16, 32, 64]
    while len(passwords) < 75:
        d = rng.choice(periods)
        if rng.random() < 0.5:
            unit = "".join(rng.choice(printable) for _ in range(d))
        else:
            unit = leetify(rng.choice(words))[:d].ljust(d, "q")
        passwords.add((unit * (128 // d))[:128])
    # 25 条混合：随机段 + 重复段 + leet 段
    while len(passwords) < count:
        rand_part = "".join(rng.choice(printable) for _ in range(40))
        unit = leetify(rng.choice(words))[:8].ljust(8, "z")
        rep_part = unit * 6
        leet_part = leetify(rng.choice(words))
        blob = (rand_part + rep_part + leet_part)
        blob = blob[:128].ljust(128, rng.choice(printable))
        passwords.add(blob)
    return sorted(passwords)


class PerformanceTests(unittest.TestCase):
    def test_100_passwords_of_length_128_within_budget(self):
        rng = random.Random(99)
        words = set()
        while len(words) < 20000:
            words.add("".join(rng.choice(string.ascii_lowercase)
                               for _ in range(rng.randint(3, 12))))
        words = sorted(words)
        path = make_wordlist_file(words)
        try:
            wl = load_wordlist(path)
        finally:
            os.unlink(path)
        analyzer = PasswordAnalyzer(wl)
        passwords = generate_perf_passwords(words)
        self.assertEqual(len(passwords), 100)
        self.assertTrue(all(len(p) == 128 for p in passwords))

        start = time.perf_counter()
        results = [analyzer.analyze(p) for p in passwords]
        elapsed = time.perf_counter() - start
        for result in results:
            self.assertEqual(verify_explanation(result, wl), result.total_cost)

        peak_mib = peak_memory_mib()
        print(f"\n[perf] 100 条 128 字符口令分析耗时 {elapsed:.2f}s，"
              f"进程峰值内存 {peak_mib:.0f} MiB")
        self.assertLess(elapsed, 30.0)
        self.assertLess(peak_mib, 512.0)

    def test_wordlist_capacity_100k(self):
        path = make_wordlist_file([f"word{i:06d}" for i in range(100000)])
        try:
            start = time.perf_counter()
            wl = load_wordlist(path)
            load_elapsed = time.perf_counter() - start
        finally:
            os.unlink(path)
        self.assertEqual(len(wl), 100000)
        self.assertEqual(wl.rank_of("word099999"), 100000)
        analyzer = PasswordAnalyzer(wl)
        result = analyzer.analyze("w0rd000001" * 12 + "w0rd000!")  # 恰好 128 字符
        self.assertEqual(verify_explanation(result, wl), result.total_cost)
        peak_mib = peak_memory_mib()
        print(f"\n[perf] 10 万词条加载耗时 {load_elapsed:.2f}s，"
              f"进程峰值内存 {peak_mib:.0f} MiB")
        self.assertLess(peak_mib, 512.0)


def peak_memory_mib():
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return usage / (1024 * 1024)  # macOS 返回字节
    return usage / 1024  # Linux 返回 KiB


if __name__ == "__main__":
    unittest.main(verbosity=2)
