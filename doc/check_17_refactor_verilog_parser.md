# CHECK: TASK-17 Refactor VerilogParser Grammar and Declaration Flow

| 字段 | 值 |
|------|----|
| 对应任务 | `doc/task_17_refactor_verilog_parser.md` |
| 设计文档 | `doc/design_17_refactor_verilog_parser.md` |
| 交付文档 | `doc/delivery_17_refactor_verilog_parser.md` |
| 验证文档 | `doc/verification_17_refactor_verilog_parser.md` |
| 负责 | vcg-verilog-checker |
| 状态 | CHECKED |
| 日期 | 2026-05-12 |

## AST 正确性检查

| 检查项 | 结果 | 说明 |
|--------|------|------|
| ANSI 同组端口继承方向和位宽 | PASS | `module m(input [7:0] a, b, output reg q, r); endmodule` 解析为 `a/b input wire [7:0]`，`q/r output reg`。 |
| Header parameter/localparam 同组继承 | PASS | `module m #(parameter A=1, B=2, localparam C=3, D=4); endmodule` 解析为 `A/B parameter`，`C/D localparam`。 |
| V95 header name list + body declaration | PASS | `module m(a,b); input [3:0] a,b; endmodule` 解析为 `a/b input wire [3:0]`。 |
| Mixed header/body last update | PASS | `module m(input wire clk, a, b); output b; endmodule` 最终 `clk/a input`，`b output`，符合 last-update-wins 兼容预期。 |
| assign 泄漏 fail-loud | PASS | `assign x = a;` 抛 `VCGParseError`，不返回 AST。 |
| positional instance 泄漏 fail-loud | PASS | `child u0(a);` 抛 `VCGParseError`，不返回 AST。 |
| named instance 泄漏 fail-loud | PASS | `child u0 (.a(a));` 抛 `VCGParseError`，不返回 AST。 |

## BNF 同步检查

| 检查项 | 结果 | 说明 |
|--------|------|------|
| Flat ANSI header grammar | PASS | `src/verilog.bnf` 记录 `ansi_port_header_list` / `ansi_port_header_next` flat element grammar；`src/VerilogParser.py` 使用同名 PLY rules 和 `_coalesce_ansi_port_elements()`。 |
| Flat parameter header grammar | PASS | BNF 记录 `parameter_header_list` / `parameter_header_next`；Parser 使用 `ParameterHeaderElement` 和 `_coalesce_parameter_header_elements()` 支持 continuation assignment。 |
| 无 `ignored_body_item` parser 成员 | PASS | `rg` 未发现 `ignored_body_item`；BNF 明确 non-declaration body item 泄漏必须 fail loud。 |
| 无 assign/instance AST-silent body rule | PASS | Parser 中无 `module_item_assignment` / `module_item_instance`；`ASSIGN` 仅保留为 lexer token，不在 body grammar 中消费。 |
| Body syntax fail-loud | PASS | `module_item` 只接受 declaration；泄漏的 assign/instance 触发 parser diagnostics 并抛 `VCGParseError`。 |
| 无 fallback declaration/expression 写入 | PASS | error productions 记录 diagnostics，`param_assignment` 错误返回 `None`，参数列表只接受 `ParameterDeclarator`；bit-select/part-select/concat 错误不生成 `?` 或 `{?}` spelling。 |

## 发现的问题

未发现需要反馈给 architect 或 dev 的产品问题。

观察项：assign / instance 泄漏时当前 parser 会产生多条级联 syntax diagnostics，例如 assign 输入为 5 条、positional instance 为 6 条、named instance 为 10 条。该行为仍满足 TASK-17 的 fail-loud 要求，因为 `parse_string()` 抛 `VCGParseError` 且不返回 AST。

## 命令证据

```bash
uv run pytest tests/test_VerilogParser.py::TestTask17VerilogParserRefactor -q
# 14 passed in 1.12s
```

```bash
uv run python -c "<TASK-17 AST smoke script>"
# ansi [('a', 'input', 'wire', '[7:0]'), ('b', 'input', 'wire', '[7:0]'), ('q', 'output', 'reg', ''), ('r', 'output', 'reg', '')] []
# params [] [('A', 'parameter', '1'), ('B', 'parameter', '2'), ('C', 'localparam', '3'), ('D', 'localparam', '4')]
# v95 [('a', 'input', 'wire', '[3:0]'), ('b', 'input', 'wire', '[3:0]')] []
# mixed [('clk', 'input', 'wire', ''), ('a', 'input', 'wire', ''), ('b', 'output', 'wire', '')] []
# assign VCGParseError Parse failed with 5 diagnostics:
# posinst VCGParseError Parse failed with 6 diagnostics:
# namedinst VCGParseError Parse failed with 10 diagnostics:
```

```bash
rg -n "ignored_body_item|module_item_assignment|module_item_instance|ASSIGN|assign|instance|fallback|\\?\\}|\\[\\?\\]|parameter_header|ansi_port_header|error" src/VerilogParser.py src/verilog.bnf
# No ignored_body_item, module_item_assignment, or module_item_instance parser rule found.
# BNF and parser both show flat parameter_header / ansi_port_header grammar.
# ASSIGN appears only as supported lexer token / fail-loud documentation, not as parser body item.
```

## 结论

TASK-17 Verilog/AST check 通过。未写 `doc/feedback_17_refactor_verilog_parser.md`。
