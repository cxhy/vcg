# FEEDBACK: TASK-01（T-A 回归）

| 字段 | 值 |
|------|----|
| 来源 | vcg-python-dev |
| 严重性 | blocker（pytest 2 项失败，阻塞验收） |
| 触发任务 | T-A（删除 `_calculate_vector_width` 的 endswith hack） |
| 相关 commit | `829f61c` |

---

## 问题描述

T-A 完成后全量 pytest：**525 passed, 2 failed**。两个失败测试均与
`msb='N-1', lsb='0'` 的表达式化简相关：

```
tests/test_VerilogAst.py::TestParameterExpressions::test_simple_parameter_expression_optimization
tests/test_VerilogAst.py::TestExpressionCalculation::test_parameter_expression_optimization[N-1-0-N]
```

期望：`port.width == 'N'`
实际：`port.width == '(N-1)-(0)+1'`

## 根因分析

sympy 把字母 `N`（以及 `O`、`S`、`Q` 等）当作内置函数/保留名，
`sympify('N-1')` 会抛 `TypeError: unsupported operand type(s) for -: 'function' and 'One'`。
于是 `_sympy_parse` 的 silent fallback 原样返回 `'N-1'`（字符串），
后续 `width_expr = '(N-1)-(0)+1'` 再次 sympify 同样失败，最终返回
整个 `'(N-1)-(0)+1'` 字符串。

**旧 hack 的救赎路径**：
```python
if str(lsb_val) == "0" and str(self.msb_expr).endswith("-1"):
    return self.msb_expr[:-2]
```
正好命中 `msb_expr='N-1', lsb_val=0` → 返回 `'N'`。
hack 对这个 case 是 **load-bearing** 的，不是"死代码"或"坏品味叠加"。

### sympy 保留名实证（uv run python 验证）

| 符号 | `sympify('X-1')` |
|------|-----------------|
| N | ❌ TypeError |
| O | ❌ TypeError |
| S | ❌ TypeError |
| Q | ❌ TypeError |
| E | ✅ `-1 + E`（退化为自然常数 e） |
| I | ✅ `-1 + I`（退化为虚数单位） |
| C | ✅ `C - 1` |
| WIDTH / DATA_WIDTH / ADDR_WIDTH / DEPTH / SIZE | ✅ 正常 |

`N`/`O`/`S`/`Q` 四个单字母 Verilog 参数名是硬冲突；
`E`/`I` 会被 sympy 当作常数符号化简到奇怪结果；
常见的多字母名 `WIDTH` 等不受影响。

## 重申 review 原文的判断

review #1 写的 Linus 金句："sympy 完全能把 `(N-1)-(0)+1` 化简成 `N`"
—— **这句话在 N 字面量遇到 sympy 保留名时不成立**。Linus 漏看了 sympy 的保留名语义。

## 备选修复方向

按侵入性从低到高排序：

### 方向 A：保留 hack 但去掉字符串拼接硬编码（推荐）

把 hack 精确限定到 **"sympy 确实失败时的 fallback"** 且仅处理 `-1 / 0` 经典模式，
并且用 `re` 精确匹配尾部 `-1`（处理 `WIDTH - 1` 带空格）：

```python
def _calculate_vector_width(self) -> Union[int, str, float]:
    if not self.msb_expr or not self.lsb_expr:
        return 1

    msb_val = _calculator.parse_width_expression(self.msb_expr)
    lsb_val = _calculator.parse_width_expression(self.lsb_expr)

    if isinstance(msb_val, int) and isinstance(lsb_val, int):
        return abs(msb_val - lsb_val) + 1

    width_expr = f"({msb_val})-({lsb_val})+1"
    result = _calculator.parse_width_expression(width_expr)

    # sympy 失败时 result 是原样字符串（含括号与 +1），此时 fallback：
    # 对 [X-1:0] 这种最常见的 Verilog 习惯写法做纯字符串化简
    if isinstance(result, str) and str(lsb_val) == "0":
        m = re.fullmatch(r'\s*(.+?)\s*-\s*1\s*', str(self.msb_expr))
        if m:
            return m.group(1)

    return result
```

**优点**：
- `WIDTH-1` 经 sympy 得到 `'WIDTH'`（不走 fallback）
- `WIDTH - 1`（带空格）经 sympy 得到 `'WIDTH'`（不走 fallback）
- `N-1` sympy 失败，fallback 得到 `'N'`（救回来）
- `FOO-1+1` sympy 得 `'FOO'`（不走 fallback；旧 hack 会错误截断为 `'FOO-1+'`，此方案仍正确）
- re 精确匹配避免旧 hack 的 `endswith('-1')` 空格/嵌套问题

**代价**：保留 hack，但被限制在"sympy 真的失败"的 narrow case，且逻辑正确。

### 方向 B：预 symbolize

在 sympify 之前把所有标识符替换为 `sympy.Symbol`：

```python
def _sympy_parse(self, expr):
    # 用 regex 找出所有标识符，创建 symbol dict 注入
    ...
    return sympify(processed, locals=symbol_dict)
```

**优点**：根本解决保留名问题
**代价**：新逻辑较多；`$clog2(X)` 等特殊函数需额外处理；风险高

### 方向 C：修改测试用例

把 `N-1` 改为 `WIDTH-1` 等不冲突的名字。

**致命缺点**：违反验收标准"byte-for-byte 等价"——现实 Verilog 代码里
`N-1` 也是合法参数名（尤其 FIFO `DEPTH=N`, `PTR_WIDTH=$clog2(N)`），
测试删掉只是掩盖回归，用户代码照样会踩。**不推荐**。

## 影响范围

- 本次回归仅影响 T-A，其余 T-B..T-I 改动无关
- 如采纳方向 A，仅需补丁 `PortInfo._calculate_vector_width` 一个方法
- tests/test_VerilogAst.py 不需要改（期望 `'N'` 是合理期望）
- 下游模块行为无变化（width 返回值恢复与旧版一致）
- 与 examples/dma_system.v baseline 的兼容性：dma_system.v 使用 `ADDR_WIDTH-1` / `DATA_WIDTH-1` 等长名，不受影响；但方向 A 能让整个路径更鲁棒

## 建议 architect 决策项

1. 采用方向 A / B / C 哪一个？（推荐 A）
2. 若采方向 A，是否允许把补丁作为 **新 commit T-A-fix** 加到序列末尾，
   还是要求 `git reset --hard` 回到 T-A 之前重做？
3. review #1 的"删整个 if 分支"结论是否需要调整为"替换成 narrow fallback"，
   并记入 doc/decisions/2026-04-25_*.md？

## 当前 dev 状态

- T-A..T-I 已全部 commit（6 个 commit 在 `refactor/code-cleanup` 分支上）
- pytest: 525 passed, 2 failed（仅 T-A 相关）
- **dev 暂停**，等待 architect 决策后继续产出 delivery 文档

---

> 遵守任务约束 #7：不自行决断，等待架构师回复。
