# Verilog Parser Component Refactor Plan

| Field | Value |
|------|-------|
| Scope | `VerilogPreprocess` / `VerilogLexer` / `VerilogParser` / parser-facing `VerilogAst` contracts / `src/verilog.bnf` |
| Out of scope | `vcg_instance_manager.py`, `vcg_wires_manager.py`, `vcg_rule_manager.py`, CLI and VCG block execution |
| Progress source | `doc/parser_refactor_tasks.json` |
| Status | draft_for_user_review |
| Created | 2026-05-11 |

## Goal

把当前 Verilog 解析器组件重构成一个边界清晰、失败语义可信、声明建模正确、
文件职责干净的前端组件。近期目标仍是 VCG 需要的 module-level declaration
子集，不把范围扩大成完整 Verilog/SystemVerilog 编译器。

最终状态必须满足：

- Preprocess / Lexer / Parser 任一阶段发现当前支持子集内无法可靠理解的输入时，
  抛 `VCGParseError` 或更具体的 VCG 异常，不能返回脏 AST。
- Lexer token 契约明确：关键字大小写敏感，数字/字符串/系统函数/宏引用的
  `type` 与 `value` 语义稳定。
- Parser grammar 使用 declaration group 模型，正确处理
  `input [7:0] a, b` 与 `parameter A = 1, B = 2`。
- Parser 不再半吊子解析或吞掉非声明型 body item。Preprocess 已负责裁剪声明
  子集，Parser 只解析该子集。
- AST Builder 的 parser-facing API 不再依赖散乱 `dict` 与宽松 `**kwargs` 核心路径。
- `src/verilog.bnf` 与真实 grammar 同步，作为当前支持子集规范。
- 解析器相关文件保持单一职责；单文件小于 800 行，函数小于 50 行。

## Current Baseline

已完成的前置工作：

- `TASK-09` 已重构 `VerilogPreprocess` 数据流。
- 当前 `VerilogPreprocess` 支持整文件条件编译、目标 module 选择和声明抽取。
- 最新验证记录为 `696 passed`。
- `src/verilog.bnf` 已从历史草稿整理为当前支持子集规范。

当前主要风险：

- `VerilogLexer.t_error()` 仍会记录日志并跳过非法字符。
- `VerilogParser.parse_string()` 仍可能在 `parse_errors` 非空时返回 AST。
- Lexer 关键字匹配使用 `lower()`，违反 Verilog 大小写敏感规则。
- Based number 规则不完整，部分合法 Verilog 数字会被拆成多个 token。
- ANSI header 端口声明组和 header 参数声明组仍未正确建模。
- Parser 仍包含吞掉 `assign` / positional instance 的 grammar 分支。

## JSON Progress Protocol

`doc/parser_refactor_tasks.json` 是本轮 parser 重构的唯一机器可读进度源。
每个任务执行时必须遵守：

1. 开始任务前，将任务状态改为 `in_progress`，并填写 `started_at`。
2. 开发交付后，将状态改为 `delivered_for_verification`，填写：
   - `delivery_doc`
   - `changed_files`
   - `validation.commands`
3. Tester 验证后，将状态改为 `verified` 或 `blocked`，填写：
   - `verification_doc`
   - `validation.results`
   - `blockers`
4. 如果任务影响 AST 语义、parser grammar 或生成 Verilog 的下游输入，必须写
   `check_doc`，再把状态推进到 `checked`。
5. 任务完全闭环后，将状态改为 `done`，填写 `completed_at`。
6. 每次状态变化都必须追加一条 `history` 记录，包含时间、角色、动作和证据。

允许状态：

```text
pending -> in_progress -> delivered_for_verification -> verified -> checked -> done
pending -> blocked
in_progress -> blocked
delivered_for_verification -> blocked
verified -> done
checked -> done
```

如果后续发现任务拆分错误，不删除历史任务；改为 `superseded`，并在
`superseded_by` 指向新任务。

## Per-Task Role Handoff Protocol

每个 task 必须按文档交接推进，不允许直接从总计划跳到代码修改。

1. **Architect phase**

   `vcg-architect` 写 `doc/task_<NN>_<slug>.md`。该文档必须列出：

   - 需要重构的功能点。
   - 当前问题和证据。
   - 当前不做的边界。
   - 接口约束。
   - 验收标准。
   - 验证关注点。

   写完后，`doc/parser_refactor_tasks.json` 中对应 task 状态进入
   `pending_user_review`。用户确认前不进入设计或实现。

2. **Design phase**

   用户确认 task 文档后，设计角色写 `doc/design_<NN>_<slug>.md`。该文档必须把
   architect 功能点逐项映射到具体设计，说明文件结构、数据结构、错误流、
   测试设计和兼容策略。

3. **Delivery phase**

   设计确认后才进入实现。实现完成后写 `doc/delivery_<NN>_<slug>.md`，记录实际
   改动文件、偏离设计之处和已运行命令。

4. **Verification phase**

   验证角色读取 task/design/delivery 文档，逐项确认 architect 功能点是否完成。
   通过时写 `doc/verification_<NN>_<slug>.md`；不通过时写
   `doc/feedback_<NN>_<slug>.md`，并把 JSON 状态设为 `blocked`。

5. **Architect check phase**

   `vcg-architect` 读取验证结果，检查范围、接口、BNF 和长期决策是否一致。
   需要生成 Verilog 或 AST 语义检查时，写 `doc/check_<NN>_<slug>.md`。

6. **User closeout phase**

   架构师检查通过后，状态进入 `pending_user_final_confirmation`。用户确认后才能
   提交并把当前 task 标为 `done`。

在 Codex 当前会话中，除非用户明确要求并行 agent/subagent，否则这些角色由主会话
顺序执行，但文档边界必须保持。

## Unsupported-Today Token Policy

TASK-10 不把 `@`、`.` 等未来可能支持的 Verilog 字符定义成“永远非法”。本轮策略是：

- **非法输入**：当前语言和未来扩展都不应接受的字符或坏字节。
- **unsupported token**：Verilog 里有意义，但当前 module-level declaration 子集
  不支持的字符或 token，例如 procedural sensitivity list 中的 `@`、命名端口连接
  中的 `.`。
- Lexer 不能静默删除 unsupported token；必须记录 diagnostic，保留原始字符、
  行号、列号和上下文。
- Parser 在最终返回 AST 前检查 diagnostics。只要存在 error 级 diagnostic，就抛
  `VCGParseError`。
- 未来扩展支持 `always @(...)` 时，只需要把 `@` 从 unsupported diagnostic 改成
  `AT` token 并补 grammar；诊断模型和 fail-loud 边界不需要重写。

因此，TASK-10 中的 `@` 测试不是在宣称 `@` 不属于 Verilog，而是在验证：

```text
当前子集不支持的源码不能被 lexer 删除后继续生成 AST。
```

## Target File Structure

本计划允许新增小文件，避免把 `VerilogParser.py` 继续堆成单体。

| File | Responsibility |
|------|----------------|
| `src/VerilogDiagnostics.py` | Source location、frontend diagnostic、lex/parse error 汇总模型。 |
| `src/VerilogTokens.py` | Token 分类、literal spelling 策略、数字/字符串 helper。 |
| `src/VerilogDeclarations.py` | Parser 内部 declaration group / declarator dataclass。 |
| `src/VerilogLexer.py` | PLY lexer facade；只负责 tokenization 和 lexer diagnostics。 |
| `src/VerilogParser.py` | PLY grammar；只负责当前声明子集到 AST Builder 的映射。 |
| `src/VerilogAst.py` | 稳定公开 AST API；增加 parser-facing typed builder 方法。 |
| `src/verilog.bnf` | 当前支持子集规范；每次 grammar 变更同步更新。 |

## Task Wave

### TASK-10: Parser Diagnostic Contract

目标：先收紧成功/失败边界，消灭“有错误但返回 AST”的第三态。

范围：

- 修改 `src/VerilogLexer.py`
- 修改 `src/VerilogParser.py`
- 新增 `src/VerilogDiagnostics.py`
- 更新 `tests/test_VerilogLexer.py`
- 更新 `tests/test_VerilogParser.py`
- 同步 `src/verilog.bnf` 的错误契约说明

验收：

- 当前子集不支持的字符或 token，例如 `@`，进入 lexer diagnostic，并导致
  `parse_string()` 抛 `VCGParseError`。diagnostic 文案必须表达
  "unsupported in current parser subset"，不能误导成 "not Verilog"。
- `parse_errors` 非空时，Parser 永不返回 AST。
- EOF 错误、后缀垃圾、残缺 module 都失败。
- `parse_file()` 继续区分 `VCGFileError` 与 `VCGParseError`。
- 下游旧调用 `VerilogParser().parse_string(code)` 签名保持可用。

重点测试：

```python
def test_illegal_character_fails_parse_without_partial_ast():
    parser = VerilogParser()
    with pytest.raises(VCGParseError):
        parser.parse_string("module m(input a@); endmodule")
    assert parser.get_module_info() is None

def test_extra_tokens_after_module_fail_parse():
    parser = VerilogParser()
    with pytest.raises(VCGParseError):
        parser.parse_string("module m; endmodule garbage")
```

### TASK-11: Lexer Token Contract

目标：把 token 分类和 token value 语义固定下来，避免 Lexer 私自改写源码。

范围：

- 修改 `src/VerilogLexer.py`
- 新增或修改 `src/VerilogTokens.py`
- 更新 `tests/test_VerilogLexer.py`
- 同步 `src/verilog.bnf`

验收：

- 关键字只精确匹配小写关键字；`MODULE`、`Input` 是普通 `ID`。
- Based number 支持大小写 base、可选 signed、`x/z/?`、下划线，并作为一个
  token 返回。
- 字符串 token 保留 raw spelling，Parser/AST 中参数默认值不会把 `"abc"` 变成
  `abc`。
- `$clog2` 这类系统标识符有明确 token 策略；`` `WIDTH`` 这类宏引用有明确
  token 策略。
- 不支持的 escaped identifier 明确失败或在 BNF 中标为 unsupported，不能被宽松
  ID 正则吞掉。

重点测试：

```python
def test_keywords_are_case_sensitive():
    lexer = VerilogLexer()
    lexer.input("MODULE Input module input")
    tokens = [(tok.type, tok.value) for tok in iter(lexer.token, None)]
    assert tokens == [
        ("ID", "MODULE"),
        ("ID", "Input"),
        ("MODULE", "module"),
        ("INPUT", "input"),
    ]

def test_based_number_is_not_partially_tokenized():
    lexer = VerilogLexer()
    lexer.input("8'HFF 8'shF_x 4'b10xz 8'd2_5")
    tokens = [(tok.type, tok.value) for tok in iter(lexer.token, None)]
    assert [typ for typ, _ in tokens] == [
        "INTNUMBER_HEX",
        "INTNUMBER_HEX",
        "INTNUMBER_BIN",
        "INTNUMBER_DEC",
    ]
```

### TASK-12: Parser Declaration Groups

目标：重做参数和端口声明组模型，修复 ANSI 多端口继承和 header 多参数继承。

范围：

- 新增 `src/VerilogDeclarations.py`
- 修改 `src/VerilogParser.py`
- 修改 parser-facing `VerilogAst` builder API
- 更新 `tests/test_VerilogParser.py`
- 同步 `src/verilog.bnf`

验收：

- `module m(input [7:0] a, b); endmodule` 中 `a`、`b` 都是
  `input wire [7:0]`。
- `module m #(parameter A=1, B=2); endmodule` 中 `A`、`B` 都是
  `parameter`。
- `localparam A=1, B=2` 的 body/header 行为一致。
- Verilog-1995 port name list + body declaration 继续工作。
- Parser action 不再传散乱 dict 作为声明核心数据。

建议数据结构：

```python
@dataclass(frozen=True)
class PortDeclarator:
    name: str
    unpacked_dims: tuple[str, ...] = ()

@dataclass(frozen=True)
class PortDeclarationGroup:
    direction: str | None
    net_type: str | None
    msb_expr: str | None
    lsb_expr: str | None
    declarators: tuple[PortDeclarator, ...]

@dataclass(frozen=True)
class ParameterDeclarator:
    name: str
    default_value: str

@dataclass(frozen=True)
class ParameterDeclarationGroup:
    param_type: str
    data_type: str | None
    declarators: tuple[ParameterDeclarator, ...]
```

重点测试：

```python
def test_ansi_port_group_inherits_direction_and_range():
    parser = VerilogParser()
    ast = parser.parse_string("module m(input [7:0] a, b); endmodule")
    ports = {port.name: port for port in ast.get_port_info()}
    assert ports["a"].direction == "input"
    assert ports["a"].range_string == "[7:0]"
    assert ports["b"].direction == "input"
    assert ports["b"].range_string == "[7:0]"

def test_header_parameter_group_inherits_parameter_type():
    parser = VerilogParser()
    ast = parser.parse_string("module m #(parameter A=1, B=2); endmodule")
    params = {param.name: param for param in ast.get_parameter_info()}
    assert params["A"].param_type == "parameter"
    assert params["B"].param_type == "parameter"
```

### TASK-13: Parser Grammar Cleanup

目标：让 Parser 只解析当前声明子集，不再用错误 grammar 吞非声明 body item。

范围：

- 修改 `src/VerilogParser.py`
- 更新 `tests/test_VerilogParser.py`
- 同步 `src/verilog.bnf`

验收：

- Parser 输入中出现 `assign`、instance、`always`、`generate` 时，如果它们来自
  Preprocess 声明抽取外泄，必须失败。
- Preprocess 正常裁剪后的声明输入继续通过 Parser。
- 删除或隔离 `module_item_assignment` / `module_item_instance` 这类“吞掉但不建模”
  规则。
- `p_error()` 的恢复策略明确：要么只收集并最终失败，要么由显式 error production
  恢复；不能让错误恢复产生成功 AST。

重点测试：

```python
def test_parser_rejects_assign_if_preprocess_leaks_it():
    parser = VerilogParser()
    with pytest.raises(VCGParseError):
        parser.parse_string("module m(input a); assign x = a; endmodule")

def test_parser_rejects_named_instance_if_preprocess_leaks_it():
    parser = VerilogParser()
    with pytest.raises(VCGParseError):
        parser.parse_string("module m(input a); child u0 (.a(a)); endmodule")
```

### TASK-14: Parser-Facing AST Builder Contract

目标：把 Parser 到 AST Builder 的接口收紧，保留公开兼容 API，但核心路径使用明确
方法和类型。

范围：

- 修改 `src/VerilogAst.py`
- 修改 `src/VerilogParser.py`
- 更新 `tests/test_VerilogAst.py`
- 更新 `tests/test_VerilogParser.py`

验收：

- Builder 提供明确 parser-facing 方法，例如：
  `add_port_group(group: PortDeclarationGroup)`、
  `add_parameter_group(group: ParameterDeclarationGroup)`。
- 旧的 `add_port(**kwargs)` / `update_port(**kwargs)` 兼容层继续可用，但 parser
  核心路径不依赖未知 kwargs。
- 未知字段在兼容层中至少被显式拒绝或记录 warning，不能静默丢弃。
- AST 对外 `PortInfo` / `ParameterInfo` 行为保持兼容。

重点测试：

```python
def test_builder_rejects_unknown_parser_field():
    builder = VerilogASTBuilder()
    with pytest.raises(VerilogASTError):
        builder.add_port(name="clk", direction="input", typo_field="bad")
```

### TASK-15: Expression and Literal Preservation

目标：统一表达式和字面量在 Parser/AST 中的文本保真策略，减少 silent semantic loss。

范围：

- 修改 `src/VerilogLexer.py`
- 修改 `src/VerilogParser.py`
- 修改 `src/VerilogAst.py`
- 更新 `tests/test_VerilogLexer.py`
- 更新 `tests/test_VerilogParser.py`
- 更新 `tests/test_VerilogAst.py`

验收：

- 参数默认值中的字符串保留引号。
- Based number 保留足够 source spelling，不因为下划线、大小写或 unknown bits 破坏
  后续展示。
- 宽度表达式中的 `` `WIDTH``、`$clog2(DEPTH)` 保留原文语义。
- ExpressionCalculator 不能把无法安全计算的表达式静默改成错误数字。
- 大整数宽度计算不能通过 float 丢精度。

重点测试：

```python
def test_string_parameter_default_preserves_quotes():
    parser = VerilogParser()
    ast = parser.parse_string('module m #(parameter S = "abc"); endmodule')
    param = ast.get_parameter_info()[0]
    assert param.default_value == '"abc"'

def test_large_integer_width_does_not_use_float_precision():
    port = PortInfo(name="data", direction="input", msb_expr="9007199254740993", lsb_expr="0")
    assert port.width == 9007199254740994
```

### TASK-16: Parser Component Verification Closure

目标：用文档和验证关闭本轮 parser component 重构，确保 JSON 进度、task 文档、
BNF、PROJECT 长期记忆一致。

范围：

- 新增 `doc/verification_16_parser_component_refactor.md`
- 新增 `doc/check_16_parser_component_refactor.md`
- 更新 `doc/parser_refactor_tasks.json`
- 更新 `PROJECT.md`
- 必要时归档过期 parser review 输入

验收：

- `doc/parser_refactor_tasks.json` 中所有 active task 状态为 `done`。
- 每个 task 都有 delivery/verification/check 证据或明确说明为什么不需要 check。
- `uv run pytest tests/test_VerilogLexer.py tests/test_VerilogParser.py tests/test_VerilogAst.py tests/test_VerilogPreprocess.py -q`
  通过。
- `uv run pytest tests -q` 通过。
- `src/verilog.bnf` 与 `VerilogParser.py` 当前 grammar 一致。
- `PROJECT.md` 提炼最终稳定结论，不复制流水账。

## Execution Order

推荐顺序固定为：

```text
TASK-10 diagnostic contract
  -> TASK-11 lexer token contract
  -> TASK-12 declaration groups
  -> TASK-13 grammar cleanup
  -> TASK-14 builder contract
  -> TASK-15 expression/literal preservation
  -> TASK-16 verification closure
```

不要先做 parser table 缓存、完整 SystemVerilog 支持、include expansion 或 manager
module_name 贯通。它们依赖更干净的 parser 前端，但不属于本轮解析器组件重构。

## Validation Gates

每个 task 至少运行对应 focused tests。涉及 grammar 或 AST 输出时，还必须运行：

```bash
uv run pytest tests/test_VerilogLexer.py tests/test_VerilogParser.py -q
uv run pytest tests/test_VerilogParser.py tests/test_VerilogAst.py -q
uv run pytest tests/test_VerilogPreprocess.py tests/test_VerilogParser.py -q
```

每两个 task 完成后运行：

```bash
uv run pytest tests -q
```

TASK-16 必须运行：

```bash
uv run pytest tests -q
```

## Compatibility Rules

- 保留 `VerilogParser(macros=None, debug=False)` 构造方式。
- 保留 `parse_string(verilog_code: str) -> VerilogAST` 旧调用。
- 保留 `parse_file(filepath: str) -> VerilogAST` 旧调用。
- 允许给 `parse_string` / `parse_file` 增加可选 `target_module`，但不能要求旧调用方修改。
- 允许新增内部 dataclass 和 helper 模块。
- 不承诺坏输入继续返回部分 AST；这是显式破坏错误兼容性的修复。
- `VerilogAST` 的公开查询方法保持可用：`get_port_info()`、`get_parameter_info()`、
  `get_module_info()`。

## Risks

- 旧测试可能绑定错误行为，例如大写关键字兼容、坏 Verilog 返回 partial AST。
  这些测试应改为 fail-loud 断言。
- PLY grammar 改动可能产生 shift/reduce 冲突。每个 task 必须记录 yacc warning。
- Builder typed API 会触碰 AST 层；必须把公开兼容层和 parser 核心路径分开。
- 表达式保真与宽度计算存在取舍。不能为了算出数字而丢掉 Verilog 原文语义。

## User Confirmation Gate

这是 parser component 的重构计划草案。进入 `src/` 和 `tests/` 实现前，应先确认：

- 是否接受本轮范围只覆盖 parser component，不推进 manager module_name 契约。
- 是否接受新增 `VerilogDiagnostics.py`、`VerilogTokens.py`、
  `VerilogDeclarations.py` 三个小模块。
- 是否接受坏输入不再返回 partial AST 的兼容性破坏。
