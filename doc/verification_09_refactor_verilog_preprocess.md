# VERIFICATION: TASK-09

| 字段 | 值 |
|------|----|
| 任务 | `doc/task_09_refactor_verilog_preprocess.md` |
| 交付 | `doc/delivery_09_refactor_verilog_preprocess.md` |
| 负责 | vcg-python-tester |
| 日期 | 2026-05-11 |
| 状态 | passed |

## 测试结果

| 命令 | 结果 |
|------|------|
| `uv run pytest tests/test_VerilogPreprocess.py::TestTask09PreprocessRefactorBehavior -q` | `17 passed` |
| `uv run pytest tests/test_VerilogPreprocess.py tests/test_VerilogParser.py -q` | `180 passed` |
| `uv run pytest tests/test_vcg_instance_manager.py tests/test_vcg_wires_manager.py -q` | `91 passed` |
| `uv run pytest tests -q` | `696 passed` |

## 覆盖场景

| 场景 | 类别 | 结果 |
|------|------|------|
| module 前 ``define`` 控制 module 内 ``ifdef`` | 回归 | PASS |
| include guard 包裹 module 不产生孤立 ``endif`` | 回归 | PASS |
| 位宽表达式中的 `` `WIDTH`` 保留原文 | 正常路径 | PASS |
| 参数默认值中的 macro reference 不展开 | 正常路径 | PASS |
| 字符串内 `//` / `;` 不影响扫描 | 边界 | PASS |
| 多 module 默认选择第一个 active module | 兼容 | PASS |
| `target_module` 选择第二个 module | 正常路径 | PASS |
| `target_module` 缺失或重复时抛 `VCGParseError` | 异常路径 | PASS |
| 非声明 body item 不进入输出，后续声明仍保留 | 回归 | PASS |
| active unsupported directive / ``include`` 位于声明范围内时报错 | 异常路径 | PASS |
| inactive include 位于 module 内时被条件编译移除 | 边界 | PASS |
| 字符串中的 `endmodule` 不截断 module span | 边界 | PASS |
| Parser 旧调用 `preprocess_string(code)` | 下游回归 | PASS |
| InstanceManager / WiresManager 下游调用 | 下游回归 | PASS |

## Tester 补充

Tester 在开发交付基础上补充了 3 个边界测试：

- `test_duplicate_target_module_raises_parse_error`
- `test_inactive_include_inside_module_is_ignored`
- `test_string_endmodule_does_not_terminate_inline_module`

这些测试用于覆盖 target module 二义性、inactive include、inline `endmodule` 拆分的字符串安全性。

## 发现的问题

未发现阻塞或回归问题。

## 剩余风险

- Parser/Lexer 的 `MACRO_ID` 契约仍属于后续任务；本任务只验证 Preprocess 保留 macro reference 原文。
- `target_module` 尚未从 `InstanceManager` / `WiresManager` 贯通到 Parser；本任务只提供 Preprocess 层可选参数。
- include expansion、include roots、package roots、SystemVerilog import resolver 均为未来任务，当前验证只覆盖“不展开且在声明范围内失败”的行为。
