# 2026-05-10 重构剩余清单

| 字段 | 值 |
|------|----|
| 来源 | 最初 `doc/review/00_INDEX.md` + 当前提交记录 + TASK-01..05 |
| 状态 | updated |
| 更新 | 2026-05-10 |

## 当前结论

最初 review 覆盖的 12 个主要 Python 文件中，核心 P0/P1 问题已经完成大半。当前不应再重复启动
`VerilogAst.py`、`vcg_file_processor.py`、`VerilogPreprocess.py`、`vcg_execution_engine.py`、
`vcg_logger.py`、`vcg_rule_manager.py` 的同类重构任务，除非后续验证发现回归。

剩余值得开 TASK 的模块主要是：

1. `src/vcg_instance_manager.py`
2. `src/vcg_wires_manager.py`
3. `src/VerilogLexer.py`
4. `src/VerilogParser.py` 的异常类型收尾

`src/vcg_exceptions.py` 已完成 TASK-05，但尚未提交时，本文件按“已完成实现、待提交”记录。

## 已完成或基本完成

| 模块 | 状态 | 依据 |
|------|------|------|
| package/CLI import 路径 | 已完成关键修复 | `3c1c70c refactor: package src/ and move CLI entry to project root` |
| `src/VerilogAst.py` | TASK-01 完成 | `doc/task_01_refactor_verilogast.md`、`doc/check_01_refactor_verilogast.md` |
| `src/vcg_file_processor.py` | TASK-02 完成 | `20c8850 refactor: restructure VCG file processor` |
| `src/VerilogPreprocess.py` | TASK-03 完成 | `7c679f6 refactor: restructure Verilog preprocessor` |
| `src/vcg_execution_engine.py` | TASK-04 完成 | `f4fe971 refactor: simplify VCG execution engine` |
| `src/vcg_exceptions.py` | TASK-05 已实现，待提交 | `doc/task_05_refactor_vcg_exceptions.md` |
| 根目录 `vcg.py` | TASK-06 已实现，待提交 | `doc/task_06_refactor_cli_entry.md` |
| `src/vcg_logger.py` | 已完成手工重构 | `doc/delivery_manual_vcg_logger_refactor.md` |
| `src/vcg_rule_manager.py` | 已完成结构性重构 | `936dfdb refactor: harden rule manager` |
| `src/VerilogLexer.py` 字符串转义 bug | 已完成关键修复 | `18a3c94 fix: correct STRING_LITERAL escape order in lexer` |
| `src/VerilogLexer.py` 死代码清理 | 已做一轮 | `a074837 refactor: clean up VerilogLexer.py dead code and normalize error handling` |
| `src/VerilogParser.py` silent failure | 已完成一轮结构性重构 | `12931bd refactor: Parser error handling + drop unused always/begin/end grammar` |
| `src/vcg_instance_manager.py` 端口计数恒 0 | 已完成关键修复 | `2f9ecd5 fix: count port connections directly instead of grepping generated text` |

## P0：建议下一批任务

### TASK-07 候选：`src/vcg_instance_manager.py`

这个模块真 bug 已修，但结构仍偏字符串渲染脚本。适合做一次数据结构和渲染层分离。

主要问题：

- `_generate_port_connections()` 返回两个 dict：`connections` 和 `port_infos`，靠 key 同步。
- 渲染层仍检查 `if port_name in port_infos`，说明数据结构没有表达完整事实。
- `_ALIGN = 18` 是实例属性魔法数，且注释列使用 `_ALIGN * 2`。
- `_render_parameter_section()` 与 `_render_port_section()` 都重复处理“最后一项不加逗号”。
- `set_alignment()` / `get_alignment()` 是公开 API，需保留或通过测试确认迁移策略。
- `except Exception` 仍包装为 `VCGRuntimeError`，需要明确 VCG 子类透传边界。

建议范围：

- 引入 `PortConnection(frozen=True)` 和 `ParameterConnection(frozen=True)`。
- 渲染函数接受结构化列表，而不是多 dict 并行传递。
- 抽出逗号渲染 helper，保持输出完全兼容。
- 保留 `set_alignment()` / `get_alignment()`，避免破坏既有测试和用户 API。

### TASK-08 候选：`src/vcg_wires_manager.py`

该模块和 InstanceManager 对称，但风险点集中在宽度格式化。建议先做低风险拆分，不要直接引入复杂 ADT。

主要问题：

- `width` 同时表示 int、数字字符串、range string、表达式、多维数组字符串。
- `_format_wire_width()` 通过 `isdigit()`、`startswith("[")`、operator sniffing 分类。
- `_is_multi_dimensional()` 只识别紧贴的 `']['`，对 `[3:0] [7:0]` 这类空格形式漏判。
- `_format_wire_declaration()` 混合宽度选择、对齐和最终声明拼接。
- `except Exception` 仍包装为 `VCGRuntimeError`，需要与全仓异常纪律一致。

建议范围：

- 先拆 `_resolve_width_text()`、`_format_spacing()`、`_render_wire_declaration()`。
- `_is_multi_dimensional()` 改为基于 bracket pair 计数或正则，覆盖空格形式。
- 保持现有输出格式和 `set_base_spacing()` / `get_base_spacing()` API。
- 宽度 ADT 化单独评估，不要和低风险清理混在同一个 TASK。

## P1：Parser/Lexer 收尾

### TASK-09 候选：`src/VerilogLexer.py`

Lexer 已做过字符串转义和死代码清理，但还没有完整收敛 token 策略。

剩余问题：

- 是否应该抛 `VCGSyntaxError` 仍需确认，目前更多是返回 lexer token / parser 统一处理。
- `ID` 规则对反引号宏、`$system_task` 的边界需要重新明确。
- 关键字表和 token 列表是否仍存在重复真相，需要继续收敛。
- `build()` / `input()` / `token()` 的 lazy build 行为和类型注解可进一步清理。

建议先写架构任务单，明确宏和 system task 是 Lexer 责任、Preprocess 责任，还是 Parser 责任。

### TASK-10 候选：`src/VerilogParser.py`

Parser 已经完成 silent failure 的一轮结构性修复，当前不建议做大重构，只做异常语义收尾。

剩余问题：

- `parse_string()` 仍有未知异常包装为 `VCGParseError` 的兜底，需要确认是否所有 VCG 子类都透传。
- 当前很多语法错误仍归入 `VCGParseError`，是否改为 `VCGSyntaxError` 需要和 Lexer 一起决策。
- 旧 `typing.Optional/Dict/List` 风格可以后续顺手清理，但不是单独重构理由。

建议与 TASK-09 绑定或排在其后。

## P2：横切清理项

### 全仓异常处理统一

当前仍可搜到 `except Exception`，但不是所有兜底都要删除。每个模块重构时采用同一纪律：

- VCG 子类直接透传。
- 未知异常包装时必须 `raise ... from e`。
- 不把运行时错误伪装成 parse/file error。
- CLI 顶层兜底可以保留，但需要拼写、日志和 debug traceback 策略。

### 类型注解现代化

部分模块仍使用 `typing.List/Dict/Optional/Tuple`。这不单独构成重构任务，但在修改模块时应顺手改为：

- `list[T]`
- `dict[K, V]`
- `T | None`
- `tuple[...]`

### Backlog 文档维护

本文件已经取代旧版“P0 仍是 file_processor/preprocess/execution_engine”的判断。后续每完成一个 TASK，应同步更新：

- 已完成模块表。
- P0/P1 顺序。
- 是否存在待提交但未提交的 TASK。

## 建议执行顺序

1. TASK-07：`src/vcg_instance_manager.py` 结构化连接数据 + 渲染清理。
2. TASK-08：`src/vcg_wires_manager.py` 宽度格式化拆分 + 多维识别修正。
3. TASK-09：`src/VerilogLexer.py` token/`VCGSyntaxError` 策略。
4. TASK-10：`src/VerilogParser.py` 异常语义收尾。
