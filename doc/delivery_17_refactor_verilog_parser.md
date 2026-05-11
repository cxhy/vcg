# DELIVERY: TASK-17 Refactor VerilogParser Grammar and Declaration Flow

## 修改文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `src/VerilogDeclarations.py` | 新增 | 增加 parser-facing frozen declaration dataclass：range、port group、ANSI port element、parameter group、parameter header element。 |
| `src/VerilogParser.py` | 修改 | 重写 header port/parameter grammar 为 flat element + coalescing helper；body 声明复用 declaration group；删除 assign/instance 无 AST 消费规则；error production 不再返回 fallback declaration/expression。 |
| `src/verilog.bnf` | 修改 | 同步 TASK-17 parser 子集，记录 flat header grammar、body non-declaration fail-loud、error production 同步约束。 |
| `tests/test_VerilogParser.py` | 修改 | 新增 `TestTask17VerilogParserRefactor` 覆盖 A17.1-A17.7；收紧缺失 `endmodule`、大量端口/参数、undefined macro 的弱断言。 |
| `doc/parser_refactor_tasks.json` | 修改 | 将 TASK-17 dev 阶段更新为 delivered_for_verification，并记录 changed_files、validation、history。 |

## 设计偏差

- ANSI port header 按设计采用 flat `AnsiPortHeaderElement` grammar 加 `_coalesce_ansi_port_elements()`。
- Header parameter 也采用同类 flat `ParameterHeaderElement` 加 `_coalesce_parameter_header_elements()`，而不是直接使用 `parameter_declaration_group` list。原因是 `parameter A=1, parameter B=2` 与 `parameter A=1, B=2` 共享逗号分隔符，flat element 能同时支持重复 keyword 和同组继承，避免 PLY 逗号二义性。
- Parser 构建使用 `errorlog=yacc.NullLogger()`，避免 TASK-17 后 `ASSIGN` unused token warning 写入全局 stderr，污染无关测试。Lexer token contract 未修改。

## Yacc 构建情况

独立默认 PLY 构建命令：

```bash
uv run python -c "import ply.yacc as yacc; from src.VerilogParser import VerilogParser; p=VerilogParser(); yacc.yacc(module=p, debug=False, write_tables=False); print('PLY parser build completed')"
```

结果：

- `PLY parser build completed`
- 无 shift/reduce 或 reduce/reduce conflict 输出。
- 仅有预期 warning：`Token 'ASSIGN' defined, but not used` / `There is 1 unused token`。这是 TASK-17 删除 parser assign 消费规则后的结果。

## 运行命令和结果

```bash
uv run pytest tests/test_VerilogParser.py::TestTask17VerilogParserRefactor -q
# 10 passed in 0.86s

uv run pytest tests/test_VerilogParser.py -q
# 109 passed in 6.67s

uv run pytest tests/test_VerilogPreprocess.py tests/test_VerilogParser.py -q
# 194 passed in 9.70s

uv run pytest tests/test_VerilogLexer.py tests/test_VerilogParser.py -q
# 255 passed in 9.85s

uv run pytest tests -q
# 713 passed in 12.35s
```

## 需要 tester 关注

1. 复核 header parameter flat element 设计偏差是否满足 F17.3 且没有扩大 data type 范围。
2. 验证 `assign`、positional instance、named instance 泄漏时均 fail loud，且不返回 partial AST。
3. 检查 error production 在参数、位选、拼接错误输入下不会写入 `''`、`?`、`{?}` fallback。
4. 关注 mixed V95/V2001 port header 的 last-update-wins 行为是否仍符合当前兼容预期。
