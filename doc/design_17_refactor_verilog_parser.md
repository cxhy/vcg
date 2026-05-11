# DESIGN-17: Refactor VerilogParser Grammar and Declaration Flow

| 字段 | 值 |
|------|----|
| 对应任务 | `doc/task_17_refactor_verilog_parser.md` |
| 负责 | vcg-design |
| 状态 | design_ready_for_review |
| 创建 | 2026-05-12 |
| 范围 | `src/VerilogParser.py`, `src/VerilogDeclarations.py`, `src/verilog.bnf`, `tests/test_VerilogParser.py` |

## 设计目标

TASK-17 只重构当前 parser 支持的 module-level declaration 子集，不扩大 Verilog /
SystemVerilog 覆盖率。实现后，Parser grammar 先构造端口/参数 declaration group，
再通过现有 `VerilogASTBuilder.add_port()` / `update_port()` /
`add_parameter()` 写入 AST，避免同组 declarator 丢失方向、类型和位宽。

本设计遵守 `AGENTS.md` Role Handoff Discipline：设计阶段只写本文档，不修改
`src/` 或 `tests/`；后续 dev/test/check subagents 分阶段接手。

## 功能点覆盖表

| 功能点 | 设计落点 |
|--------|----------|
| F17.1 declaration group 模型 | 新增 `src/VerilogDeclarations.py`，放 parser-facing frozen dataclass。Parser action 不再用 dict 作为核心声明数据。 |
| F17.2 ANSI header port group-first | Header grammar 先解析为无歧义的 flat ANSI element list，再由 Python helper 归并为 declaration group；含 direction keyword 的 header 走 ANSI，裸 ID header 走 V95 name list。 |
| F17.3 header/body parameter group 统一 | header 和 body 都使用 `ParameterDeclarationGroup(param_type, data_type, declarators)`；`parameter A=1, B=2` 与 body 行为一致。 |
| F17.4 移除无 AST body item 消费 | 从 `module_item` 删除 `module_item_assignment` 和 `module_item_instance`，让泄漏的 `assign` / instance 进入 TASK-10 fail-loud 诊断路径。 |
| F17.5 error recovery 收敛 | error production 只记录 diagnostic 和同步边界，不返回 builder 可消费的 fallback declaration/expression。 |
| F17.6 Parser 职责清理 | Parser 保持公开 API；新增小 helper `_add_port_group()`、`_add_parameter_group()`、`_range_parts()`，不做 TASK-14 typed builder API。 |

## 文件结构

### 新增 `src/VerilogDeclarations.py`

建议新增该文件，而不是把 dataclass 放进 `VerilogParser.py`。

理由：

- `VerilogParser.py` 当前约 585 行，TASK-17 会重排 grammar 和 helper；把声明模型拆出后更容易保持文件低于 800 行。
- 这些类型是 parser-facing 中间模型，未来 TASK-14 可以复用为 builder typed API 的输入边界，但 TASK-17 不需要修改 `VerilogAst.py` 公开结构。
- dataclass 与 PLY action 解耦，tester 可在 parser 行为测试中间接验证，不需要从测试直接 import 内部 grammar 函数。

内容：

```python
from dataclasses import dataclass


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
class AnsiPortHeaderElement:
    direction: str | None
    net_type: str | None
    range_spec: RangeSpec | None
    declarator: PortDeclarator


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

不在本文件加入 AST builder 调用、PLY token 或 logger，保持纯数据模型。

### 修改 `src/VerilogParser.py`

新增 imports：

```python
from .VerilogDeclarations import (
    ParameterDeclarationGroup,
    ParameterDeclarator,
    AnsiPortHeaderElement,
    PortDeclarationGroup,
    PortDeclarator,
    RangeSpec,
)
```

保留公开 API：

- `VerilogParser(macros=None, debug=False)`
- `parse_string(verilog_code: str) -> VerilogAST`
- `parse_file(filepath: str) -> VerilogAST`
- `get_module_info() -> Optional[dict]`
- `get_diagnostics() -> tuple[FrontendDiagnostic, ...]`

新增私有 helper：

```python
def _add_port_group(self, group: PortDeclarationGroup, *, update_existing: bool = False) -> None: ...
def _add_parameter_group(self, group: ParameterDeclarationGroup) -> None: ...
def _coalesce_ansi_port_elements(
    self,
    elements: tuple[AnsiPortHeaderElement, ...],
) -> tuple[PortDeclarationGroup, ...]: ...
def _range_parts(self, range_spec: RangeSpec | None) -> tuple[str | None, str | None]: ...
def _default_net_type(self, net_type: str | None) -> str: ...
```

`update_existing=True` 只用于 V95 body port declaration，header ANSI 和 V95 name list
注册用 `add_port()`。底层仍调用现有 builder 方法，不新增 typed builder contract。

### 修改 `src/verilog.bnf`

BNF 同步 TASK-17 后的真实 parser 子集：

- Section 4.2 保留 header/body 共享的 `parameter_declaration_group`。
- Section 4.3 明确 header port list 的两种入口：ANSI group list 和 V95 name list。
- Section 4.4 删除 `<ignored_body_item>` 作为 parser grammar 成员；说明 Preprocess 可以裁剪非声明 body item，但若 `assign` / instance 泄漏到 Parser，Parser 必须失败。
- Section 6 增加：error production 不得产生 builder 可消费 fallback declaration。

### 修改 `tests/test_VerilogParser.py`

新增 `TestTask17VerilogParserRefactor`，覆盖 A17.1-A17.7。现有弱断言需要收紧：

- `test_b3_many_ports`: group-first 后应精确断言 50 个端口，而不是 `>= 40`。
- `test_b4_many_parameters`: header group 仍可用重复 `parameter` 写法，应精确断言 50 个参数。
- `test_f5_3_missing_endmodule`: TASK-10/TASK-17 fail-loud 后应只接受 `VCGParseError`。
- `test_f6_4_undefined_macro`: 不应允许 `result is None`，成功时必须是 AST，失败时应由 unsupported macro 规则决定；TASK-17 不修改宏 token，tester 只在必要时保持现有行为不扩大范围。
- `test_b9_mixed_v95_v2001_ports`: 当前混合 header 是兼容风险点，见下文。

## Grammar 重排

### Header parameter grammar

目标 PLY 结构：

```text
opt_parameter_list
    : HASH LPAREN parameter_declaration_list RPAREN
    | HASH LPAREN RPAREN
    | empty

parameter_declaration_list
    : parameter_declaration_group
    | parameter_declaration_list COMMA parameter_declaration_group

parameter_declaration_group
    : parameter_kind opt_parameter_data_type param_assignment_list

parameter_kind
    : PARAMETER
    | LOCALPARAM

param_assignment_list
    : param_assignment
    | param_assignment_list COMMA param_assignment

param_assignment
    : ID EQUALS expression
```

`opt_parameter_data_type` 本任务只返回 `None`：

```text
opt_parameter_data_type : empty
```

不要在 TASK-17 支持 `integer`、`signed` 或 packed data type。这样可满足：

- `parameter A=1, B=2`
- `localparam A=1, B=2`
- `parameter A=1, localparam B=2`
- body `parameter A=1, B=2; localparam C=3, D=4;`

### Header port grammar

现有 `port_list : port_declaration | port_list COMMA port_declaration` 是问题根源。
TASK-17 不再让 PLY 同时解析 “逗号分隔 declarator” 和 “逗号分隔 group”。Header
先解析为 flat ANSI element list，再由 Python helper 归并 group：

```text
opt_port_list
    : LPAREN ansi_port_header_list RPAREN
    | LPAREN port_name_list RPAREN
    | LPAREN RPAREN
    | empty

ansi_port_header_list
    : ansi_port_header_first
    | ansi_port_header_list COMMA ansi_port_header_next

ansi_port_header_first
    : port_direction opt_net_or_reg_type opt_packed_dimension port_declarator

ansi_port_header_next
    : port_direction opt_net_or_reg_type opt_packed_dimension port_declarator
    | port_declarator

port_declarator
    : ID

port_name_list
    : ID
    | port_name_list COMMA ID
```

歧义处理：

- Header 中第一个 token 是 `INPUT` / `OUTPUT` / `INOUT` 时走 ANSI flat element
  list。`ansi_port_header_first` 必须带 direction，因此不会把 V95 裸 ID header
  吞进 ANSI。
- Header 中第一个 token 是 `ID` 时走 V95 name list。
- 逗号后如果是 direction keyword，则 `ansi_port_header_next` 匹配带 direction
  元素，Python helper 开始新 group。
- 逗号后如果是 `ID`，则 `ansi_port_header_next` 匹配裸 `port_declarator`，Python
  helper 将它并入前一个 group。
- 因为 `ansi_port_header_next` 的两个 alternatives 首 token 分别是 direction
  keyword 和 `ID`，PLY 在 COMMA 后看 1 个 token 即可决定，不需要在 COMMA 处提前
  归约 group。

要求支持并解释如下：

- `module m(input [7:0] a, b);`
  flat elements:
  `input [7:0] a`、`b`；helper 归并为一个 `input wire [7:0]` group，含 `a,b`。
- `module m(output reg q, r);`
  flat elements:
  `output reg q`、`r`；helper 归并为一个 `output reg` group，含 `q,r`。
- `module m(input a, input b, output c);`
  flat elements:
  `input a`、`input b`、`output c`；helper 生成三个 group，或两个 input group 加一个
  output group。两种 builder 写入结果等价，推荐保持“每个显式 direction 开新 group”，
  便于保留源码声明边界。
- `module m(input a, b, output c);`
  flat elements:
  `input a`、`b`、`output c`；helper 生成 `input {a,b}` 和 `output {c}`。

### Body module item grammar

目标：

```text
module_item
    : module_item_declaration

module_item_declaration
    : body_port_declaration
    | body_parameter_declaration

body_port_declaration
    : port_direction opt_net_or_reg_type opt_packed_dimension port_declarator_list SEMICOLON

body_parameter_declaration
    : parameter_declaration_group SEMICOLON
```

删除：

```text
module_item_assignment : ASSIGN expression EQUALS expression SEMICOLON
module_item_instance   : ID ID LPAREN expression_list RPAREN SEMICOLON
```

结果：

- `assign x = a;` 中 `ASSIGN` 到达 `module_item` 时触发 parser diagnostic。
- `child u0(a);` 中 `ID ID LPAREN ...` 不再被消费，触发 parser diagnostic。
- `child u0 (.a(a));` 中 `.` 继续由 TASK-10 lexer diagnostic 标为
  `recognized_unsupported`，最终 `parse_string()` 抛 `VCGParseError`。

## 临时数据结构和 Parser Action 策略

### Range

`opt_packed_dimension` 返回 `RangeSpec | None`：

```python
def p_opt_packed_dimension(self, p):
    """opt_packed_dimension : LBRACKET expression COLON expression RBRACKET
                            | empty"""
    p[0] = RangeSpec(msb_expr=p[2], lsb_expr=p[4]) if len(p) == 6 else None
```

保留一维 packed range。不要实现 packed dimension list。

### Port groups

`port_declarator` 返回 `PortDeclarator(name=p[1])`。

Body declaration 继续使用 `port_declarator_list`，返回 tuple：

```python
p[0] = (p[1],)
p[0] = p[1] + (p[3],)
```

Header ANSI 不直接构造 `PortDeclarationGroup`，而是构造 flat elements：

```python
def p_ansi_port_header_first(self, p):
    """ansi_port_header_first : port_direction opt_net_or_reg_type opt_packed_dimension port_declarator"""
    p[0] = AnsiPortHeaderElement(p[1], p[2], p[3], p[4])


def p_ansi_port_header_next_decl(self, p):
    """ansi_port_header_next : port_direction opt_net_or_reg_type opt_packed_dimension port_declarator"""
    p[0] = AnsiPortHeaderElement(p[1], p[2], p[3], p[4])


def p_ansi_port_header_next_continuation(self, p):
    """ansi_port_header_next : port_declarator"""
    p[0] = AnsiPortHeaderElement(None, None, None, p[1])
```

`ansi_port_header_list` 返回 tuple：

```python
def p_ansi_port_header_list_single(self, p):
    """ansi_port_header_list : ansi_port_header_first"""
    p[0] = (p[1],)


def p_ansi_port_header_list_append(self, p):
    """ansi_port_header_list : ansi_port_header_list COMMA ansi_port_header_next"""
    p[0] = p[1] + (p[3],)
```

`opt_port_list : LPAREN ansi_port_header_list RPAREN` 的 action 是 header ANSI 的
唯一 builder 写入时机：

```python
groups = self._coalesce_ansi_port_elements(p[2])
for group in groups:
    self._add_port_group(group)
```

`port_name_list` 返回 tuple[str, ...]，在 `opt_port_list` 的 V95 分支中逐个
`builder.add_port(name=name)` 注册裸端口。

### Parameter groups

`param_assignment` 返回 `ParameterDeclarator`。

`param_assignment_list` 返回 `tuple[ParameterDeclarator, ...]`。

`parameter_declaration_group` 返回 `ParameterDeclarationGroup`。header 分支可在 group
rule 中直接 `_add_parameter_group()`；body 分支复用同一个 group 并调用相同 helper。

如果选择 group rule 直接写 builder，需要避免 body `parameter_declaration_group
SEMICOLON` 和 header 共享时重复添加。推荐策略是：group rule 只返回 group，不写
builder；调用点负责写入：

- `parameter_declaration_list` 在 header 中对每个 group 调 `_add_parameter_group()`。
- `body_parameter_declaration` 对 group 调 `_add_parameter_group()`。

## Builder 调用策略

### `_coalesce_ansi_port_elements`

Header ANSI 写 builder 前先归并 flat elements。规则：

- 第一个 element 必须带 `direction`，这是 grammar 保证。
- 带 `direction` 的后续 element 开始新 group。
- 不带 `direction` 的后续 element 继承当前 group 的 `direction`、`net_type`、
  `range_spec`，追加到当前 group 的 declarators。
- 如果 helper 收到第一个 element 无 direction，记录 parser diagnostic 并返回空
  tuple；正常 grammar 不应产生该输入。

建议实现：

```python
def _coalesce_ansi_port_elements(
    self,
    elements: tuple[AnsiPortHeaderElement, ...],
) -> tuple[PortDeclarationGroup, ...]:
    groups: list[PortDeclarationGroup] = []
    current: PortDeclarationGroup | None = None

    for element in elements:
        if element.direction is not None:
            current = PortDeclarationGroup(
                direction=element.direction,
                net_type=element.net_type,
                range_spec=element.range_spec,
                declarators=(element.declarator,),
            )
            groups.append(current)
            continue

        if current is None:
            self._record_parse_error(
                f"ANSI port continuation '{element.declarator.name}' has no declaration context"
            )
            return ()

        current = PortDeclarationGroup(
            direction=current.direction,
            net_type=current.net_type,
            range_spec=current.range_spec,
            declarators=current.declarators + (element.declarator,),
        )
        groups = groups[:-1] + [current]

    return tuple(groups)
```

具体例子：

- `input a, b, output c` 解析为三个 element：
  `input/a`、continuation `b`、`output/c`；归并为两个 group：
  `input {a,b}` 和 `output {c}`。
- `input a, input b, output c` 解析为三个带 direction element；归并为三个 group。
  builder 写入结果仍是 `a=input`、`b=input`、`c=output`。

### `_range_parts`

```python
def _range_parts(self, range_spec: RangeSpec | None) -> tuple[str | None, str | None]:
    if range_spec is None:
        return None, None
    return range_spec.msb_expr, range_spec.lsb_expr
```

### `_add_port_group`

ANSI header：

```python
def _add_port_group(self, group: PortDeclarationGroup, *, update_existing: bool = False) -> None:
    if self.builder is None:
        return
    msb_expr, lsb_expr = self._range_parts(group.range_spec)
    method = self.builder.update_port if update_existing else self.builder.add_port
    for declarator in group.declarators:
        method(
            name=declarator.name,
            direction=group.direction,
            net_type=group.net_type or "wire",
            msb_expr=msb_expr,
            lsb_expr=lsb_expr,
        )
```

V95 body declarations call `_add_port_group(group, update_existing=True)`。
V95 header name list uses `builder.add_port(name=name)` without direction/type/range.

### `_add_parameter_group`

```python
def _add_parameter_group(self, group: ParameterDeclarationGroup) -> None:
    if self.builder is None:
        return
    for declarator in group.declarators:
        self.builder.add_parameter(
            name=declarator.name,
            param_type=group.param_type,
            default_value=declarator.default_value,
            data_type=group.data_type,
        )
```

This keeps TASK-17 below TASK-14's boundary. Do not add
`VerilogASTBuilder.add_port_group()` or `add_parameter_group()` in this task.

## Error Recovery 策略

TASK-10 已保证 error diagnostic 会阻止 AST 返回。TASK-17 要进一步避免 fallback
数据污染 builder。

删除或改写这些 fallback：

- `param_assignment : ID EQUALS error` 不返回 `ParameterDeclarator("", "")`，只记录 diagnostic，返回 `None` 或让同步 rule 处理。
- `primary : ID LBRACKET error RBRACKET` 不返回 `name[?]`。
- `primary : ID LBRACKET error COLON error RBRACKET` 不返回 `name[?:?]`。
- `concatenation : LBRACE error RBRACE` 不返回 `{?}`。
- `opt_packed_dimension : LBRACKET error RBRACKET` 不返回 `None` 作为可继续构建的合法 scalar；它只能记录 diagnostic，并确保调用方不写 builder。

推荐同步点：

```text
opt_parameter_list : HASH LPAREN error RPAREN
opt_port_list      : LPAREN error RPAREN
module_item_list   : module_item_list error SEMICOLON
```

这些 action 只调用 `_record_parse_error(...)`，`p[0] = None`。任何依赖这些结果写
builder 的 action 必须先检查对象类型，例如 `isinstance(group,
ParameterDeclarationGroup)`；不是合法 group 就跳过写入。由于存在 error diagnostic，
`parse_string()` 最终仍然失败。

`p_error()` 保持记录结构化 diagnostic；TASK-17 可移除 `self.parser.errok()`，或仅在
明确同步 production 中恢复。若 dev 选择保留 `errok()`，delivery 必须说明没有
fallback builder 写入，且 focused tests 证明错误输入不会返回 AST。

## BNF 同步点

`src/verilog.bnf` 需要与实现同步以下内容：

1. Section 1: 将 “Non-declaration body items may be skipped” 改为 “Preprocess may
   remove them before parser input; parser must fail if they leak into grammar input.”
2. Section 3.1: `ASSIGN` 可仍列为 supported token，因为 lexer 支持它；但 Section
   4 不应再把 assign 作为 supported parser grammar body item。
3. Section 4.2: 确认 `parameter_declaration_group` 和
   `param_assignment_list` 是 header/body 共用模型。
4. Section 4.3: 确认 header ANSI grammar 使用 flat
   `ansi_port_header_list` / `ansi_port_header_next`，并说明 Python helper 将
   continuation ID 归并进前一个 declaration group。
5. Section 4.4: 删除 `<ignored_body_item>` 产生式。
6. Section 6: 增加 “error productions are synchronization only and must not create
   fallback declarations or expressions consumed by AST builder.”

## 测试设计

新增测试类：

```python
class TestTask17VerilogParserRefactor:
    def test_ansi_port_group_inherits_direction_and_range(self): ...
    def test_ansi_port_group_inherits_reg_type(self): ...
    def test_header_parameter_group_inherits_parameter_type(self): ...
    def test_header_localparam_group_inherits_parameter_type(self): ...
    def test_body_parameter_and_localparam_groups_are_consistent(self): ...
    def test_parser_rejects_assign_if_preprocess_leaks_it(self): ...
    def test_parser_rejects_positional_instance_if_preprocess_leaks_it(self): ...
    def test_parser_rejects_named_instance_if_preprocess_leaks_it(self): ...
    def test_v95_port_names_and_body_declaration_still_work(self): ...
```

具体断言按 TASK-17 A17.1-A17.7 编写。额外 named instance 测试用于覆盖 A17.6
第三段。

建议补充 regression：

- `module m(input a, output b); endmodule` 继续支持多个显式 ANSI group。
- `module m(input a, b, output c); endmodule` 归并为 `a,b` 继承 input，`c` 为 output。
- `module m #(parameter A=1, localparam B=2); endmodule` 继续支持混合参数类型。
- `module m(input a); assign x = a; endmodule` 后 `parser.get_module_info() is None`。
- 错误表达式如 `module m #(parameter P = {A,}); endmodule` 抛
  `VCGParseError`，且不会加入 default value `{?}`。

## 兼容性

保持兼容：

- Parser public API 不变。
- `VerilogAST`、`PortInfo`、`ParameterInfo` 查询 API 不变。
- `get_module_info()` 返回结构不变。
- Existing builder compatibility methods continue to be used.
- Verilog-1995 header name list + body declarations 继续工作。

有意收紧：

- Parser 不再接受泄漏的 `assign`、positional instance 或 named instance。
- error production 不再生成 `''`、`?`、`{?}` 这类伪表达式。
- 弱测试中允许 partial parse 的断言应改为明确成功或明确失败。

非目标保持：

- 不修改 `VerilogLexer.py` token spelling 和 keyword case-sensitive bug。
- 不支持 `SYSTEM_ID` / `MACRO_ID` 新 token。
- 不实现完整 data type grammar。
- 不修改 `vcg_instance_manager.py`、`vcg_wires_manager.py`、`vcg_rule_manager.py`。
- 不新增 AST builder typed API。

## 风险和控制

- **PLY shift/reduce 冲突**：旧 group-first 写法把逗号同时用于 declarator 和 group
  分隔。控制：TASK-17 采用 flat ANSI element grammar，COMMA 后的 lookahead 为
  direction keyword 时产生新声明 element，为 `ID` 时产生 continuation element；
  dev delivery 仍必须记录 yacc 构建是否出现冲突。

- **混合 header 风格风险**：现有 `test_b9_mixed_v95_v2001_ports` 使用
  `input wire clk, a, b` 后再在 body 声明 `a, b`。TASK-17 的 group-first 语义会把
  `a, b` 也继承为 input wire。若 body 后续把 `b` 更新为 output，则当前 builder
  “last update wins” 可得到最终 output；但这类混合风格不是验收主路径。tester 应保留
  回归但不扩大语法承诺。

- **删除 instance/assign 消费暴露 preprocess 漏洞**：这是预期行为。控制：
  focused tests 明确断言抛 `VCGParseError`。

- **error production 跳过合法后续声明**：TASK-17 允许有限同步，但不能牺牲
  fail-loud。控制：错误输入最终失败，合法声明组测试覆盖 A17.1-A17.7。

- **新增 `VerilogDeclarations.py` import 边界**：该文件只被 Parser 直接 import。
  Tests 不应依赖其内部类，除非 tester 需要专门验证 dataclass immutability。

## 建议验证命令

设计阶段不运行测试作为完成依据。实现/验证阶段建议按顺序运行：

```bash
uv run pytest tests/test_VerilogParser.py::TestTask17VerilogParserRefactor -q
uv run pytest tests/test_VerilogParser.py -q
uv run pytest tests/test_VerilogPreprocess.py tests/test_VerilogParser.py -q
uv run pytest tests/test_VerilogLexer.py tests/test_VerilogParser.py -q
uv run pytest tests -q
```

## 后续角色交接

### 给 vcg-python-dev

- 只修改 TASK-17 write scope：`src/VerilogParser.py`、`src/VerilogDeclarations.py`、
  `src/verilog.bnf`，必要时配合 tester 修改 `tests/test_VerilogParser.py`。
- 不修改 Lexer token contract，不修改 AST public API。
- delivery 文档必须记录 yacc 冲突情况、实际 grammar 差异、验证命令结果。

### 给 vcg-python-tester

- 新增 `TestTask17VerilogParserRefactor`，覆盖 A17.1-A17.7。
- 收紧现有 partial parse 弱断言。
- 若验证发现产品代码问题，写 `doc/feedback_17_refactor_verilog_parser.md`，不要在
  tester 阶段静默混入产品代码修复。

### 给 vcg-verilog-checker

- 检查 TASK-17 是否改变生成 AST 的端口方向、net type、range、parameter type。
- 特别确认 ANSI group inheritance、V95 body update、unsupported assign/instance
  fail-loud 三类行为。
