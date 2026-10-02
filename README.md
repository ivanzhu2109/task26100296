# CyberQuest 离线口令强度演练评分库

纯 Python（仅标准库，Python 3.10+）实现的口令猜测成本评分库，由上层直接调用。
训练词库存于本地 UTF-8 文件，全部分析状态仅保存在内存中，不监听端口、不连接任何外部服务。

## 成本模型

一条**分析方案**把整个口令拆成连续、不重叠的非空片段。若共有 `m` 个片段，
方案成本为 `m!` 乘以各片段成本的乘积。`analyze()` 返回所有合法方案中的
**最小成本**以及一条达到该成本的解释（同成本方案任选其一）。

每个片段按以下三种方式中成本最低者计费（可任意混用）：

- **暴力猜测**：`95 ** 片段长度`。
- **词库匹配**：片段先转小写，允许把 `0→o`、`1→i|l`、`3→e`、`4→a`、`5→s`、`7→t`
  逐字符还原，再选择是否整体反转；所得字符串必须恰好等于某个词库单词。
  成本为 `单词排名 × 2^(大写字母数 + 实际替换字符数 + 反转标记)`，
  反转标记在反转时为 1，否则为 0。多种匹配均为合法候选。
- **重复结构**：片段恰为同一非空单元连续重复 `k` 次（`k >= 2`，按原始字符逐字一致）时，
  成本为 `k × F(单元)`，其中 `F(单元)` 是该单元**单独分析**的最小成本
  （单元内部可继续词库匹配、拆分并适用 `m!` 规则、嵌套重复）。
  所有合法重复单元都是候选，不只考虑最短单元。

成本是精确整数，不是强度等级或数量级。

## 快速开始

```python
from cyberquest import Analyzer, Dictionary, verify_analysis

dictionary = Dictionary.load("words.txt")   # UTF-8，每行一个小写 ASCII 单词
analyzer = Analyzer(dictionary)             # 加载后词库不可变，顺序调用

result = analyzer.analyze("0LL3H")
print(result.cost)                          # 精确最小成本
for seg in result.segments:
    print(seg.method, seg.text, seg.cost)   # 每个片段的计费方式与成本

verify_analysis(result, dictionary)         # 独立复算，不一致则抛 ValueError
```

### 词库文件格式

- UTF-8 编码，每行一个互不重复的小写 ASCII 单词（可含数字与可打印符号，不含大写字母）。
- 行号从 1 开始，即该单词的猜测排名。
- 每条最长 32 字符；重复、空行、含大写或非 ASCII 的行会在加载时抛出 `ValueError`。

### 口令约束

- 仅含 ASCII 码 32 至 126 的可打印字符；大小写和空格均有意义。
- 非空且最长 128 字符（超出时 `analyze()` 抛出 `ValueError`）。

## 解释结构

`analyze()` 返回 `AnalysisResult`：

- `cost`：总成本，等于 `len(segments)! × 各片段 cost 的乘积`。
- `segments`：按顺序覆盖口令每个字符的 `SegmentExplanation` 元组，
  `start`/`end` 为片段在口令中的偏移。

`SegmentExplanation` 按 `method` 分为：

- `brute_force`：`cost == 95 ** len(text)`。
- `dictionary`：`word`（词库原词）、`rank`、`reversed`、`uppercase_count`、
  `substitutions`（每个替换的片段内偏移、原字符、替换后字符）、
  `multiplier`（即 `2 ** 指数`）。
- `repeat`：`unit`、`repeat_count`、`unit_analysis`
  （单元完整分析的 `AnalysisResult`，可递归复算）。

`verify_analysis(result, dictionary=None)` 只依据解释树独立复算总成本，
校验字符覆盖、匹配转换、排名（传入词库时）与重复结构，任何不一致都会抛出
`ValueError`；通过时返回与 `result.cost` 相等的成本。

## 性能

词库加载完成后（10 万条、每条最长 32 字符），单进程分析 100 条互不相同、
长度 128 的口令（含纯随机、大量可替换数字的 leet 口令、多种重复周期的口令）：

- 总耗时约 **10 秒**（预算 30 秒）。
- 进程峰值内存约 **315 MiB**（预算 512 MiB）。

每次 `analyze()` 的分析缓存随调用结束释放，词库本身驻留内存且不可变。

## 运行测试

```bash
python3 -m pytest tests/ -q
```

测试覆盖：

- 短口令与独立穷举枚举（`tests/reference.py`）逐一对比最小成本，
  包括局部最便宜拆分因 `m!` 惩罚而非全局最优的情形；
- 同一数字对应不同单词（`1→i|l`）、反转与大小写及替换叠加的精确成本；
- 较长重复单元因命中高排名词条而优于最短单元；
- 全部解释均经 `verify_analysis` 复算；
- 上述规模下的耗时与内存验收（`tests/test_performance.py`）。
