# src/vcg_wires_manager.py Linus 风格技术评审

评审日期: 2026-05-10
评审范围: `src/vcg_wires_manager.py`。只读 `CLAUDE.md`、`PROJECT.md`、`doc/MANUAL.md`、调用处、`VCGRuleManager`、Parser/AST 契约和相关测试；未修改源码，未提交 git。

## 品味评分

黄牌，凑合偏危险，5/10。

这个文件表面上很整齐：函数短，缩进浅，异常透传也比一把 `except Exception` 强。但好代码不是把烂逻辑拆成小函数。这里最大的问题是数据契约没想清楚：`module_name` 传进来却不用，`PortInfo.width` 被当成声明 range，`RuleManager` 已经做出的“不生成”决策又被本文件改写。代码生成器最怕这种东西：不崩，直接生成看起来像真的错 Verilog。

## 核心判断

不值得保留现状。应该修，而且不需要大重构。

`WiresManager` 的本质只有一句话：解析目标模块端口，按规则决定哪些端口需要 wire，并渲染声明。当前实现把“目标模块是谁”、“是否应该生成 wire”、“wire 的声明形态”这三件事分散在字符串和布尔值里猜。先把这三条契约收紧，代码会更少，行为也更可信。

## Linus 三问

1. 这是真问题吗？

是。`WiresDef("foo.v", "bar")` 是用户直接写的 public DSL。现在 `bar` 只出现在日志里，解析出来什么模块就给什么模块生成 wire。另一个真问题是 greedy 模式会把下游明确跳过的端口又兜底生成回来。

2. 有更简单的方法吗？

有。AST 已经有 `module_name`，端口已经有 `range_string`，`RuleManager.resolve_wire_generation()` 已经根据 greedy/lazy 返回了最终名字。不要新建框架，不要搞 WireWidth 类型系统第一阶段；先使用已经存在的数据，不要重新猜。

3. 会破坏什么吗？

会破坏一种坏兼容：有人可能把 `module_name` 当无效占位符，或者依赖 greedy 模式给所有东西硬生成 wire。但手册写的是“目标模块名称”，`RuleManager` 也已经有“interface 不生成 wire”的意图。继续保护这些行为，就是保护 silent wrong code。

## 关键洞察

- 数据结构: `PortInfo.width` 是语义宽度，`PortInfo.range_string` 才是 Verilog 声明文本；`wire_name == ""` 和 `rule_matched == False` 被用来同时表示“没匹配规则”和“不要生成”，这是脆弱契约。
- 复杂度: 当前复杂度不是函数太长，而是同一决策做了两遍。`RuleManager` 决定一次，`WiresManager` 再用 greedy/lazy 分支重判一次。
- 风险点: 错误不会在 VCG 层暴露，而是在后续仿真、综合、lint 阶段才暴露，甚至可能完全不报错但连接语义变了。

## 按严重度排序的问题

### P0: `module_name` 是假参数，目标模块契约没有生效

位置: `src/vcg_wires_manager.py:45-60`

`generate_wires_def(file_path, module_name, ...)` 接收模块名，但整个函数只在日志里使用它：

```python
ast = self._parse_verilog_file(file_path)
ports = self._get_ports_by_direction(ast, port_direction)
```

这意味着：

```python
WiresDef("uart.v", "uart_core", "input")
```

并不会确认 `uart.v` 里解析出来的模块真的叫 `uart_core`。如果文件错了、模块名改了、或者未来 Parser 支持多 module 文件，这里都会静默给错误对象生成 wire。手册把第二个参数定义成“目标模块名称”，不是日志标签。

最小修法：解析后立即校验 `ast.module_name == module_name`。不一致就抛 VCG 自家异常。多模块支持应该由 Parser 提供按模块名选择 AST 的能力，不能让 WiresManager 假装已经支持。

### P1: greedy 模式会覆盖下游的“不要生成 wire”决策

位置: `src/vcg_wires_manager.py:121-132`

本文件调用：

```python
wire_name, width, expression, rule_matched = self.rule_manager.resolve_wire_generation(port, pattern)
```

但随后又自己做兜底：

```python
if not wire_name or not wire_name.strip():
    if rule_matched:
        return ""
    wire_name = port_name
```

问题是 `resolve_wire_generation()` 已经收到 `pattern`，也已经知道 greedy/lazy。它返回空名字且 `rule_matched=False` 不一定表示“没匹配规则所以请默认生成”。在当前 `VCGRuleManager` 里，interface port 就会走“不应生成 wire”的路径。结果到了这里，greedy 模式又把它变成 `wire <interface_port>;`。

这就是坏接口的典型症状：调用方不相信被调用方的结果，自己再猜一次。

最小修法：让 `RuleManager` 成为唯一生成决策来源。greedy 无规则时它已经应该返回端口名；WiresManager 看到空 `wire_name` 就跳过。更好的下一步是把四元组换成明确对象，例如 `WireGeneration(name, width, expression, should_emit)`，别靠空字符串和布尔值编码语义。

### P1: 位宽声明用错数据源，丢失原始 range 方向

位置: `src/vcg_wires_manager.py:143-150`, `src/vcg_wires_manager.py:170-190`

没有 rule width 时，代码用的是：

```python
return getattr(port, "width", None)
```

然后 `_format_wire_width()` 把宽度数值重新渲染成 `[N-1:0]`。这对普通 `[7:0]` 没问题，但对真实 Verilog 声明不是等价变换。

例子：

```verilog
module m(input [0:7] data); endmodule
```

AST 的 `width` 是 `8`，但声明文本是 `[0:7]`。当前会生成：

```verilog
wire [7:0]     data;
```

这改变了索引方向。对整线连接可能暂时不炸，但代码生成器不应该随便改用户的位序表达。参数化 range 也一样：`[0:WIDTH-1]` 不应该被重写成 `[WIDTH-1:0]`。

最小修法：端口自身宽度优先使用 `port.range_string`。只有 rule 显式传入 `width` 时，才把它当“宽度计数或 range 文本”格式化。

### P2: 数组端口的数据模型会渲染成垃圾

位置: `src/vcg_wires_manager.py:147-150`, `src/vcg_wires_manager.py:181-190`

`_format_wire_width()` 支持 `"[7:0][3:0]"` 这种多维文本，但 `_resolve_effective_width()` 从真实 `PortInfo` 取的是 `port.width`。而 `PortInfo.width` 对 array 类型返回的是字符串 `"array"`。所以一旦真实数组端口进入这里，结果会是：

```verilog
wire [array-1:0] name;
```

这个多维支持只对“rule 手工传进来的 width 字符串”有效，对真实 AST 端口无效。问题还是同一个：声明文本和语义宽度混在一起。

修法同 P1：从端口生成声明时使用 `range_string`，并明确是否支持 unpacked array wire。不能支持就跳过或报错，不要生成假 range。

### P2: 输出标识符完全不校验，错误定位会被推到 Verilog 工具

位置: `src/vcg_wires_manager.py:127-134`, `src/vcg_wires_manager.py:152-163`

`wire_name` 来自规则或端口名，然后原样拼进 Verilog：

```python
return f"{prefix}{spacing}{wire_name};"
```

VCG DSL 是可信 Python，这不是安全漏洞。但这是糟糕的代码生成器边界：规则写错成 `"bad name"`、空白、换行、分号，VCG 不报，后面 Verilog parser/lint 再报一堆离源头很远的错误。

最小修法：对普通 identifier 做最小校验，至少拒绝空白和明显会打断声明的字符。如果要支持 escaped identifier，显式支持，不要任意字符串透传。

### P3: `pattern` 决策散落两处，测试还固化了错误 mock 契约

位置: `src/vcg_wires_manager.py:101-134`

`_validate_pattern()` 在本文件，`resolve_wire_generation()` 也接收 `pattern`，然后 `_generate_single_wire()` 又根据 `pattern` 分支。这个设计让测试很容易 mock 出真实 `RuleManager` 不会返回的组合，例如 greedy + no rule 返回 `None`，再要求 WiresManager 自己兜底。

这不是立即炸的 bug，但它会持续制造误导性测试。正确方向是：`RuleManager` 决定生成结果，`WiresManager` 只渲染结果。不要把策略拆成两个半边。

## 改进方向

1. 先修契约，不要先重构。

   `generate_wires_def()` 解析后校验 `ast.module_name`。不一致就失败。代码生成器宁可早失败，也不要生成错东西。

2. 把生成决策收敛到一个地方。

   `resolve_wire_generation(port, pattern)` 返回什么，WiresManager 就尊重什么。空名字就是不输出。greedy 的默认端口名由 RuleManager 返回，不要在 WiresManager 里补第二套逻辑。

3. 区分“声明 range”和“宽度计数”。

   端口默认声明用 `port.range_string`；rule width 才走 `_format_wire_width()`。这一步能同时解决 `[0:7]` 被翻转和 array 变成 `[array-1:0]` 的问题。

4. 加最小输入/输出校验。

   `module_name` 校验目标模块，`wire_name` 校验基本 Verilog identifier。不要让低级拼写错误穿透到后端工具才暴露。

5. 补测试要测真实契约。

   至少补四类：模块名不匹配失败；greedy 下 interface/显式 skip 不生成；`[0:7]` range 原样保持；array 端口不生成垃圾声明。别再用不符合真实 `RuleManager` 合同的 mock 返回值定义行为。

## 结论

这个文件不是需要大拆的烂摊子，但现在的“整洁”是表面整洁。真正的问题是三个核心语义没有落在数据结构上：目标模块、生成决策、声明 range。修这些，比继续拆小函数有用得多。
