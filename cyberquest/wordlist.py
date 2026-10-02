"""训练词库：加载、校验与带 leet 替换规则的字典匹配。"""
from __future__ import annotations

# 数字 -> 可还原的字母
LEET_MAP: dict[str, tuple[str, ...]] = {
    "0": ("o",),
    "1": ("i", "l"),
    "3": ("e",),
    "4": ("a",),
    "5": ("s",),
    "7": ("t",),
}

# 可作为 leet 还原目标的字母集合
TARGET_LETTERS: frozenset[str] = frozenset("oileast")

MAX_WORD_LENGTH = 32

# 词库单词只含可打印 ASCII，用不可打印字符作通配符不会冲突
_WILD = "\x00"
_TERMINAL = "\x01"


def _skeleton(word: str) -> str:
    """单词的匹配骨架：可被数字替换的字母位置记为通配符。"""
    return "".join(_WILD if ch in TARGET_LETTERS else ch for ch in word)


class Wordlist:
    """一次加载后保持不变的词库。行号（从 1 开始）即猜测排名。"""

    def __init__(self, words: list[str]) -> None:
        self._words: tuple[str, ...] = tuple(words)
        self._ranks: dict[str, int] = {
            word: index + 1 for index, word in enumerate(self._words)
        }
        # 字典树：节点为 dict，子边键为骨架字符，_TERMINAL 键保存
        # 按排名升序的 (rank, word) 列表。
        self._trie: dict = {}
        for word in self._words:
            node = self._trie
            for ch in _skeleton(word):
                node = node.setdefault(ch, {})
            rank = self._ranks[word]
            node.setdefault(_TERMINAL, []).append((rank, word))

    def __len__(self) -> int:
        return len(self._words)

    @property
    def words(self) -> tuple[str, ...]:
        return self._words

    def rank_of(self, word: str) -> int:
        """返回单词排名（1 起）；不在词库中抛出 KeyError。"""
        return self._ranks[word]

    def best_match(self, transformed: str, limit: int | None = None):
        """在已小写（且按需已反转）的字符串上寻找最优词库匹配。

        返回 (rank, word, substitutions) 或 None；substitutions 为
        需要把数字替换为字母的字符数。仅考虑 rank * 2**substitutions
        严格小于 limit 的匹配；多个候选中取该值最小者。
        """
        best_value = limit
        best = None
        length = len(transformed)
        stack = [(self._trie, 0)]
        while stack:
            node, pos = stack.pop()
            if pos == length:
                entries = node.get(_TERMINAL)
                if entries:
                    for rank, word in entries:
                        if best_value is not None and rank >= best_value:
                            break  # 列表按排名升序，之后不可能更优
                        substitutions = 0
                        compatible = True
                        for have, want in zip(transformed, word):
                            if have != want:
                                targets = LEET_MAP.get(have)
                                if targets is None or want not in targets:
                                    compatible = False
                                    break
                                substitutions += 1
                        if not compatible:
                            continue
                        value = rank << substitutions
                        if best_value is None or value < best_value:
                            best_value = value
                            best = (rank, word, substitutions)
                continue
            ch = transformed[pos]
            if ch in TARGET_LETTERS:
                # 字母只能原样匹配单词中同一字母（骨架通配位）
                child = node.get(_WILD)
                if child is not None:
                    stack.append((child, pos + 1))
            else:
                if ch in LEET_MAP:
                    # 数字可还原为字母（骨架通配位）……
                    child = node.get(_WILD)
                    if child is not None:
                        stack.append((child, pos + 1))
                # ……或原样匹配单词中的同一字符
                child = node.get(ch)
                if child is not None:
                    stack.append((child, pos + 1))
        return best


def _validate_word(word: str, lineno: int) -> None:
    if not 1 <= len(word) <= MAX_WORD_LENGTH:
        raise ValueError(
            f"第 {lineno} 行：单词长度须为 1..{MAX_WORD_LENGTH}，实际 {len(word)}"
        )
    for ch in word:
        code = ord(ch)
        if code < 32 or code > 126:
            raise ValueError(f"第 {lineno} 行：单词含非可打印 ASCII 字符 {code}")


def load_wordlist(path: str) -> Wordlist:
    """从 UTF-8 文件加载词库：每行一个互不重复的小写 ASCII 单词。"""
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()
    words: list[str] = []
    seen: set[str] = set()
    for lineno, word in enumerate(content.splitlines(), start=1):
        _validate_word(word, lineno)
        if word in seen:
            raise ValueError(f"第 {lineno} 行：单词 {word!r} 重复")
        seen.add(word)
        words.append(word)
    return Wordlist(words)
