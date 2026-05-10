# TASK-07: Refactor VCG Instance Manager

| 字段 | 值 |
|------|----|
| 负责 | vcg-python-dev -> vcg-python-tester -> vcg-verilog-checker |
| 依赖 | TASK-05 |
| 状态 | completed |
| 创建 | 2026-05-10 |

## 需求描述

`src/vcg_instance_manager.py` 已修复端口计数 bug，但仍用 `port_connections` 与 `port_infos` 两个 dict 表达同一组端口连接。渲染层需要靠 key 同步检查，数据结构没有表达完整事实。本任务将端口/参数连接改为不可变结构化对象，清理渲染重复逻辑，并收紧异常透传边界。

## 范围

本任务只修改：

- `src/vcg_instance_manager.py`
- `tests/test_vcg_instance_manager.py`
- TASK-07 交付、验证、Verilog 检查文档
- `doc/refactor_backlog_2026-05-10.md`

不修改：

- `src/vcg_wires_manager.py`
- `src/vcg_rule_manager.py`
- `src/VerilogParser.py`
- 现有 public CLI 行为

## 接口约束

### 保持兼容

- `InstanceManager(rule_manager, macros=None)` 构造方式不变。
- `generate_instance(file_path, module_name, instance_name) -> str` 输出格式保持兼容。
- `set_alignment(align: int)` / `get_alignment() -> int` 保留。
- 默认 alignment 仍为 `18`。
- 参数和端口输出顺序仍由 AST 返回顺序决定。

### 新增内部数据结构

```python
@dataclass(frozen=True)
class PortConnection:
    port: PortInfo
    signal: str

@dataclass(frozen=True)
class ParameterConnection:
    parameter: ParameterInfo
    value: str
```

约束：

- `_generate_port_connections()` 返回 `list[PortConnection]`。
- `_generate_param_connections()` 返回 `list[ParameterConnection]`。
- 渲染层不再使用两个 dict 并行传递。
- 渲染层不再检查 `if port_name in port_infos`。

### 异常处理

- `VCGFileError`、`VCGParseError`、`VCGSyntaxError`、`VCGRuntimeError` 直接透传。
- 未知异常包装为 `VCGRuntimeError(... ) from e`。

## 验收标准

1. 新增或更新测试覆盖：
   - `PortConnection` / `ParameterConnection` 是 frozen dataclass。
   - `_generate_port_connections()` 返回结构化列表并保持顺序。
   - `_generate_param_connections()` 返回结构化列表并跳过未覆盖参数。
   - 渲染输出与旧格式兼容，包括参数逗号、端口逗号、注释、alignment。
   - `VCGRuntimeError` 从 rule manager 直接透传，不被重新包装。
2. 编译通过：
   - `uv run python -m py_compile src\vcg_instance_manager.py`
3. 聚焦测试通过：
   - `uv run pytest tests/test_vcg_instance_manager.py -v`
4. 回归测试通过：
   - `uv run pytest tests/test_vcg_execution_engine.py -v`
   - `uv run pytest tests/ -v`
5. Verilog checker 用真实小模块生成 instance，检查语法结构、端口顺序、参数覆盖、注释格式。

## 风险

- 输出格式隐藏兼容风险高。应避免自适应 alignment 改变旧输出，本任务只清内部结构。
- 旧测试大量使用 MockPortInfo，其 `port_type` 可能是字符串。`_generate_port_comment()` 需要保持兼容。
- 公开 `set_alignment/get_alignment` 已有测试，不删除。
