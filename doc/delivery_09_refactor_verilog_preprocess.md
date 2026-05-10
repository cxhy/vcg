# DELIVERY: TASK-09

| 字段 | 值 |
|------|----|
| 任务 | `doc/task_09_refactor_verilog_preprocess.md` |
| 负责 | vcg-python-dev |
| 日期 | 2026-05-11 |
| 状态 | delivered_for_verification |

## 修改文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `src/VerilogPreprocess.py` | 修改 | 重排为整文件条件编译、active line stream、module span 选择、声明抽取的数据流。 |
| `tests/test_VerilogPreprocess.py` | 修改 | 增加 TASK-09 行为测试，覆盖整文件宏上下文、include guard、字符串扫描、target module、unsupported directive/include。 |

## 实现摘要

- `preprocess_string()` / `preprocess_file()` 新增可选 `target_module` 参数，旧调用保持兼容。
- 新增私有 `SourceLine` / `ModuleSpan`，保留原始行号和可见代码，给后续 source location 扩展留位置。
- 条件编译现在先在整文件范围处理，再定位目标 module，修复 module 前 ``define`` 和 include guard 被提前裁掉的问题。
- 声明抽取只输出 module header、body 端口声明、body `parameter` / `localparam`、`endmodule`。
- 注释扫描现在区分字符串，字符串内 `//`、`/* */`、`;` 不再影响 directive 或语句结束判断。
- active ``include`` / 其他 unsupported directive 如果出现在目标声明抽取范围内，会抛 `VCGParseError`；目标范围外仍可丢弃。
- 未实现 include 展开、SystemVerilog import、resolver、搜索根或 package 文件读取。

## 兼容性说明

- `VerilogPreprocess(macros=None)`、`read_file()`、`preprocess_string(code)`、`preprocess_file(path)`、`process_conditional_compilation()`、`get_macros()` 保持可用。
- `clear_macros()` 补充返回类型 `-> None`，运行时行为不变。
- `remove_pre_module_content()` / `extract_module_ports_section()` 保留为兼容 wrapper，不再作为核心数据流。
- 未传 `target_module` 时仍默认选择第一个 active module。
- 空文件和无 module 文件继续返回空字符串。

## 需要验证的测试点

1. module 前 ``define`` 能影响 module 内 ``ifdef``。
2. include guard 包裹整个 module 时不再出现孤立 ``endif``。
3. 位宽和参数表达式中的 object-like macro reference 保留原文，不展开为宏值。
4. 字符串字面量中的注释符和分号不会影响扫描。
5. 多 module 文件默认选择第一个 active module；显式 `target_module` 可选择后续 module。
6. active ``include`` 或 unsupported directive 位于目标声明范围内时抛 `VCGParseError`。
7. 非声明型 body item 不进入 parser 输入，不污染后续声明抽取。
8. Parser、InstanceManager、WiresManager 旧调用不受新可选参数影响。

## 已运行验证

```bash
uv run pytest tests/test_VerilogPreprocess.py::TestTask09PreprocessRefactorBehavior -q
```

结果：`14 passed`

```bash
uv run pytest tests/test_VerilogPreprocess.py tests/test_VerilogParser.py -q
```

结果：`177 passed`

```bash
uv run pytest tests/test_vcg_instance_manager.py tests/test_vcg_wires_manager.py -q
```

结果：`91 passed`

```bash
uv run pytest tests -q
```

结果：`693 passed`

## 对下游模块的影响

- `VerilogParser.py` 仍通过 `preprocess_string(verilog_code)` 旧签名调用，不需要适配。
- `InstanceManager` / `WiresManager` 的 `module_name` 仍未贯通到 parser；这属于后续任务。
- Parser 仍可能受 Lexer/Parser 自身 MACRO_ID 契约限制影响；本任务只保证 Preprocess 保留 macro reference 原文。
- include/import 的显式搜索根接口仍是未来设计，不在本交付中落地。

## 偏离任务单

无功能偏离。实现了任务单允许的 `target_module` 可选参数，并保留旧 helper wrapper。
