# DESIGN-10: Parser Diagnostic Contract

| 字段 | 值 |
|------|----|
| 对应任务 | `doc/task_10_parser_diagnostic_contract.md` |
| 负责 | design |
| 状态 | design_ready_for_review |
| 创建 | 2026-05-11 |
| 范围 | 诊断数据模型、Lexer diagnostics、Parser 成功边界、BNF 错误契约、focused tests |

## 设计目标

TASK-10 只建立 Parser 管线的诊断和成功边界，不扩大 grammar 覆盖率。实现后，
Lexer / Parser 可以继续做有限错误恢复来收集更多诊断，但只要存在 error 级
diagnostic，`VerilogParser.parse_string()` 就必须抛 `VCGParseError`，不能返回 AST。

## 功能点覆盖表

| Architect 功能点 | 设计落点 |
|------------------|----------|
| F10.1 结构化 frontend diagnostic | 新增 `src/VerilogDiagnostics.py`，定义 `SourceLocation`、`FrontendDiagnostic`、分类与格式化 helper。 |
| F10.2 Lexer diagnostics | `VerilogLexer` 增加 diagnostics 列表、`reset_diagnostics()`、`get_diagnostics()`、unsupported/invalid 分类记录。 |
| F10.3 Parser 唯一成功边界 | `VerilogParser.parse_string()` 统一收集 preprocess / lexer / parser / AST diagnostics，失败前清空 `self.ast`。 |
| F10.4 Parser 状态重置 | 新增 `_reset_parse_state()`，每次 parse 前重置 builder、ast、parse_errors、diagnostics、lexer lineno。 |
| F10.5 错误消息聚合 | 新增 `_raise_if_diagnostics()`，把 diagnostics 格式化进 `VCGParseError`。 |
| F10.6 BNF 同步 | 更新 `src/verilog.bnf` 的 unsupported/invalid token 分类说明。 |

## Token 分类策略

TASK-10 不用单个字符特判决定错误类型。Lexer 采用三层分类：

### supported

当前 parser 子集支持并返回给 PLY parser 的 token。例如：

- `module` / `endmodule`
- `input` / `output` / `inout`
- `parameter` / `localparam`
- 普通 ID、当前支持的数字、字符串、表达式运算符、括号、分号、逗号。

### recognized_unsupported

Verilog/SystemVerilog 有明确语义，但当前 module-level declaration 子集不支持。
这些输入应记录 error 级 diagnostic，message 使用
`unsupported in current parser subset`，不能写成 `illegal Verilog`。

初始表：

```python
UNSUPPORTED_SINGLE_CHAR_TOKENS = {
    "@": "procedural event control",
    ".": "named port connection or hierarchical name",
}

UNSUPPORTED_MULTI_CHAR_TOKENS = {
    "::": "SystemVerilog package scope",
    "->": "event trigger",
}

UNSUPPORTED_KEYWORDS = {
    "always": "procedural block",
    "initial": "procedural block",
    "begin": "procedural block",
    "end": "procedural block",
    "generate": "generate block",
    "endgenerate": "generate block",
    "case": "procedural block",
    "endcase": "procedural block",
    "for": "procedural or generate loop",
    "if": "procedural or generate conditional",
    "typedef": "SystemVerilog type declaration",
    "interface": "SystemVerilog interface",
    "modport": "SystemVerilog modport",
    "import": "SystemVerilog package import",
}
```

未来支持其中任意 token 时，迁移方式是：

1. 从 unsupported 表删除。
2. 加入 `tokens` / `reserved`。
3. 增加 grammar rule。
4. 增加 parser/AST 测试。

诊断框架不需要变化。

### invalid

词法上无法可靠形成 token 的输入。例如：

- 不在 supported 或 recognized_unsupported 表中的不可见控制字符。
- 当前 string rule 无法识别的未闭合字符串。
- 当前无法可靠处理的 escaped identifier。
- 后续 TASK-11 细化前，坏 based number 可先落入 generic invalid diagnostic。

TASK-10 不要求完整修复数字和字符串 token 契约；那属于 TASK-11 / TASK-15。但
TASK-10 必须保证一旦 lexer 发现 invalid，就不会返回 AST。

## 新增文件设计

### `src/VerilogDiagnostics.py`

只放诊断模型和格式化 helper，不依赖 PLY。

```python
from dataclasses import dataclass
from typing import Literal, Optional

DiagnosticSeverity = Literal["error", "warning"]
DiagnosticStage = Literal["preprocess", "lexer", "parser", "ast"]
DiagnosticKind = Literal["recognized_unsupported", "invalid", "syntax", "semantic"]

@dataclass(frozen=True)
class SourceLocation:
    line: int
    column: int
    lexpos: Optional[int] = None

@dataclass(frozen=True)
class FrontendDiagnostic:
    code: str
    message: str
    severity: DiagnosticSeverity
    stage: DiagnosticStage
    kind: DiagnosticKind
    location: Optional[SourceLocation] = None
    spelling: str = ""

    @property
    def is_error(self) -> bool:
        return self.severity == "error"
```

格式化 helper：

```python
def format_diagnostics(diagnostics: tuple[FrontendDiagnostic, ...]) -> str:
    ...
```

输出格式固定为：

```text
Parse failed with 2 diagnostics:
- VLEX_UNSUPPORTED_TOKEN at line 1, column 16: unsupported token '@' in current parser subset
- VPARSE_SYNTAX at line 1, column 17: syntax error near ')'
```

## Lexer 设计

### 状态字段

`VerilogLexer.__init__()` 增加：

```python
self._diagnostics: list[FrontendDiagnostic] = []
```

新增 public-ish helper：

```python
def reset_diagnostics(self) -> None:
    self._diagnostics = []

def get_diagnostics(self) -> tuple[FrontendDiagnostic, ...]:
    return tuple(self._diagnostics)
```

`input(data)` 调整为：

```python
def input(self, data: str) -> None:
    self.reset_diagnostics()
    self.lexer.lineno = 1
    self.lexer.input(data)
```

### unsupported multi-character token

PLY function rules优先于简单 token。新增规则放在 `t_ID` 和 `t_error` 前：

```python
def t_UNSUPPORTED_SCOPE(self, t):
    r"::"
    self._record_unsupported(t, "VLEX_UNSUPPORTED_TOKEN", "SystemVerilog package scope")

def t_UNSUPPORTED_ARROW(self, t):
    r"->"
    self._record_unsupported(t, "VLEX_UNSUPPORTED_TOKEN", "event trigger")
```

这些函数不返回 token，表示消费该 lexeme 继续扫描；最终 Parser 会因为
diagnostics 失败。

### unsupported keyword

`t_ID` 增加 exact lowercase 检查：

```python
if t.value in UNSUPPORTED_KEYWORDS:
    self._record_unsupported(t, "VLEX_UNSUPPORTED_KEYWORD", UNSUPPORTED_KEYWORDS[t.value])
    return None
```

注意大小写敏感：`Generate` 不是 keyword，仍按普通 `ID` 处理。关键字大小写问题的
全面测试属于 TASK-11，但 TASK-10 不应引入新的大小写折叠。

### unsupported / invalid character

`t_error()` 改为：

```python
char = t.value[0]
if char in UNSUPPORTED_SINGLE_CHAR_TOKENS:
    self._record_unsupported_char(t, UNSUPPORTED_SINGLE_CHAR_TOKENS[char])
else:
    self._record_invalid_char(t)
t.lexer.skip(1)
```

`@` 的 message 示例：

```text
unsupported token '@' in current parser subset (procedural event control)
```

## Parser 设计

### 状态字段

`VerilogParser.__init__()` 增加：

```python
self._diagnostics: list[FrontendDiagnostic] = []
```

保留 `parse_errors: List[str]` 兼容旧测试和调试习惯，但 Parser 内部新增
`_record_parse_error()`，同时写入 `parse_errors` 和 `_diagnostics`。

### reset

新增：

```python
def _reset_parse_state(self) -> None:
    self.builder = VerilogASTBuilder()
    self.ast = None
    self.parse_errors.clear()
    self._diagnostics = []
    self.lexer.reset_diagnostics()
```

`parse_string()` 开头只调用该 helper。

### parse flow

`parse_string()` 设计为：

```python
def parse_string(self, verilog_code: str) -> VerilogAST:
    self._reset_parse_state()
    try:
        preprocessed_code = self.preprocessor.preprocess_string(verilog_code)
        self.lexer.input(preprocessed_code)
        parse_result = self.parser.parse(lexer=self.lexer.lexer, debug=self.debug)
    except VCGError:
        self.ast = None
        raise
    except Exception as e:
        self.ast = None
        raise VCGParseError(f"Unexpected parse failure: {e}") from e

    self._diagnostics.extend(self.lexer.get_diagnostics())
    self._raise_if_error_diagnostics()

    if self.ast is None:
        raise VCGParseError("Parser did not produce an AST (no module declaration found?)")
    return self.ast
```

如果 `_finalize_ast()` 先成功、后续 token 又触发 `p_error()`，`_raise_if_error_diagnostics()`
必须在 raise 前执行：

```python
self.ast = None
```

这避免失败后 `get_module_info()` 返回 stale AST。

### p_error

`p_error()` 不在 TASK-10 中重新设计完整恢复策略，只改成记录结构化 diagnostic。
现有 `errok()` 可以暂时保留，因为本任务通过最终边界保证不会成功返回 AST。
完整 grammar cleanup 放到 TASK-13。

## BNF 更新设计

`src/verilog.bnf` 增加或修正这些段落：

- 当前 supported token list。
- future recognized unsupported token list：
  `@`、`.`、`::`、`->`、`always`、`initial`、`begin`、`end`、
  `generate`、`endgenerate`、`typedef`、`interface`、`modport`、`import`。
- 说明 recognized unsupported token 一旦进入 lexer diagnostics，当前 parse 必须失败。
- 说明未来支持路径是从 unsupported list 迁移到 supported token + grammar，不改
  fail-loud 边界。

## 测试设计

新增或更新测试集中放在现有文件：

- `tests/test_VerilogLexer.py`
- `tests/test_VerilogParser.py`

### Lexer focused tests

```python
def test_at_is_recognized_unsupported_not_invalid():
    lexer = VerilogLexer()
    lexer.input("@")
    assert lexer.token() is None
    diagnostic = lexer.get_diagnostics()[0]
    assert diagnostic.kind == "recognized_unsupported"
    assert diagnostic.spelling == "@"
    assert "current parser subset" in diagnostic.message
```

```python
def test_generate_keyword_is_recognized_unsupported():
    lexer = VerilogLexer()
    lexer.input("generate")
    assert lexer.token() is None
    diagnostic = lexer.get_diagnostics()[0]
    assert diagnostic.code == "VLEX_UNSUPPORTED_KEYWORD"
    assert diagnostic.kind == "recognized_unsupported"
```

```python
def test_unknown_control_character_is_invalid():
    lexer = VerilogLexer()
    lexer.input("\x01")
    assert lexer.token() is None
    diagnostic = lexer.get_diagnostics()[0]
    assert diagnostic.kind == "invalid"
```

### Parser boundary tests

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
def test_unsupported_generate_keyword_fails_without_partial_ast():
    parser = VerilogParser()
    with pytest.raises(VCGParseError) as exc_info:
        parser.parse_string("module m; generate endgenerate endmodule")
    assert parser.get_module_info() is None
    assert "generate" in str(exc_info.value)
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
def test_trailing_garbage_after_module_fails():
    parser = VerilogParser()
    with pytest.raises(VCGParseError):
        parser.parse_string("module m; endmodule garbage")
```

## 兼容性

保持不变：

- `VerilogLexer.input(data)`
- `VerilogLexer.token()`
- `VerilogParser.parse_string(verilog_code)`
- `VerilogParser.parse_file(filepath)`
- `VerilogParser.get_module_info()`
- 外部仍捕获 `VCGParseError`，不需要知道 `FrontendDiagnostic`。

新增 API：

- `VerilogLexer.get_diagnostics()`
- `VerilogLexer.reset_diagnostics()`
- `VerilogParser.get_diagnostics()`

明确破坏的错误兼容性：

- 坏输入或当前 unsupported construct 不再返回 partial AST。
- 失败后 `get_module_info()` 返回 `None`，不会返回上次成功结果。

## 实施顺序

1. 新增 `src/VerilogDiagnostics.py`。
2. 给 `VerilogLexer` 增加 diagnostics 状态和分类表。
3. 修改 `t_error()` 和 `t_ID()`，记录 recognized_unsupported / invalid。
4. 给 `VerilogParser` 增加 `_diagnostics`、`get_diagnostics()`、
   `_reset_parse_state()`、`_record_parse_error()`。
5. 修改 `parse_string()` 成唯一成功边界。
6. 修改 `p_error()` 和 AST build failure 路径，写结构化 diagnostics。
7. 更新 focused tests。
8. 更新 `src/verilog.bnf`。
9. 运行 TASK-10 验证命令。

## 验证命令

```bash
uv run pytest tests/test_VerilogLexer.py tests/test_VerilogParser.py -q
uv run pytest tests/test_VerilogPreprocess.py tests/test_VerilogParser.py -q
```

建议设计确认后实现阶段补充运行：

```bash
uv run pytest tests -q
```

## 风险和控制

- **风险：unsupported keyword 被跳过后 Parser 仍能构造 AST。**
  控制：Parser 最终统一检查 lexer diagnostics，并在 raise 前清空 `self.ast`。

- **风险：把 future token 写成 invalid。**
  控制：维护显式 `UNSUPPORTED_*` 表，并在 tests 中覆盖 `@`、`.`、`::`、`generate`。

- **风险：TASK-10 侵入 TASK-11 的 token 契约。**
  控制：TASK-10 只分类和失败，不重写数字/字符串 token spelling 规则。

- **风险：`p_error()` 恢复策略仍不优雅。**
  控制：TASK-10 只保证最终失败；完整 grammar cleanup 留给 TASK-13。
