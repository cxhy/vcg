# VERIFICATION: TASK-10

| 字段 | 值 |
|------|----|
| 任务 | `doc/task_10_parser_diagnostic_contract.md` |
| 设计 | `doc/design_10_parser_diagnostic_contract.md` |
| 交付 | `doc/delivery_10_parser_diagnostic_contract.md` |
| 负责 | vcg-python-tester |
| 日期 | 2026-05-11 |
| 状态 | passed |

## 测试结果

| 命令 | 结果 |
|------|------|
| `uv run pytest tests/test_VerilogLexer.py::TestTask10LexerDiagnostics -q` | `3 passed` |
| `uv run pytest tests/test_VerilogParser.py::TestTask10ParserDiagnosticContract -q` | `4 passed` |
| `uv run pytest tests/test_VerilogLexer.py tests/test_VerilogParser.py -q` | `245 passed` |
| `uv run pytest tests/test_VerilogPreprocess.py tests/test_VerilogParser.py -q` | `184 passed` |
| `uv run pytest tests -q` | `703 passed` |

## 覆盖场景

| 场景 | 类别 | 结果 |
|------|------|------|
| `@` 记录为 `recognized_unsupported` | Lexer 边界 | PASS |
| `generate` 记录为 `VLEX_UNSUPPORTED_KEYWORD` | Lexer 边界 | PASS |
| 未知控制字符记录为 `invalid` | Lexer 异常路径 | PASS |
| `module m(input a@); endmodule` 抛 `VCGParseError` | Parser fail-loud | PASS |
| parser-visible garbage 不返回 partial AST | Parser fail-loud | PASS |
| 同一 Parser 成功后再失败不复用 stale AST | 回归 | PASS |
| Lexer + Parser 组合回归 | 回归 | PASS |
| Preprocess + Parser 组合回归 | 回归 | PASS |
| 全量测试套件 | 回归 | PASS |

## 功能点核对

| 功能点 | 验证结论 |
|--------|----------|
| F10.1 结构化 frontend diagnostic | PASS，`FrontendDiagnostic` 和 `SourceLocation` 已存在并由测试间接覆盖。 |
| F10.2 Lexer diagnostics | PASS，unsupported / invalid 均有 focused tests。 |
| F10.3 Parser 唯一成功边界 | PASS，lexer diagnostics 和 parser diagnostics 均阻止 AST 返回。 |
| F10.4 Parser 状态重置 | PASS，stale AST 回归测试通过。 |
| F10.5 错误消息聚合 | PASS，`VCGParseError` 包含 offending spelling 和 current subset 信息。 |
| F10.6 BNF 同步 | PASS，`src/verilog.bnf` 已包含 recognized unsupported 与 invalid 诊断契约。 |

## 发现的问题

未发现阻塞或回归问题。

## 剩余风险

- `p_error()` 的恢复策略仍保持旧实现；TASK-10 通过最终 fail-loud 边界兜住成功语义，
  完整 grammar cleanup 仍应在 TASK-13 处理。
- 数字和字符串 token spelling 仍未在 TASK-10 中全面重写；应按 TASK-11 / TASK-15
  继续推进。
