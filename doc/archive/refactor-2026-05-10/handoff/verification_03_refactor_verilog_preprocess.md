# VERIFICATION: TASK-03

## 验证范围

- 读取 `doc/delivery_03_refactor_verilog_preprocess.md`，验证 `src/VerilogPreprocess.py` 的交付行为。
- 读取 `doc/feedback_03_refactor_verilog_preprocess.md`，验证 dev 对块注释端口泄漏问题的回修。
- 只修改 `tests/test_VerilogPreprocess.py`、`tests/test_VerilogParser.py` 和本验证报告。
- 未修改 `src/`。

## 测试更新

| 测试点 | 覆盖用例 | 结果 |
|--------|----------|------|
| missing file 抛 `VCGFileError` | `test_read_nonexistent_file`, `test_preprocess_file_not_found_runtime_error` | PASS |
| unclosed ifdef / extra endif 抛 `VCGParseError` | `test_unclosed_ifdef`, `test_extra_endif` | PASS |
| orphan else / elsif / endif 抛 `VCGParseError` | `test_orphan_conditional_directives_raise_parse_error` | PASS |
| `define` 后 `ifdef` 生效 | `test_define_before_ifdef_activates_branch` | PASS |
| `undef` 后 `ifdef` 失效 | `test_undef_before_ifdef_deactivates_branch` | PASS |
| 非活动分支内 `define` 不生效 | `test_define_in_inactive_branch_does_not_activate_later_ifdef` | PASS |
| 注释中的预处理指令不影响条件栈 | `test_line_comment_directives_do_not_affect_condition_stack`, `test_trailing_comment_directives_do_not_affect_condition_stack`, `test_block_comment_directives_do_not_affect_condition_stack` | PASS |
| module 前 attribute 行不导致 module 丢失 | `test_attribute_line_before_module_does_not_drop_module` | PASS |
| 注释中的 `;` 不截断 module header 或端口声明 | `test_comment_semicolon_does_not_truncate_module_header`, `test_comment_semicolon_does_not_truncate_port_declaration` | PASS |
| `localparam` 可提取 | `test_extract_localparam_declaration` | PASS |
| feedback 回归：块注释内 `input hidden;` 不泄漏到预处理输出 | `test_block_comment_port_text_does_not_leak_into_output` | PASS |
| feedback 回归：Parser AST ports 只包含真实 `clk` | `test_b14_block_comment_port_text_does_not_create_ast_port` | PASS |

## 测试结果

| 命令 | 结果 |
|------|------|
| `uv run pytest tests/test_VerilogPreprocess.py -v` | 68 passed |
| `uv run pytest tests/test_VerilogParser.py -v` | 95 passed |
| `uv run pytest tests/ -v` | 637 passed |

## 发现的问题

未发现阻断产品代码问题。`doc/feedback_03_refactor_verilog_preprocess.md` 记录的块注释跨行状态泄漏问题已由新增回归覆盖验证通过。

观察项：`remove_pre_module_content()` 会保留紧邻 module 前的 attribute 行，但 `preprocess_string()` 的最终输出在 `extract_module_ports_section()` 阶段不包含该 attribute 行。TASK-03 的验收要求是“不导致 module 丢失”，当前行为满足；交付文档“保留 attribute 行”的表述比实际最终输出更强，建议 checker 阶段确认是否需要保留到最终预处理输出。

## Feedback 回归验证

样例：

```verilog
module block_comment_leak(
  input wire clk
);
  /* `ifdef COMMENT_ONLY
     input hidden;
     `endif */
endmodule
```

- `VerilogPreprocess().preprocess_string(sample)` 输出包含真实 `clk`，不包含 `hidden`。
- `VerilogParser().parse_string(sample)` 解析后的 AST ports 为 `['clk']`，不包含 `hidden`。

## 结论

TASK-03 tester 回修验证通过。预处理器聚焦测试、Parser 链路回归和全量回归均通过；未新增或更新 feedback 文档。
