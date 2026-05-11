# TASK-17: Refactor VerilogParser Grammar and Declaration Flow

| 字段 | 值 |
|------|----|
| 负责 | vcg-architect |
| 后续角色 | vcg-design -> vcg-python-dev -> vcg-python-tester -> vcg-verilog-checker -> vcg-architect -> user |
| 依赖 | TASK-10; `doc/parser_refactor_plan.md`; `doc/parser_refactor_tasks.json`; `doc/review/10_VerilogParser.md` |
| 取代 | TASK-12 Parser declaration groups; TASK-13 Parser grammar cleanup |
| 状态 | pending_user_review |
| 创建 | 2026-05-12 |
| 范围 | `src/VerilogParser.py`, parser declaration helper if required, `src/verilog.bnf`, `tests/test_VerilogParser.py` |

## 需求描述

本任务重构 `VerilogParser.py` 的 grammar 和声明数据流，让 Parser 只负责当前
module-level declaration 子集，并把端口/参数声明建模成清晰的 declaration group。

TASK-10 已经建立 fail-loud 诊断边界；TASK-17 在这个基础上清理 Parser 内部结构：

- 修复 ANSI header 中同组端口不继承方向、类型、位宽的问题。
- 修复 header parameter 中 `parameter A=1, B=2` 不能按同组声明解析的问题。
- 删除或隔离 `assign` / instance 这类“吞掉但不建 AST”的 grammar。
- 收敛 error production，避免 grammar action 返回伪造值。
- 降低 `VerilogParser.py` 的职责混杂度，为后续 AST builder contract 和 literal
  preservation 任务留出干净接口。

本任务是 parser 文件重构，不是 Verilog/SystemVerilog 覆盖率扩展。

## 当前问题和证据

### P17.1 ANSI 端口声明组语义错误

当前位置：`src/VerilogParser.py` 的 `port_list` 把逗号分隔项都当成完整
`port_declaration`。

问题输入：

```verilog
module m(input [7:0] a, b); endmodule
```

期望：`a` 和 `b` 都是 `input wire [7:0]`。

当前结构无法表达“同一声明组的多个 declarator 继承同一个方向/类型/位宽”。

### P17.2 Header parameter group 语义不一致

当前位置：`parameter_declaration_list` 要求逗号后继续出现完整
`parameter_declaration`。

问题输入：

```verilog
module m #(parameter A=1, B=2); endmodule
```

期望：`A`、`B` 都是 `parameter`。

当前 body parameter 已有 `param_assignment_list`，header 与 body 行为不一致。

### P17.3 Parser 仍在吞非声明型 body item

当前位置：

- `module_item_assignment`
- `module_item_instance`

这些 rule 消费 `assign` 或 positional instance，却不产生 AST，也不产生 unsupported
diagnostic。这会让 Parser 看起来支持模块行为，但实际只丢弃信息。

TASK-17 要求：如果 `assign`、instance、procedural/generate 语法从
`VerilogPreprocess` 外泄到 Parser，Parser 必须失败，不能吞掉后继续生成 AST。

### P17.4 error production 返回伪造值

当前位置：

- `param_assignment : ID EQUALS error` 返回 `{'name': ..., 'value': ''}`
- `primary : ID LBRACKET error RBRACKET` 返回 `name[?]`
- `concatenation : LBRACE error RBRACE` 返回 `{?}`

TASK-10 已经保证有 diagnostic 时最终失败，但 TASK-17 要求进一步清理这些
fallback，避免 Parser action 继续污染 builder 或表达式字符串。

### P17.5 Parser 数据模型仍依赖散乱 dict/list

当前位置：

- dimension 使用 `{'msb': ..., 'lsb': ...}`
- parameter 使用 `{'name': ..., 'value': ...}`
- port identifier list 是裸 list

这些临时结构使 grammar action 难以读，也让 group inheritance 很容易写错。

## 需要重构的功能点

### F17.1 引入 parser 内部 declaration group 模型

设计阶段必须决定 dataclass 放置位置：

- 优先：新增 `src/VerilogDeclarations.py`，只放 parser-facing immutable dataclass。
- 可接受：如果设计证明无需新文件，也可在 `VerilogParser.py` 内部定义小型
  frozen dataclass，但必须保持文件小于 800 行、函数小于 50 行。

建议模型：

```python
@dataclass(frozen=True)
class RangeSpec:
    msb_expr: str
    lsb_expr: str

@dataclass(frozen=True)
class PortDeclarator:
    name: str

@dataclass(frozen=True)
class PortDeclarationGroup:
    direction: str | None
    net_type: str | None
    range_spec: RangeSpec | None
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

约束：

- dataclass 使用 `frozen=True`。
- Parser action 不再把 dict 作为核心声明数据结构。
- Builder 调用可以继续使用现有 `add_port()` / `update_port()` /
  `add_parameter()`；不要在本任务扩大到 TASK-14 的 AST builder contract。

### F17.2 重写 ANSI header port grammar 为 group-first

目标 grammar 语义：

```text
port_list -> ansi_port_declaration_group
           | port_list COMMA ansi_port_declaration_group

ansi_port_declaration_group
    -> port_direction opt_net_or_reg_type opt_packed_dimension port_declarator_list

port_declarator_list
    -> port_declarator
     | port_declarator_list COMMA port_declarator
```

行为要求：

- `module m(input [7:0] a, b); endmodule` 中 `a`、`b` 都继承 `input` 和
  `[7:0]`。
- `module m(output reg q, r); endmodule` 中 `q`、`r` 都继承 `output reg`。
- `module m(input a, output b); endmodule` 继续支持多个显式 group。
- Verilog-1995 port name list + body declaration 继续支持。

设计阶段必须处理 ANSI group 和 V95 name list 的歧义。建议把含 direction keyword
的 header 识别为 ANSI group；裸 ID header 作为 V95 name list。

### F17.3 统一 header/body parameter declaration group

行为要求：

- `module m #(parameter A=1, B=2); endmodule` 解析出两个 parameter。
- `module m #(localparam A=1, B=2); endmodule` 解析出两个 localparam。
- `module m #(parameter A=1, localparam B=2); endmodule` 保持支持。
- `module m; parameter A=1, B=2; localparam C=3, D=4; endmodule` 行为一致。

约束：

- header/body 参数共享同一个 `ParameterDeclarationGroup` 数据模型。
- data type 字段可先保留为 `None`；不要在本任务实现 `integer`、`signed`、
  packed type 等新语法。

### F17.4 移除无 AST 语义的 body item 消费规则

必须删除或改成显式失败：

- `module_item_assignment`
- `module_item_instance`

验收行为：

```verilog
module m(input a); assign x = a; endmodule
```

必须抛 `VCGParseError`。

```verilog
module m(input a); child u0(a); endmodule
```

必须抛 `VCGParseError`。

```verilog
module m(input a); child u0 (.a(a)); endmodule
```

必须抛 `VCGParseError`；其中 `.` 仍由 TASK-10 diagnostic model 归类为
`recognized_unsupported`。

### F17.5 收敛 parser error recovery

要求：

- `p_error()` 只负责记录结构化 parser diagnostic，不伪装恢复成功。
- error production 不得向 builder 写入不完整声明。
- 如果保留 error production 只是为了同步到 `RPAREN` / `SEMICOLON`，必须保证
  action 只记录 diagnostic，不返回会被 builder 消费的 fallback 数据。
- `parse_string()` 的成功边界仍由 TASK-10 负责：任何 error diagnostic 都不能返回 AST。

### F17.6 清理 Parser 文件职责

要求：

- `VerilogParser.py` 仍保留公开 API：
  - `VerilogParser(macros=None, debug=False)`
  - `parse_string(verilog_code: str) -> VerilogAST`
  - `parse_file(filepath: str) -> VerilogAST`
  - `get_module_info() -> Optional[dict]`
  - `get_diagnostics() -> tuple[FrontendDiagnostic, ...]`
- 私有 helper 命名清晰，例如：
  - `_add_port_group(group)`
  - `_add_parameter_group(group)`
  - `_range_parts(range_spec)`
- 单个函数小于 50 行。
- `src/VerilogParser.py` 小于 800 行。
- 不在 Parser 中实现完整 AST builder typed API；这属于 TASK-14。

## 非目标

- 不修改 `src/VerilogLexer.py` 的 token spelling / keyword case-sensitive bug；这是 TASK-11。
- 不实现 `SYSTEM_ID` / `MACRO_ID` 新 token；这是 TASK-11/TASK-15。
- 不实现 `always`、`initial`、`generate`、named instance、package/import。
- 不实现完整 Verilog data type grammar。
- 不修改 `vcg_instance_manager.py`、`vcg_wires_manager.py`、`vcg_rule_manager.py`。
- 不做 PLY table 缓存。
- 不改变 `VerilogAST` 公开查询 API。

## 接口约束

必须保持：

```python
parser = VerilogParser(macros=None, debug=False)
ast = parser.parse_string(verilog_code)
ast = parser.parse_file(filepath)
info = parser.get_module_info()
diagnostics = parser.get_diagnostics()
```

允许新增内部-only API：

```python
def _add_port_group(self, group: PortDeclarationGroup) -> None: ...
def _add_parameter_group(self, group: ParameterDeclarationGroup) -> None: ...
```

允许新增文件：

```text
src/VerilogDeclarations.py
```

如果新增该文件，设计文档必须说明为什么它比把 dataclass 放进
`VerilogParser.py` 更干净，并同步测试 import 边界。

## 验收标准

### A17.1 ANSI 端口声明组继承正确

```python
def test_ansi_port_group_inherits_direction_and_range():
    parser = VerilogParser()
    ast = parser.parse_string("module m(input [7:0] a, b); endmodule")
    ports = {port.name: port for port in ast.get_port_info()}
    assert ports["a"].direction == "input"
    assert ports["a"].range_string == "[7:0]"
    assert ports["b"].direction == "input"
    assert ports["b"].range_string == "[7:0]"
```

### A17.2 ANSI 端口声明组继承 net/reg 类型

```python
def test_ansi_port_group_inherits_reg_type():
    parser = VerilogParser()
    ast = parser.parse_string("module m(output reg q, r); endmodule")
    ports = {port.name: port for port in ast.get_port_info()}
    assert ports["q"].net_type == "reg"
    assert ports["r"].net_type == "reg"
```

### A17.3 Header parameter group 支持同声明多赋值

```python
def test_header_parameter_group_inherits_parameter_type():
    parser = VerilogParser()
    ast = parser.parse_string("module m #(parameter A=1, B=2); endmodule")
    params = {param.name: param for param in ast.get_parameter_info()}
    assert params["A"].param_type == "parameter"
    assert params["B"].param_type == "parameter"
```

### A17.4 Header localparam group 支持同声明多赋值

```python
def test_header_localparam_group_inherits_parameter_type():
    parser = VerilogParser()
    ast = parser.parse_string("module m #(localparam A=1, B=2); endmodule")
    params = {param.name: param for param in ast.get_parameter_info()}
    assert params["A"].param_type == "localparam"
    assert params["B"].param_type == "localparam"
```

### A17.5 Body parameter/localparam 继续一致

```python
def test_body_parameter_and_localparam_groups_are_consistent():
    parser = VerilogParser()
    ast = parser.parse_string(
        "module m; parameter A=1, B=2; localparam C=3, D=4; endmodule"
    )
    params = {param.name: param for param in ast.get_parameter_info()}
    assert params["A"].param_type == "parameter"
    assert params["B"].param_type == "parameter"
    assert params["C"].param_type == "localparam"
    assert params["D"].param_type == "localparam"
```

### A17.6 Parser 不再吞 assign / instance

```python
def test_parser_rejects_assign_if_preprocess_leaks_it():
    parser = VerilogParser()
    with pytest.raises(VCGParseError):
        parser.parse_string("module m(input a); assign x = a; endmodule")
```

```python
def test_parser_rejects_positional_instance_if_preprocess_leaks_it():
    parser = VerilogParser()
    with pytest.raises(VCGParseError):
        parser.parse_string("module m(input a); child u0(a); endmodule")
```

### A17.7 V95 端口声明继续工作

```python
def test_v95_port_names_and_body_declaration_still_work():
    parser = VerilogParser()
    ast = parser.parse_string("module m(a, b); input [3:0] a, b; endmodule")
    ports = {port.name: port for port in ast.get_port_info()}
    assert ports["a"].direction == "input"
    assert ports["a"].range_string == "[3:0]"
    assert ports["b"].direction == "input"
    assert ports["b"].range_string == "[3:0]"
```

## 必须运行的验证命令

Focused：

```bash
uv run pytest tests/test_VerilogParser.py::TestTask17VerilogParserRefactor -q
uv run pytest tests/test_VerilogParser.py -q
```

Parser component regression：

```bash
uv run pytest tests/test_VerilogPreprocess.py tests/test_VerilogParser.py -q
uv run pytest tests/test_VerilogLexer.py tests/test_VerilogParser.py -q
```

Closure before user final confirmation：

```bash
uv run pytest tests -q
```

## 交付物

设计阶段必须交付：

- `doc/design_17_refactor_verilog_parser.md`

实现阶段必须交付：

- `src/VerilogParser.py`
- `src/VerilogDeclarations.py`（如设计选择新增）
- `src/verilog.bnf`
- `tests/test_VerilogParser.py`
- `doc/delivery_17_refactor_verilog_parser.md`

验证阶段必须交付：

- `doc/verification_17_refactor_verilog_parser.md`

Verilog/AST 检查阶段必须交付：

- `doc/check_17_refactor_verilog_parser.md`

进度必须同步更新：

- `doc/parser_refactor_tasks.json`

## 角色交接流程

1. `vcg-architect` 完成本任务单和 JSON 状态更新，等待用户 review。
2. 用户确认后，主会话将 JSON 状态推进到 `user_approved_architecture`。
3. 主会话启动独立 `vcg-design` subagent，`reasoning_effort=high`，只写 design 文档。
4. 设计文档经用户或架构师批准后，启动独立 `vcg-python-dev` subagent，
   `reasoning_effort=high`，按 design 实现。
5. Dev 写 delivery 文档后，启动独立 `vcg-python-tester` subagent，
   `reasoning_effort=high`，写测试和 verification 文档。
6. 因本任务影响 parser grammar 和 AST 输入语义，必须启动独立
   `vcg-verilog-checker` subagent，`reasoning_effort=high`，写 check 文档。
7. 架构师读取 verification/check，确认 F17.1-F17.6 和 A17.1-A17.7 全部关闭。
8. 用户最终确认后，才允许提交并把 TASK-17 标记为 `done`。

## 风险

- Parser grammar 改为 group-first 后可能产生 PLY shift/reduce 冲突；delivery 文档必须记录 yacc 构建结果。
- 旧测试中存在“允许部分解析失败”的弱断言，tester 需要把相关断言收紧为精确行为。
- 如果本任务顺手修改 Lexer token spelling，会和 TASK-11 交叉污染；设计和 dev 都必须避免。
- 如果本任务顺手修改 AST builder typed API，会和 TASK-14 交叉污染；只允许通过现有 builder 兼容方法写入 AST。
- 删除 `assign` / instance 消费规则可能暴露 Preprocess 裁剪遗漏；这是预期行为，应通过 fail-loud 测试确认。
