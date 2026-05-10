# DELIVERY: TASK-03

## 修改文件清单
| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `src/VerilogPreprocess.py` | 修改 | 重构条件编译状态机、文件异常处理、module/端口/参数提取逻辑；移除调试入口和注释死代码。 |
| `doc/delivery_03_refactor_verilog_preprocess.md` | 新增 | 记录 dev 阶段交付内容、验证点、下游影响和风险。 |

## 实现摘要
1. 保留 `VerilogPreprocess` 公开 API，不改 `VerilogParser` 调用链。
2. 新增 frozen dataclass `ConditionalFrame`，替代 dict 条件栈。
3. 支持活动分支内的 ``define`` / ``undef`` 更新 `self.macros`，影响后续 ``ifdef`` / ``ifndef`` / ``elsif`` 判断；不展开宏体。
4. 条件编译扫描会剥离 `//`、行尾 `//`、`/* ... */` 中的内容，注释内预处理指令不影响条件栈。
5. orphan ``else`` / ``elsif`` / ``endif``、重复 ``else``、``else`` 后 ``elsif``、未闭合条件块均抛 `VCGParseError`。
6. `read_file()` 使用 `Path.read_text()`，UTF-8 失败后 fallback latin-1；文件读写问题抛 `VCGFileError`。
7. `preprocess_file()` / `preprocess_string()` 保留 `ValueError` 输入契约，透传 VCG 异常，未知异常包装为 `VCGParseError` 并使用 `raise ... from e`。
8. module header 和声明提取使用去注释后的分号判断，避免注释中的 `;` 截断 header/声明；`localparam` 已纳入声明提取。
9. `remove_pre_module_content()` 保留紧邻 module 前的 Verilog attribute 行。

## feedback 修复记录
2026-05-10 根据 `doc/feedback_03_refactor_verilog_preprocess.md` 修复 checker 发现的块注释泄漏问题：

1. 根因：`extract_module_ports_section()` 外层维护了跨行块注释状态，但 `_collect_declaration()` 内部重新用无状态 `_strip_line_comment()` 判断声明开始，导致块注释内部的 `input hidden;` 被当作真实声明。
2. 修复：声明开始、声明结束和最终输出行统一使用外层按行扫描得到的跨行去注释可见代码。
3. 修复：纯块注释内部文本不再追加到预处理输出，块注释结束行只保留注释外的可见代码。
4. 验证样例：`block_comment_leak` 中块注释内的 `input hidden;` 不再出现在 `preprocess_string()` 输出中。

## 需要验证的测试点
1. 正常路径：ANSI header、多行端口、V95 端口声明、`parameter` / `localparam` 能保留到预处理输出。
2. 条件路径：``define`` 后 ``ifdef`` 生效，``undef`` 后 ``ifdef`` 失效；``ifndef`` / ``elsif`` / ``else`` 嵌套分支选择正确。
3. 注释路径：整行 `//`、行尾 `//`、块注释中的预处理指令不改变条件栈；注释中的 `;` 不结束 header/声明。
4. 异常路径：孤立条件指令和未闭合条件块抛 `VCGParseError`；缺失文件抛 `VCGFileError`。
5. 链路回归：`tests/test_VerilogParser.py` 应继续通过，确认 Parser 链路无需修改。

## 已运行验证
| 命令 | 结果 |
|------|------|
| `uv run python -m py_compile src\VerilogPreprocess.py` | 通过 |
| `uv run pytest tests\test_VerilogParser.py -v` | 94 passed |
| 自定义 `uv run python -` smoke | 通过：覆盖 ``define`` / ``undef``、注释指令忽略、注释分号、`VCGParseError`、`VCGFileError` |
| `uv run pytest tests\test_VerilogPreprocess.py -v` | 50 passed, 4 failed |
| feedback inline smoke: `uv run python -` | 通过：块注释中的 `input hidden;` 不出现在预处理输出 |

## 已知测试偏差
`tests/test_VerilogPreprocess.py` 的 4 个失败来自旧契约断言，和 TASK-03 的兼容性要求一致：

1. `read_file()` 缺失文件旧预期 `FileNotFoundError`，新实现抛 `VCGFileError`。
2. `preprocess_file()` 缺失文件旧预期 `FileNotFoundError` / `RuntimeError`，新实现抛 `VCGFileError`。
3. 未闭合 ``ifdef`` 旧预期不崩溃，新实现抛 `VCGParseError`。
4. 多余 ``endif`` 旧预期安全忽略，新实现抛 `VCGParseError`。

## 对下游模块的影响
- `VerilogParser.parse_string()` / `parse_file()` 无需接口适配，Parser 聚焦测试已通过。
- 预处理输出仍是 `module header + 端口/参数声明 + endmodule`。
- 条件编译结构错误现在会更早以 `VCGParseError` 暴露，tester 需要按 TASK-03 更新旧宽松测试断言。

## 偏差和风险
- 未实现完整宏展开、函数式宏、``include`` 展开，符合 TASK-03 非目标。
- `define NAME value` 仅记录宏名和值用于后续条件判断和 `get_macros()`，不会替换源码中的宏引用。
- 声明提取仍以 VCG 当前 Parser 可消费的 module header / port / parameter 子集为边界，不声明支持完整 SystemVerilog 语法。
