# vcg_wires_manager.py Review

> 评审日期: 2026-04-21
> 评审人: Linus (代理)
> 文件路径: src/vcg_wires_manager.py
> 文件规模: 209 行

## 品味评分
🟡 凑合

整体不算垃圾，至少 209 行单一职责清楚、没什么 4 层嵌套地狱。但是有几处典型的"用 if 补丁掩盖坏数据结构"的味道，特别是宽度格式化和异常阶梯。距离"好品味"差一次重构。

## 核心判断

✅ 值得保留并清理：模块职责单一，与 `vcg_instance_manager.py` 的结构相似性说明这是一类稳定的"resolve → format"套路。但 `_format_wire_width` 必须重写，`generate_wires_def` 的 except 阶梯必须砍掉冗余分支，`_is_multi_dimensional` 这种基于字符串嗅探的实现是定时炸弹。

## 关键洞察

- **数据结构**: `width` 在系统里被表达为四种不同的东西——`int`、纯数字字符串、`[N-1:0]` 已格式化字符串、表达式字符串、甚至多维 `[A][B]`。一个字段五种语义，所有的 if 分支都是为了弥补这个"上游不愿统一类型"的债。真正的修复不在本文件，而是上游 `PortInfo.width` / `RuleManager.resolve_wire_generation` 的返回类型应该明确。
- **复杂度**: 文件本身复杂度不高，但 `_format_wire_declaration` 的"对齐 spacing 计算"和 `_format_wire_width` 的"5 个互斥分支"是熵的来源。spacing 这种纯展示逻辑应该剥离出去。
- **风险点**: (1) `_is_multi_dimensional` 用 `'][' in width_str` 嗅探，碰到 `"[7:0] [3:0]"`（中间有空格）就漏判；(2) `except Exception` 把所有真 bug 都包成 `VCGParseError`，未来调试地狱；(3) `_format_wire_declaration` 里 `port.range_string` 真假判断和 `port.width` 取值之间的耦合假设很脆——如果 `width` 是空但 `range_string` 非空，就会调 `_format_wire_width(port.width)` 拿到空字符串，又走回 prefix="wire" 分支。

## 致命问题（按严重度）

### P0

**1. `vcg_wires_manager.py:81-83` —— `except Exception` 捕获并包装成 `VCGParseError` 是错的**

```python
except Exception as e:
    self.logger.error(f"Wire generation failed: {e}")
    raise VCGParseError(f"Generate Wire Error: {e}")
```

这违反 CLAUDE.md 自己写的"不用通用 except Exception 吞掉有语义的异常"。`AttributeError`、`KeyError`、`TypeError` 全部被伪装成"解析错误"，调试时没人能找到真凶。同样的问题在 `vcg_instance_manager.py` 也存在——这是项目级反模式。

更糟的是 `vcg_wires_manager.py:74-80` 的 except 阶梯：

```python
except FileNotFoundError:        # 已经在 _parse_verilog_file 转成 FileNotFoundError 了
    raise VCGFileError(...)      # 然后又转成 VCGFileError —— 转来转去
except ValueError:               # 让 ValueError 穿透，但 _generate_single_wire 里没有 ValueError，只 generate_wires_def 入口的 pattern 校验抛
    raise
except VCGParseError:            # 已经是 VCG 异常了，re-raise 是对的
    raise
except Exception as e:           # 兜底，把真 bug 全部杀死
    raise VCGParseError(...)
```

四层 except 中两层是冗余的。`pattern` 校验完全可以让 `ValueError` 直接抛出去，调用者自己处理。`Exception` 兜底应该删除。

### P1

**2. `vcg_wires_manager.py:191-202` —— `_is_multi_dimensional` 字符串嗅探脆弱**

```python
if dimension_count >= 2:
    if '][' in width_str:
        ...
        return True
return False
```

判断"多维数组"靠 `'][' in width_str`：

- `"[7:0][3:0]"` → True ✓
- `"[7:0] [3:0]"` → False ✗（中间一个空格就挂）
- `"[7:0]\t[3:0]"` → False ✗
- `"[FUNC()][3:0]"` → True ✓ 但里面带嵌套括号就开始模糊

这种"基于上游恰好不会插入空格"的隐式契约是定时炸弹。要么用正则 `re.search(r'\]\s*\[', width_str)`，要么真正解析（既然 `width` 来自 AST，为什么不让 AST 给一个结构化的 `dimensions: list[Range]`？）。

**3. `vcg_wires_manager.py:164-189` —— `_format_wire_width` 是经典的"if 阶梯打补丁"**

5 个互斥分支处理同一个字段的 5 种语义：

```python
if isinstance(width_input, int): ...
if self._is_multi_dimensional(width_str): ...
if width_str.startswith('[') and width_str.endswith(']') and width_str.count('[') == 1: ...
if width_str.isdigit(): ...
if any(op in width_str for op in ['+', '-', '*', '/', '(', ')']): ...
else: ...
```

这是 Linus 教科书式的"特殊情况处理"。根本问题不在这个函数，在于 `width` 这个字段在系统里没有一个明确类型。理想情况下应该有一个 `WireWidth` ADT/Union：

```python
@dataclass(frozen=True)
class ScalarWidth: pass
@dataclass(frozen=True)
class FixedWidth: bits: int
@dataclass(frozen=True)
class RangeWidth: msb: str; lsb: str
@dataclass(frozen=True)
class MultiDimWidth: dims: tuple[RangeWidth, ...]
```

然后 `_format_wire_width(w: WireWidth) -> str` 用单个 `match`，每个 case 一行。所有的 `isdigit()`、`startswith('[')`、`'][' in ...` 这些字符串嗅探全部消失。

### P2

**4. `vcg_wires_manager.py:138-162` —— `_format_wire_declaration` 三件事混在一起**

这个函数在做：(a) 决定宽度字符串，(b) 计算列对齐 spacing，(c) 拼接最终声明。其中 (b) 是纯展示逻辑，应该独立成 `_pad_to_column(prefix: str, column: int) -> str`。当前 `_BASE_SPACING` 这个名字也不准——它实际上是"wire 关键字+宽度"列后的目标列宽，应该叫 `_NAME_COLUMN`。

**5. `vcg_wires_manager.py:138-143` —— `width` 与 `port.range_string` / `port.width` 的耦合是隐式的**

```python
if width:
    width_str = self._format_wire_width(width)
elif port.range_string:
    width_str = self._format_wire_width(port.width)
```

为什么不统一为"如果 rule 给了 width 用 rule，否则 fallback 到 port"？现在的写法把"port 是否有宽度"分散成两个判断（`port.range_string` 和 `port.width`），如果某天 `range_string` 非空但 `width` 是 `None` 或 `0`，就会静默走到 `width_str = ""` 分支。建议直接：

```python
effective_width = width or port.width
width_str = self._format_wire_width(effective_width) if effective_width else ""
```

**6. `vcg_wires_manager.py:40` —— `VerilogParser` 在 `__init__` 里实例化、生命周期跨多次调用**

`generate_wires_def` 可能被同一个 `WiresManager` 调用多次解析不同文件。`VerilogParser` 内部如果有状态（`parse_errors` 属性已经暗示有），重用会出问题。检查一下 `parser.parse_file` 是否会重置内部状态——如果不会，这是隐患。

**7. `vcg_wires_manager.py:121-134` —— `_generate_single_wire` 的 lazy/greedy 决策分支可以简化**

逻辑上其实是个 2x2 表（rule_matched × wire_name_empty）乘上 pattern。可以重写成：

```python
if pattern == 'lazy' and not rule_matched:
    return ""
if not wire_name or not wire_name.strip():
    if rule_matched:
        return ""  # rule 显式返回空，尊重
    if pattern == 'greedy':
        wire_name = port_name
    else:
        return ""  # 已被前面 lazy+!matched 拦截，理论上不可达
```

注意第二个 `else` 分支理论上死代码——`pattern == 'lazy' and not rule_matched` 已经在函数开头返回了。这种"防御性死代码"也是品味差的标志。

**8. `vcg_wires_manager.py:24` —— `import re` 没用上**

整个文件没有调用 `re`。要么删掉，要么真的用 `re` 把 `_is_multi_dimensional` 写好。

## Linus 式改进方向

1. **删 `except Exception`，让真 bug 暴露**。`generate_wires_def` 的 except 阶梯砍到只剩 `FileNotFoundError → VCGFileError` 一条，其余让 `VCGParseError` / `VCGRuntimeError` / `ValueError` 自然向上传。

2. **把 `width` 提升为 ADT**。这是治本之策。在 `VerilogAst` 或 `vcg_rule_manager` 层定义 `WireWidth` 类型，下游（本文件、`vcg_instance_manager`）直接 pattern match。`_format_wire_width` 从 30 行 5 分支砍到 10 行 5 个 case，再无字符串嗅探。

3. **`_is_multi_dimensional` 立即改成 `re.search(r'\]\s*\[', width_str)`**。这是最低成本的止血。

4. **`_format_wire_declaration` 拆成两个函数**：`_compose_declaration(prefix, name, expr)` 和 `_pad_prefix(prefix, target_col)`。展示和组合分离。

5. **删掉 `import re` 或使其名副其实**。

6. **审计 `VerilogParser` 复用安全性**。如果 `parse_errors` 在跨文件调用时累积，要么每次重建 parser，要么在 `_parse_verilog_file` 开头 reset。

7. **删除 `_generate_single_wire` 里的死代码 else 分支**，加一行注释或 `assert` 说明前置条件。

底线：本文件不是垃圾，但停留在"能跑就行"的层级。要进入"好品味"区，至少要做掉 P0 + P1。P0 不修，未来某天调试这个模块的人会用一种你听不懂的语言诅咒你。
