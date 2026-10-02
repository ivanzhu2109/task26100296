# CyberQuest 离线口令强度演练评分库

用统一、可解释的猜测成本衡量口令强度：不只检查字符种类，而是找出口令中
可预测的结构（词库单词、leet 替换、反转、大小写、重复模式），给出所有合法
分析方案中的**最小猜测成本**以及一条可独立复算的解释。

纯 Python 实现，无第三方依赖；词库存于本地 UTF-8 文件，分析状态仅保存在
内存中，不启动任何网络服务。

## 计费规则

一条分析方案把整个口令拆成连续、不重叠的非空片段。若共有 `m` 个片段，
方案成本为 `m!`（片段数的阶乘）乘以各片段成本的乘积。最终结果是所有合法
方案中的最小成本。每个片段可按三种方式计费，任意混用：

- **暴力猜测**：成本为 `95 ** 片段长度`（ASCII 32..126 共 95 种可打印字符）。
- **词库匹配**：片段先转小写，允许把 `0→o`、`1→i/l`、`3→e`、`4→a`、
  `5→s`、`7→t` 逐字符还原（也可保留数字），再选择是否整体反转；所得字符串
  恰好等于某个词库单词时，成本为 `单词排名 * 2**指数`，指数 = 原片段大写
  字母数 + 实际替换字符数 + 反转标记（反转为 1，否则 0）。
- **重复结构**：片段恰为同一非空单元连续重复 `k` 次（`k >= 2`）时，成本为
  `k * 单元单独分析的最小成本`。单元内部可继续拆分、匹配词库或嵌套重复；
  所有合法单元（不只最短单元）都是候选。

## 快速开始

```python
from cyberquest import PasswordAnalyzer, load_wordlist, verify_explanation

wordlist = load_wordlist("words.txt")        # 每行一个小写 ASCII 单词，行号即排名
analyzer = PasswordAnalyzer(wordlist)        # 或 PasswordAnalyzer.from_file("words.txt")

result = analyzer.analyze("P4ssw0rdP4ssw0rd")
print(result.total_cost)                     # 最小猜测成本（精确整数）

# 调用方可独立复算总成本；解释不自洽时抛出 ExplanationError
assert verify_explanation(result, wordlist) == result.total_cost
```

约束：词库单词每行一个、互不重复、长度 1..32、可打印 ASCII；口令长度
1..128、仅含 ASCII 32..126（大小写与空格均有意义）。违反时抛出
`ValueError`。

## 解释结构

`analyze` 返回 `PasswordExplanation`：

- `segments`：连续覆盖整个口令的 `SegmentExplanation` 元组，每个片段给出
  `method`（`"brute"` / `"dictionary"` / `"repeat"`）与 `cost`；
- `segment_count` / `factorial_multiplier`：片段数 `m` 与 `m!`；
- `total_cost`：`m!` 乘以各片段成本之积。

词库匹配片段记录命中的 `word`、`rank`、逐处 `substitutions`（位置、数字、
字母）、`reversed`、`uppercase_count` 与 `exponent`；重复片段记录
`repeat_count`、`unit` 以及单元内部的完整 `unit_explanation`
（递归的 `PasswordExplanation`，偏移相对于单元自身）。因此每个字符如何被
计费都可逐级核对。

## 运行测试

```bash
python3 -m pytest tests/ -q        # 或 python3 -m unittest discover -s tests -v
```

测试覆盖：短口令与独立穷举参照逐一比对最小成本；局部最便宜拆分因片段数
阶乘惩罚而非全局最优；同一数字对应不同单词；反转与大小写、替换叠加；较长
重复单元命中词条优于最短单元；解释复算与篡改检测；以及下述规模验证。

## 性能验证（本机实测）

- 2 万词条词库，100 条互不相同、长度 128 的口令（含纯随机、大量可替换
  数字、多种重复周期与混合结构）：分析总耗时约 **5.2s**（预算 30s），进程
  峰值内存约 **74 MiB**（预算 512 MiB）；
- 10 万词条词库加载约 **0.2s**，峰值内存约 **106 MiB**。

## 实现要点

- 词库匹配用「骨架字典树」索引：可被数字替换的字母位置记为通配符，查找时
  数字可走通配（计一次替换）或原样两条边，避免枚举指数级替换组合；
- 主动态规划按前缀维护「片段数、片段成本积」的帕累托前沿（片段数更少且
  成本积更小的状态支配其余状态），最后对前沿取 `m! * 成本积` 的最小值并
  回溯出一条最优拆分；
- 重复单元的最优分析按字符串内容记忆化，重复结构大量出现时不会重复计算；
- 所有成本为精确整数，中间状态以 `95**128`（整体暴力成本）为上界截断，
  不影响最优解。
