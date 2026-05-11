# DELIVERY: TASK-10

| 字段 | 值 |
|------|----|
| 任务 | `doc/task_10_parser_diagnostic_contract.md` |
| 设计 | `doc/design_10_parser_diagnostic_contract.md` |
| 负责 | vcg-python-dev |
| 日期 | 2026-05-11 |
| 状态 | delivered_for_verification |

## 修改文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `src/VerilogDiagnostics.py` | 新增 | 增加不可变 frontend diagnostic 数据模型和格式化 helper。 |
| `src/VerilogLexer.py` | 修改 | 增加 diagnostics 状态、unsupported/invalid 分类、`get_diagnostics()` / `reset_diagnostics()`。 |
| `src/VerilogParser.py` | 修改 | 增加 parser diagnostics、统一 parse 成功边界、失败前清空 AST，避免 partial/stale AST。 |
| `src/verilog.bnf` | 修改 | 补充 recognized unsupported token 和 invalid lexical input 的诊断契约。 |
| `tests/test_VerilogLexer.py` | 修改 | 新增 TASK-10 lexer diagnostics 测试，并更新旧 `@` 测试为 diagnostics 断言。 |
| `tests/test_VerilogParser.py` | 修改 | 新增 TASK-10 parser fail-loud 和 stale AST 回归测试。 |
| `doc/parser_refactor_tasks.json` | 修改 | TASK-10 状态推进到开发阶段并记录设计确认和实现开始。 |

## 实现摘要

- 新增 `FrontendDiagnostic`，字段包含 `code`、`message`、`severity`、`stage`、
  `kind`、`location` 和 `spelling`。
- Lexer 对当前子集不支持但未来可能支持的 token/keyword 记录
  `recognized_unsupported`，例如 `@`、`.`、`::`、`->`、`generate`。
- Lexer 对无法形成可靠 token 的输入记录 `invalid`。
- Parser 在 `parse_string()` 返回 AST 前聚合 lexer/parser/AST diagnostics。
  任一 error 级 diagnostic 存在时抛 `VCGParseError`。
- Parser parse 失败前会清空 `self.ast`，因此 `get_module_info()` 不会返回上一次
  成功 parse 的 stale AST。
- `parse_errors` 保留为兼容字段，但 parser 内部错误同时写入结构化 diagnostics。

## 需要验证的测试点

1. `@` 记录为 `recognized_unsupported`，message 包含 current parser subset。
2. `generate` 记录为 `VLEX_UNSUPPORTED_KEYWORD`，不作为普通 ID 静默进入 AST 路径。
3. 控制字符记录为 `invalid`。
4. `module m(input a@); endmodule` 抛 `VCGParseError`，且 `get_module_info()` 为 `None`。
5. parser-visible 垃圾 token 导致 parse failure，不能返回 partial AST。
6. 同一 parser 实例一次成功后再失败，不复用上一次 AST。

## 已运行验证

```bash
uv run pytest tests/test_VerilogLexer.py::TestTask10LexerDiagnostics -q
```

结果：`3 passed`

```bash
uv run pytest tests/test_VerilogParser.py::TestTask10ParserDiagnosticContract -q
```

结果：`4 passed`

```bash
uv run pytest tests/test_VerilogLexer.py tests/test_VerilogParser.py -q
```

结果：`245 passed`

```bash
uv run pytest tests/test_VerilogPreprocess.py tests/test_VerilogParser.py -q
```

结果：`184 passed`

```bash
uv run pytest tests -q
```

结果：`703 passed`

## 对下游模块的影响

- 外部异常类型保持 `VCGParseError` / `VCGFileError`，调用方不需要捕获新异常类型。
- 坏输入或当前 unsupported construct 不再返回 partial AST。这是 TASK-10 的预期
  错误兼容性破坏。
- `VerilogLexer.get_diagnostics()` 和 `VerilogParser.get_diagnostics()` 是新增只读
  诊断接口。
- TASK-10 未实现 `always` / `generate` / named instance / package scope grammar；
  这些仍是 future unsupported。

## 偏离设计说明

- `module m; endmodule garbage` 的 public parser 测试未作为 TASK-10 断言，因为
  TASK-09 Preprocess 会选择目标 module 并丢弃 module 外文本，Parser 看不到该
  garbage。对应测试改为 parser-visible 的
  `module m(input a) garbage; endmodule`。
- `p_error()` 的恢复策略仍保持现状，只新增结构化 diagnostic；完整 grammar cleanup
  留给 TASK-13。
