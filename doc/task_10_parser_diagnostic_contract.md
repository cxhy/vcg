# TASK-10: Parser Diagnostic Contract

| 字段 | 值 |
|------|----|
| 负责 | vcg-architect |
| 后续角色 | design -> vcg-python-dev -> vcg-python-tester -> vcg-architect -> user |
| 依赖 | TASK-09; `PROJECT.md` 决策 13-18; `doc/parser_refactor_plan.md`; `doc/parser_refactor_tasks.json` |
| 状态 | pending_user_review |
| 创建 | 2026-05-11 |
| 范围 | `VerilogLexer.py`, `VerilogParser.py`, diagnostics model, focused lexer/parser tests, `src/verilog.bnf` |

## 需求描述

TASK-10 只解决 Parser 管线的诊断和成功边界问题。目标是消灭当前最危险的第三态：

```text
源码有 lexer/parser 错误 -> Parser 记录错误 -> 仍返回一个看似成功的 AST
```

本任务不扩大 grammar 覆盖率，不实现 procedural block，不支持 always/sensitivity
list，不支持 named instance。它只要求当前不支持的输入不能被 lexer/parser 静默删除
或降级成 warning 后继续生成 AST。

## 关于 `@` 的处理原则

`@` 不是“永远非法”的字符。它在 Verilog procedural sensitivity list 中有语义，例如：

```verilog
always @(posedge clk) begin
end
```

但当前 VCG parser 的稳定目标是 module-level declaration 子集。TASK-10 不支持
procedural block，因此 `@` 在当前解析入口出现时应被归类为：

```text
unsupported token in current parser subset
```

而不是：

```text
illegal Verilog character
```

具体策略：

- Lexer 不得静默 `skip(1)` 后让解析继续成功。
- Lexer 应记录 error 级 diagnostic，包含：
  - diagnostic code，例如 `VLEX_UNSUPPORTED_CHAR`
  - 原始字符，例如 `@`
  - line / column / lexpos
  - message，明确说明当前 parser 子集不支持该字符
- Parser 在返回 AST 前统一检查 lexer diagnostics 和 parser diagnostics。
- 只要存在 error 级 diagnostic，就抛 `VCGParseError`。
- 未来支持 always/sensitivity list 时，把 `@` 注册为合法 token（例如 `AT`）并补
  grammar 即可；diagnostic model 不需要推倒。

这个策略同样适用于 `.`、`@`、`::`、`always`、`generate`、`begin`、`end` 等
未来可能支持但当前子集不支持的 token 或 keyword。

## token 诊断分类

TASK-10 必须避免把所有 lexer 问题都混成同一种“非法字符”。诊断至少分为三类：

1. **supported**

   当前 parser 子集支持的 token，正常进入 Parser grammar。

2. **recognized_unsupported**

   Verilog/SystemVerilog 中有明确语义，但当前 VCG parser 子集不支持的 token 或
   keyword。例如：

   - `@`：procedural sensitivity list。
   - `.`：named port connection 或 hierarchical name。
   - `::`：package scope。
   - `always` / `generate` / `begin` / `end` / `endgenerate`：procedural 或
     generate construct。

   这类诊断必须说明“当前 parser 子集不支持”，不能说明成“非法 Verilog”。
   如果后续任务支持其中一种语法，只需把对应 token 从 unsupported 表迁移到
   supported token + grammar。

3. **invalid**

   词法上无法可靠解释的输入，例如坏控制字符、未闭合字符串、无法完整识别的
   escaped identifier、坏数字字面量。它们不是“未来未实现”，而是当前输入本身
   不能形成可靠 token 流。

TASK-10 的实现设计必须维护显式分类表，而不是按单个字符特判。

## 需要重构的功能点

### F10.1 新增结构化 frontend diagnostic

定义一个轻量诊断模型，供 Lexer 和 Parser 共享。建议新增
`src/VerilogDiagnostics.py`，只放通用数据结构，不放 PLY 规则。

建议接口：

```python
from dataclasses import dataclass
from typing import Literal

DiagnosticSeverity = Literal["error", "warning"]

@dataclass(frozen=True)
class SourceLocation:
    line: int
    column: int
    lexpos: int | None = None

@dataclass(frozen=True)
class FrontendDiagnostic:
    code: str
    message: str
    severity: DiagnosticSeverity
    location: SourceLocation | None = None
    spelling: str = ""
```

约束：

- diagnostic 是不可变 dataclass。
- 不在 diagnostic 层决定是否抛异常；抛异常由 Parser 边界统一处理。
- `message` 不应把 unsupported-in-current-subset 误写成 invalid-Verilog。

### F10.2 Lexer 收集 diagnostics，禁止静默吞字符

`VerilogLexer` 需要维护当前输入的 diagnostics。

建议接口：

```python
class VerilogLexer:
    def reset_diagnostics(self) -> None:
        ...

    def get_diagnostics(self) -> tuple[FrontendDiagnostic, ...]:
        ...
```

行为要求：

- `input(data)` 时重置 diagnostics 和 PLY lexer 状态。
- `t_error()` 记录 `FrontendDiagnostic`。
- `t_error()` 可以调用 `skip(1)` 以避免 lexer 卡住，但这只是恢复扫描，不是容错成功。
- Parser 最终必须看到这些 diagnostics 并失败。
- 对未来保留但当前不支持的 token/keyword，Lexer 应记录
  `recognized_unsupported` 诊断；对无法可靠 token 化的输入，记录 `invalid`
  诊断。
- `generate`、`always` 等未来关键字不应被当作普通 ID 静默进入 AST 路径。

### F10.3 Parser 建立唯一成功边界

`VerilogParser.parse_string()` 的成功条件必须变成：

```text
preprocess 成功
lexer diagnostics 无 error
parser diagnostics 无 error
PLY parse result 完整
AST build 成功
```

任一条件不满足，抛 `VCGParseError`。

禁止：

- `parse_errors` 非空但返回 `self.ast`。
- lexer diagnostic 非空但返回 `self.ast`。
- 后缀垃圾或 EOF 错误只记录 warning。
- `get_module_info()` 在 parse 失败后返回上一次成功解析的 AST 信息。

### F10.4 Parser 状态重置必须彻底

每次 `parse_string()` 开始时必须重置：

- `self.builder`
- `self.ast`
- `self.parse_errors`
- lexer diagnostics
- PLY lexer line number，如适用

避免同一个 `VerilogParser` 实例多次解析时串状态。

### F10.5 错误消息聚合

`VCGParseError` 应包含足够上下文，便于用户定位：

```text
Parse failed with 2 diagnostics:
- VLEX_UNSUPPORTED_CHAR at line 1, column 16: unsupported character '@' in current parser subset
- VPARSE_SYNTAX at line 1, column 17: syntax error near ')'
```

如果 lexer 已经记录 error，Parser 可以继续解析以收集更多错误，但最终必须失败。

### F10.6 BNF 同步

更新 `src/verilog.bnf`：

- 明确当前 parser 子集不支持 `@`、`.`、`::`。
- 明确当前 parser 子集不支持 `always`、`generate`、`begin`、`end` 等未来 keyword。
- 说明这些 token/keyword 属于 future Verilog/SystemVerilog extension，不是永久非法。
- 说明 unsupported token 进入 diagnostics 后必须导致 parse failure。

## 非目标

- 不实现 `always @(...)`。
- 不实现 named instance `.a(a)`。
- 不把 `@` 加入当前 grammar。
- 不实现 SystemVerilog package/import。
- 不修改 InstanceManager/WiresManager 的 module_name 契约。
- 不做 parser table 缓存。

## 接口约束

必须保持：

```python
VerilogParser(macros=None, debug=False)
VerilogParser.parse_string(verilog_code: str) -> VerilogAST
VerilogParser.parse_file(filepath: str) -> VerilogAST
VerilogParser.get_module_info() -> Optional[dict]
VerilogLexer.input(data: str) -> None
VerilogLexer.token()
```

允许新增：

```python
VerilogLexer.get_diagnostics() -> tuple[FrontendDiagnostic, ...]
VerilogLexer.reset_diagnostics() -> None
VerilogParser.get_diagnostics() -> tuple[FrontendDiagnostic, ...]
```

不允许要求旧调用方捕获新异常类型。外部仍以 `VCGParseError` 识别 parse failure。

## 验收标准

### 必须新增或更新的行为测试

```python
def test_unsupported_at_character_fails_without_partial_ast():
    parser = VerilogParser()
    with pytest.raises(VCGParseError) as exc_info:
        parser.parse_string("module m(input a@); endmodule")
    assert parser.get_module_info() is None
    assert "@" in str(exc_info.value)
    assert "current parser subset" in str(exc_info.value)
```

```python
def test_parse_errors_do_not_return_ast():
    parser = VerilogParser()
    with pytest.raises(VCGParseError):
        parser.parse_string("module m(input); endmodule")
    assert parser.ast is None
```

```python
def test_trailing_garbage_after_module_fails():
    parser = VerilogParser()
    with pytest.raises(VCGParseError):
        parser.parse_string("module m; endmodule garbage")
```

```python
def test_parser_instance_does_not_reuse_previous_successful_ast_after_failure():
    parser = VerilogParser()
    parser.parse_string("module ok(input clk); endmodule")
    with pytest.raises(VCGParseError):
        parser.parse_string("module bad(input a@); endmodule")
    assert parser.get_module_info() is None
```

```python
def test_parse_file_still_raises_file_error_for_missing_file():
    parser = VerilogParser()
    with pytest.raises(VCGFileError):
        parser.parse_file("missing_file_that_should_not_exist.v")
```

### 必须运行的验证命令

```bash
uv run pytest tests/test_VerilogLexer.py tests/test_VerilogParser.py -q
uv run pytest tests/test_VerilogPreprocess.py tests/test_VerilogParser.py -q
```

建议补充：

```bash
uv run pytest tests -q
```

## 交付物

设计阶段必须交付：

- `doc/design_10_parser_diagnostic_contract.md`

实现阶段必须交付：

- `src/VerilogDiagnostics.py`
- `src/VerilogLexer.py`
- `src/VerilogParser.py`
- `src/verilog.bnf`
- `tests/test_VerilogLexer.py`
- `tests/test_VerilogParser.py`
- `doc/delivery_10_parser_diagnostic_contract.md`

验证阶段必须交付：

- `doc/verification_10_parser_diagnostic_contract.md`

架构检查阶段必须交付：

- `doc/check_10_parser_diagnostic_contract.md`

进度必须同步更新：

- `doc/parser_refactor_tasks.json`

## 角色交接流程

1. `vcg-architect` 完成本文件，状态为 `pending_user_review`。
2. 用户 review 并确认后，JSON 状态改为 `user_approved_architecture`。
3. 设计角色编写 `doc/design_10_parser_diagnostic_contract.md`，逐项覆盖 F10.1-F10.6。
4. 实现角色按 design 文档修改代码，写 delivery 文档。
5. 验证角色读取 task/design/delivery，逐项确认 F10.1-F10.6 是否完成。
6. 架构师读取 verification/check，确认未扩大范围、未阻碍未来 `@` token 支持。
7. 用户最终确认后，才提交并把 TASK-10 标为 `done`。

## 风险

- 如果 diagnostic 文案写成 "illegal Verilog character"，会误导未来扩展方向。
  本任务必须使用 "unsupported in current parser subset" 这类措辞。
- 如果 lexer 仍然只 log，不暴露 diagnostics，Parser 无法建立可靠成功边界。
- 如果 parse 失败后 `self.ast` 保留上一次成功结果，下游可能继续生成错误 Verilog。
- 如果测试只断言抛异常，不检查 `get_module_info()`，可能漏掉 stale AST 问题。
