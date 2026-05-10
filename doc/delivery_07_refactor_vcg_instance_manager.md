# DELIVERY: TASK-07

## 修改文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `src/vcg_instance_manager.py` | 修改 | 引入结构化连接对象，清理渲染输入数据和异常透传 |
| `tests/test_vcg_instance_manager.py` | 修改 | 增加结构化连接和异常透传测试 |
| `doc/task_07_refactor_vcg_instance_manager.md` | 新增 | 定义重构边界和验收标准 |

## 实现说明

- 新增 `PortConnection(frozen=True)`，封装 `port` 与 `signal`。
- 新增 `ParameterConnection(frozen=True)`，封装 `parameter` 与 `value`。
- `_generate_port_connections()` 从 `(dict, dict)` 改为 `list[PortConnection]`。
- `_generate_param_connections()` 从 `dict` 改为 `list[ParameterConnection]`。
- `_render_instance_code()` 和 `_render_port_section()` 不再依赖双 dict key 同步。
- `_generate_port_comment()` 改为卫语句风格，保持输出兼容。
- `generate_instance()` 现在直接透传 `VCGFileError`、`VCGParseError`、`VCGSyntaxError`、`VCGRuntimeError`。
- 未知异常仍包装为 `VCGRuntimeError(... ) from e`。
- 保留 `set_alignment()` / `get_alignment()` 和默认 alignment `18`。

## 需要验证的测试点

1. `PortConnection` / `ParameterConnection` 是 frozen dataclass。
2. 端口连接生成保持 AST 顺序。
3. 参数连接只包含被规则覆盖的参数。
4. `VCGRuntimeError` 从 rule manager 抛出时原样透传。
5. 例化输出在有/无参数场景下保持原有格式。
6. 端口注释方向、net type、range string 保持兼容。
7. 端口计数日志仍使用真实连接数量。

## 对下游模块的影响

- `InstanceManager.generate_instance()` public API 不变。
- `set_alignment()` / `get_alignment()` public API 不变。
- 内部 helper `_generate_port_connections()` 和 `_generate_param_connections()` 的返回类型改变；当前仓库只有测试直接调用这些 private helper，已同步更新。
- 生成 Verilog 文本应保持兼容。

## 开发阶段验证

- RED: `uv run pytest tests/test_vcg_instance_manager.py -v` -> 4 failed, 36 passed
- GREEN: `uv run python -m py_compile src\vcg_instance_manager.py`
- GREEN: `uv run pytest tests/test_vcg_instance_manager.py -v` -> 40 passed
