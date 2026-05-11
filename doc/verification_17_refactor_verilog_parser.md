# VERIFICATION: TASK-17 Refactor VerilogParser Grammar and Declaration Flow

| 字段 | 值 |
|------|----|
| 对应任务 | `doc/task_17_refactor_verilog_parser.md` |
| 设计文档 | `doc/design_17_refactor_verilog_parser.md` |
| 交付文档 | `doc/delivery_17_refactor_verilog_parser.md` |
| 负责 | vcg-python-tester |
| 状态 | VERIFIED |
| 日期 | 2026-05-12 |

## 测试改动

修改 `tests/test_VerilogParser.py`，在 `TestTask17VerilogParserRefactor` 中补充 4 个验证点：

- `test_header_parameter_flat_elements_start_new_explicit_group`
- `test_error_parameter_value_does_not_leave_fallback_parameter`
- `test_error_bit_select_does_not_leave_question_fallback`
- `test_mixed_v95_v2001_body_declaration_last_update_wins`

未修改 `src/` 产品代码。

## 功能点验证

| 功能点 | 结论 | 证据 |
|--------|------|------|
| F17.1 declaration group 模型 | PASS | `src/VerilogDeclarations.py` 提供 frozen parser-facing dataclass；Parser action 使用 group/element 模型写 builder。 |
| F17.2 ANSI header port group-first | PASS | `input [7:0] a, b`、`output reg q, r`、`input a, b, output c` 聚焦测试通过。 |
| F17.3 header/body parameter group 统一 | PASS | header `parameter A=1, B=2`、`localparam A=1, B=2`、mixed flat element、body group 测试通过。 |
| F17.4 移除无 AST body item 消费 | PASS | `assign`、positional instance、named instance 泄漏均抛 `VCGParseError` 且无 partial AST。 |
| F17.5 收敛 error recovery | PASS | 参数错误值和 bit-select 错误不会留下 `P` fallback 参数或 `A[?]` fallback value；错误输入抛 `VCGParseError`。 |
| F17.6 Parser 职责清理 | PASS | 公共 API 仍由现有 parser 测试覆盖；`src/VerilogParser.py` 当前 667 行，低于 800 行。 |

## 验收项验证

| 验收项 | 结论 | 覆盖测试 |
|--------|------|----------|
| A17.1 ANSI 端口声明组继承方向和位宽 | PASS | `test_ansi_port_group_inherits_direction_and_range` |
| A17.2 ANSI 端口声明组继承 net/reg 类型 | PASS | `test_ansi_port_group_inherits_reg_type` |
| A17.3 Header parameter group 支持同声明多赋值 | PASS | `test_header_parameter_group_inherits_parameter_type` |
| A17.4 Header localparam group 支持同声明多赋值 | PASS | `test_header_localparam_group_inherits_parameter_type` |
| A17.5 Body parameter/localparam 继续一致 | PASS | `test_body_parameter_and_localparam_groups_are_consistent` |
| A17.6 Parser 不再吞 assign / instance | PASS | `test_parser_rejects_assign_if_preprocess_leaks_it`、`test_parser_rejects_positional_instance_if_preprocess_leaks_it`、`test_parser_rejects_named_instance_if_preprocess_leaks_it` |
| A17.7 V95 端口声明继续工作 | PASS | `test_v95_port_names_and_body_declaration_still_work` |

## Delivery 重点复核

| 复核点 | 结论 | 证据 |
|--------|------|------|
| header parameter flat element 设计偏差 | PASS | `parameter A=1, B=2, localparam C=3, D=4` 正确归并为两个 parameter 和两个 localparam。 |
| assign/positional/named instance fail-loud | PASS | 三类泄漏输入全部抛 `VCGParseError`，`get_module_info()` 返回 `None`。 |
| error production 不写入 fallback | PASS | 错误参数值不会写入 `P`；错误 bit select 不产生 `A[?]`。 |
| mixed V95/V2001 last-update-wins | PASS | header continuation 先给 `b` input，body `output b;` 后最终 `b.direction == "output"`。 |

## 运行命令和结果

```bash
uv run pytest tests/test_VerilogParser.py::TestTask17VerilogParserRefactor -q
# 14 passed in 1.11s

uv run pytest tests/test_VerilogParser.py -q
# 113 passed in 6.89s

uv run pytest tests/test_VerilogPreprocess.py tests/test_VerilogParser.py -q
# 198 passed in 6.95s

uv run pytest tests/test_VerilogLexer.py tests/test_VerilogParser.py -q
# 259 passed in 7.23s

uv run pytest tests -q
# 717 passed in 12.72s
```

## 发现的问题

未发现产品代码问题。未写 `doc/feedback_17_refactor_verilog_parser.md`。

## 结论

TASK-17 验证阶段通过。建议进入 `vcg-verilog-checker` 阶段，继续检查 generated Verilog / AST 语义影响。
