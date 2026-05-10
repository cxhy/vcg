# TASK-05: Refactor VCG Exception Hierarchy

| 字段 | 值 |
|------|----|
| 负责 | vcg-python-dev -> vcg-python-tester |
| 依赖 | TASK-01..TASK-04 |
| 状态 | completed |
| 创建 | 2026-05-10 |

## 需求描述

`src/vcg_exceptions.py` 当前只有 5 个空异常类，无法携带结构化上下文，也没有清晰的公开导出和类语义说明。需要把它提升为项目异常约定的真实接口，同时保持现有调用方兼容。

## 范围

本任务只重构 `src/vcg_exceptions.py` 及其直接测试/交付文档。

不在本任务中修改：

- `vcg.py` 的 CLI 错误处理。
- 现有调用点的异常构造文本。
- Parser/Lexer 对 `VCGSyntaxError` 的使用策略。

这些属于后续 CLI 或 Parser/Lexer 任务，避免本任务扩大为跨模块异常治理。

## 接口约束

### `VCGError`

保持向后兼容：

```python
VCGError("message")
VCGFileError("message")
VCGParseError("message")
VCGSyntaxError("message")
VCGRuntimeError("message")
```

新增可选关键字字段：

```python
VCGError(
    message: str,
    *,
    path: str | os.PathLike[str] | None = None,
    lineno: int | None = None,
    column: int | None = None,
    snippet: str | None = None,
)
```

字段要求：

- `message`：稳定的人工可读错误消息。
- `path`：可选文件路径，内部以字符串保存。
- `lineno`：可选 1-based 行号。
- `column`：可选 1-based 列号。
- `snippet`：可选源码片段或上下文。
- `location` property：返回结构化位置字符串；没有位置时返回 `None`。
- `str(error)`：没有上下文字段时必须保持旧行为；有上下文时附加位置/片段。

### 子类

保留所有现有子类名：

- `VCGFileError`
- `VCGParseError`
- `VCGSyntaxError`
- `VCGRuntimeError`

每个子类增加 docstring，说明语义边界。

### 公开导出

新增 `__all__`，显式列出异常层级。

## 兼容性要求

- 现有 `except VCGError` 和 `except VCGFileError` 等捕获行为不变。
- 现有只传 message 的 `str(e)` 输出不变。
- 不强制调用点立即迁移到 `path=` / `lineno=`。
- 不引入新依赖。

## 验收标准

1. `src/vcg_exceptions.py` 通过 `py_compile`。
2. 新增测试覆盖：
   - 子类继承关系。
   - 旧构造形式和 `str(e)` 兼容。
   - `path` / `lineno` / `column` / `snippet` 字段保存。
   - `location` property 格式。
   - `__all__` 与公开异常类一致。
3. 运行聚焦测试：
   - `uv run pytest tests/test_vcg_exceptions.py -v`
4. 运行回归测试：
   - `uv run pytest tests/test_vcg_execution_engine.py -v`
   - `uv run pytest tests/test_vcg_file_processor.py -v`
   - `uv run pytest tests/ -v`

## 已知风险

- 如果 `__str__` 对无上下文异常改变输出，会造成大量现有测试或 CLI 文本回归。
- 如果子类构造签名不兼容，会破坏现有 `raise VCGFileError("...")` 调用点。
- `VCGSyntaxError` 当前仍主要是保留类型；是否在 Lexer/Parser 中使用，应作为后续任务单独处理。
