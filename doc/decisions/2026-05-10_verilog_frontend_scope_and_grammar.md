# 2026-05-10: Verilog 前端解析边界与 BNF 管理

| 字段 | 值 |
|------|----|
| 状态 | accepted |
| 作用范围 | `src/VerilogPreprocess.py`, `src/VerilogLexer.py`, `src/VerilogParser.py`, `src/VerilogAst.py`, `src/verilog.bnf` |
| 输入依据 | `PROJECT.md` 决策 13-18, `doc/review/09_VerilogLexer.md`, `doc/review/10_VerilogParser.md`, `doc/review/11_VerilogPreprocess.md`, `doc/design_verilog_frontend_extension_interfaces.md`, 当前 `src/verilog.bnf` |
| 关联任务 | 后续 Parser 管线重构 TASK |

## 问题

当前 Verilog 前端最初为 VCG 的端口和参数提取服务，因此有意忽略大量完整
Verilog 语法。但这种简化边界没有被清楚写进架构和 BNF，导致实现上同时出现
两类问题：

- 代码只需要 module-level declarations，却在部分地方像完整 parser 一样解析
  body item。
- 遇到不支持或错误语法时，有些路径会跳过、记录日志或返回带错误的 AST，
  下游可能继续生成错误 Verilog。

本决策用于约束后续重构：保留长期扩展方向，但把当前支持子集和 BNF 管理规则
先固定下来。

## 已确认事实

- `Verilog*` 命名需要保留，项目未来可能扩展成更完整的
  Verilog/SystemVerilog parser。
- VCG 当前下游主要消费目标 module 的参数、端口、range、方向和连接所需信息。
- body 内 `parameter` / `localparam` 会影响端口宽度和生成结果，不能从解析范围中
  删除。
- 非声明型 body item，例如 `assign`、module instance、`always`、`generate`，当前
  不需要建 AST。
- `src/verilog.bnf` 当前存在重复、过期和与 `VerilogParser.py` 漂移的规则，不能
  继续作为历史草稿放任不管。

## 当前假设

- 本轮重构不以完整 Verilog/SystemVerilog parser 为验收目标。
- 可以在保持公共模块名和主要 API 稳定的前提下，重构内部数据流和声明建模方式。
- SystemVerilog 支持暂不实现，但数据结构和 BNF 需要给 data type、interface
  port、modport、packed/unpacked dimensions 留扩展空间。

## 决策

1. **保留 `Verilog*` 模块命名**

   不把 `VerilogParser` 重命名为 interface-only 或 module-interface parser。
   当前通过文档和契约说明支持子集，而不是通过改名收窄长期方向。

2. **当前稳定范围是 module-level declaration 子集**

   必须解析：

   - 目标 module header 中的 `parameter` / `localparam`。
   - Verilog-2001 ANSI header 端口声明。
   - Verilog-1995 body 端口声明。
   - module body 内的 `parameter` / `localparam`。
   - 参数默认值、端口 range 和宽度计算所需表达式子集。

   可以跳过但不建 AST：

   - `assign`
   - module instance
   - `always`
   - `generate`
   - 其他非声明型 body item

3. **预处理顺序必须改为整文件上下文优先**

   目标数据流是：

   ```text
   原始文件
     -> 整文件条件编译 / 宏上下文处理
     -> 目标 module 定位
     -> 声明相关文本抽取
     -> lexer/parser
     -> VerilogAst
   ```

   不接受先裁掉 module 前内容再处理条件编译的流程。

4. **声明建模采用 declaration group 思路**

   端口和参数声明应建模为“共享声明属性 + declarator list”，避免把逗号分隔项
   当成互不相关的完整声明。

   这个模型必须覆盖当前场景：

   ```verilog
   input [7:0] a, b
   parameter A = 1, B = 2
   ```

   同时为未来 SystemVerilog 预留：

   ```systemverilog
   logic signed [W-1:0] a, b
   axi_if.master m_axi
   ```

5. **BNF 是当前支持子集规范**

   `src/verilog.bnf` 必须清理成当前支持子集的规范文件，并与
   `VerilogParser.py` 同步维护。暂不支持但未来计划支持的语法，应标为
   future/unsupported，不能混进当前 grammar。

6. **简化实现必须 fail loud**

   在当前支持子集内，如果 preprocess/lexer/parser 记录错误或无法可靠理解输入，
   必须抛 `VCGParseError` 或更具体的 VCG 异常，不能返回看似成功的 AST。

## BNF 重构结果

本决策已同步落到 `src/verilog.bnf`。该文件不再作为历史草稿保存多版 grammar，
而是作为当前 Verilog 前端的规范文件维护。

### 当前 BNF 文件定位

- `src/verilog.bnf` 是 `VerilogPreprocess.py`、`VerilogLexer.py`、
  `VerilogParser.py`、`VerilogAst.py` 的共同规范。
- 它描述当前支持子集和近期待重构目标。
- 它不是完整 Verilog 或 SystemVerilog grammar。
- 后续任何 parser grammar 变更都必须同步检查该文件。

### 当前支持 token

当前 BNF 明确支持这些 token 类别：

- 关键字：`module`、`endmodule`、`input`、`output`、`inout`、`wire`、
  `reg`、`logic`、`parameter`、`localparam`、`assign`。
- 标识符：普通简单标识符。
- 系统标识符：`$clog2` 这类 `$` 开头名称，仅作为表达式函数名使用。
- 宏引用：`` `WIDTH`` 这类 object-like macro reference，作为表达式原文保留。
- 数字：十进制数、based number，目标支持大小写 base、可选 signed marker、
  `x/z/?` 和下划线。
- 字符串：保留为字符串字面量语义，不应和普通 ID 混淆。
- 表达式运算符：算术、比较、逻辑、位运算、移位、三目、括号、拼接等当前
  range/parameter 需要的子集。

### 当前不支持 token

当前 BNF 明确不把这些 token 纳入当前支持子集：

- `.`、`@`、`::`、`->`。
- procedural/generate 相关关键字，例如 `always`、`initial`、`begin`、`end`、
  `generate`、`endgenerate`。
- SystemVerilog interface/package/class/typedef/struct/enum/task/function 相关关键字。
- `signed` / `unsigned` 当前作为 future data model 扩展点，不进入当前 grammar。
- escaped identifier、hierarchical name、package scope name。

这些可以未来支持，但必须通过明确 task、测试和 BNF 更新进入当前 grammar。

### 当前支持 grammar

当前 grammar 只覆盖：

- `design_unit -> module_declaration`。
- module header 中的 parameter port list。
- Verilog-2001 ANSI port declaration group。
- Verilog-1995 port name list + body port declaration。
- body 内 `parameter` / `localparam`。
- parameter default 和 range 所需的 expression subset。

当前 grammar 使用 declaration group 思路：

```text
shared declaration attributes + declarator list
```

这用于修复并规范：

```verilog
input [7:0] a, b
parameter A = 1, B = 2
```

其中 `b` 必须继承 `input [7:0]`，`B` 必须继承 `parameter` 声明上下文。

### 当前不支持 grammar

当前不支持：

- 完整 module instance，特别是命名端口连接 `.a(a)`。
- procedural block：`always`、`initial`、`begin/end`。
- generate block。
- task/function。
- specify、UDP。
- package、class、import、typedef、struct、union、enum。
- 完整 SystemVerilog interface/modport。
- 完整 attribute 语法。
- 完整 macro expansion 和 include 处理。

非声明型 body item 可以在不影响目标 module 和 declaration 边界时跳过，但不能
被误建模进 `VerilogAst`。如果边界不明确，必须失败。

### Partial Preprocessing 规则

本轮特别明确：VCG 的宏环境既用于结构性代码切片，也可能出现在位宽或参数表达式
里。因此预处理不是完整 Verilog macro expansion，而是 partial preprocessing。

支持的结构性指令：

```text
`ifdef
`ifndef
`elsif
`else
`endif
`define
`undef
```

规则：

- 条件编译必须在整文件范围处理，然后再定位目标 module。
- inactive branch 会从 parser 输入中移除。
- active `define` / `undef` 更新宏环境，供后续条件编译判断。
- 指令行本身不作为 Verilog 语法交给 parser。
- 用于位宽、参数默认值、表达式的 object-like macro reference 必须保留原文，
  不展开为值。

必须保留的例子：

```verilog
input [`WIDTH-1:0] data
parameter DEPTH = `DEPTH_DEFAULT
localparam ADDR_W = $clog2(`DEPTH)
```

不支持：

- ``include``。
- ``line``、``timescale``、``default_nettype`` 等非当前目标指令。
- function-like macro expansion。
- token pasting、stringification、nested macro expansion semantics。

注释处理必须区分 code、line comment、block comment、string literal。字符串里的
`//` 或 `/* */` 不能被当作注释。

### Include 与未来 Import 策略

``include`` 和 SystemVerilog `import` 不是同一类机制，后续重构必须分开处理。

#### 当前 ``include`` 策略

``include`` 是预处理期文本包含。当前 partial preprocessing 不打开、不展开 include
文件。

本轮约束：

- active ``include`` 位于目标 module 声明抽取范围之外时，可以被丢弃。
- active ``include`` 位于目标 module header 或 body declaration 子集内时，必须抛
  `VCGParseError`，不能静默忽略。
- 原因：include 文件可能包含端口、参数、宏定义或声明，静默忽略会生成脏 AST。
- 如果 include 里的宏只用于条件编译，当前应由 VCG macro environment 显式传入。
- 未来如果要支持 include，必须单独开任务处理 include path、相对路径解析、循环
  include、最大深度、文件错误和 source location 映射。
- include 文件搜索不能隐式猜 cwd 或工程根目录。未来必须由调用方显式传入
  `include_roots`，resolver 按当前文件目录和 `include_roots` 的文档化顺序搜索。
- 如果多个搜索根或递归搜索命中同一 include spelling，必须报 ambiguity error，不能
  静默选择第一个。

#### 未来 SystemVerilog `import` 策略

SystemVerilog `import` 是语法和名字解析层机制，不是预处理文本替换。

未来约束：

- `import pkg::*;` / `import pkg::name;` 应作为 AST 或解析上下文 metadata 记录。
- 支持 `import` 不等于读取 package 文件；package discovery 属于后续 resolver。
- imported type 出现在端口声明时，短期可先保留 type text，不做完整符号解析。
- 不允许把 `import` 当成 ``include`` 展开，也不允许在预处理阶段删除会影响类型解析
  的 import。
- package 文件搜索同样不能隐式猜 cwd 或工程根目录。未来必须由调用方显式传入
  `package_roots`，resolver 按 package 名或 package index 查找定义。
- 多个 package 定义冲突时必须失败，不能因为文件系统顺序不同而解析出不同结果。

## 不选择的方向

- 不把近期目标扩大成完整 Verilog/SystemVerilog 编译器。
- 不删除 body 内 `parameter` / `localparam` 支持。
- 不通过重命名 `Verilog*` 模块来表达当前解析范围。
- 不继续让 `src/verilog.bnf` 同时保存多版互相冲突的 grammar。

## 影响

- 后续 Parser 管线 task 必须先引用本决策，再定义具体任务范围。
- `VerilogPreprocess` 的重构重点是数据流，而不是继续给字符串裁剪逻辑补特殊分支。
- `VerilogParser` 的重构重点是声明组建模、错误边界和 BNF 同步。
- `VerilogAst` 的重构需要为 SystemVerilog 扩展字段留空间，但不能提前实现未验证的
  完整 SV 语义。
- 下游 `InstanceManager` / `WiresManager` 可以继续消费现有 AST 形状，但后续需要
  校验目标 module 与 AST module name 的一致性。

## 验证要求

后续实现任务至少需要覆盖：

- module 前 ``define`` / include guard 不被提前裁掉。
- 多 module 文件能按目标 module 选择正确模块。
- body 内 `parameter` / `localparam` 被解析并进入 AST。
- `input [7:0] a, b` 中 `b` 继承方向和 range。
- `parameter A = 1, B = 2` 中 `B` 继承参数声明上下文。
- 非声明型 body item 不建 AST，且不污染声明提取。
- 当前支持子集内的 lexer/parser/preprocess 错误会失败，不返回带错误 AST。
- 每次 grammar 变更同步更新 `src/verilog.bnf`。

## 后续处理

- 本决策已提炼进 `PROJECT.md` 的长期决策 13-18。
- 后续具体任务应拆成：
  - BNF 清理与当前子集标注。
  - Preprocess 整文件上下文和目标 module 选择。
  - Parser declaration group 建模。
  - AST 兼容层和 SystemVerilog 扩展字段预留。
  - 错误契约收紧和回归测试。
