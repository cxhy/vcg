# DELIVERY: TASK-08

## 修改文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `src/vcg_wires_manager.py` | 修改 | 拆分 WiresManager 的 pattern 校验、端口声明生成、宽度选择、宽度格式化、对齐和渲染职责；补齐 VCGSyntaxError / VCGRuntimeError 透传；修复空白分隔多维 range 识别。 |
| `tests/test_vcg_wires_manager.py` | 重写 | 将旧的弱断言和无效 `VerilogParser` patch 改为实例 parser 替换、真实 parser smoke 和精确字符串断言；覆盖 TASK-08 指定行为矩阵。 |
| `doc/task_08_refactor_vcg_wires_manager.md` | 新增 | 记录架构任务单、接口约束、测试要求和验收标准。 |

## 实现要点

1. `generate_wires_def()` 保留公开签名和输出格式，内部改为 `_validate_pattern()`、`_get_ports_by_direction()`、`_generate_wire_declarations()` 串联。
2. `_format_wire_declaration()` 变成薄组合层，实际职责拆到 `_resolve_effective_width()`、`_format_wire_width()`、`_render_wire_declaration()`、`_pad_prefix()`。
3. `_is_multi_dimensional()` 改为正则识别 `(\[[...]\]\s*){2,}`，支持 `[7:0][3:0]`、`[7:0] [3:0]`、`[7:0]\t[3:0]`。
4. `_generate_single_wire()` 删除 lazy/greedy 不可达防御分支，保留六种 rule match 行为。
5. 清理未使用 import，并将类型注解更新为 `str | None`、`list[PortInfo]`。

## 需要验证的测试点

1. 正常路径：真实 parser 解析 V2001 样例，greedy 生成全部 wire 声明。
2. 方向过滤：`None`、`INPUT`、`Output`、`inout` 输出精确匹配。
3. 生成模式：greedy/lazy 下 rule matched、空 wire name、未匹配的六种组合。
4. 宽度格式：标量、整数、数字字符串、单维 range、多维 range、参数化宽度、表达式宽度。
5. 异常路径：`VCGFileError` / `VCGParseError` / `VCGSyntaxError` 透传，未知异常包装为 `VCGRuntimeError` 且保留 `__cause__`。
6. 对齐：默认 spacing、自定义 spacing、长 prefix 单空格分隔。

## 对下游模块的影响

公开 API 未变化，`src/vcg_execution_engine.py` 不需要适配。`VCGRuleManager.resolve_wire_generation()` 的四元组契约保持不变。

## 开发阶段验证

| 命令 | 结果 |
|------|------|
| `uv run pytest tests/test_vcg_wires_manager.py::TestTask08RefactorContract -q` | 初始 RED：3 failed, 12 passed；修复后该临时测试矩阵已合入重写后的测试文件。 |
| `uv run pytest tests/test_vcg_wires_manager.py -q` | `51 passed` |
