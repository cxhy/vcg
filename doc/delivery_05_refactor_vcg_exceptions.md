# DELIVERY: TASK-05

## 修改文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `src/vcg_exceptions.py` | 修改 | 将空异常类重构为兼容的结构化异常层级 |
| `doc/task_05_refactor_vcg_exceptions.md` | 新增 | 定义异常模块重构边界和验收标准 |

## 实现说明

- `VCGError` 保留 `VCGError("message")` 构造兼容。
- 新增可选字段：`path`、`lineno`、`column`、`snippet`。
- 新增 `location` property，用于稳定的位置格式化。
- `__str__()` 在没有上下文字段时保持旧输出；有上下文时追加位置和片段。
- 保留全部子类名称，并为子类补充语义 docstring。
- 新增 `__all__`，显式声明模块公开异常类型。

## 需要验证的测试点

1. 旧构造形式不变：`str(VCGFileError("missing")) == "missing"`。
2. 子类仍然是 `VCGError` 的子类，可被 `except VCGError` 捕获。
3. `path` 支持 `str` 和 `PathLike`，内部保存为字符串。
4. `lineno` / `column` / `snippet` 出现在结构化字段和字符串输出中。
5. 只有列号、没有路径/行号时，`location` 仍稳定可读。
6. `__all__` 与公开异常类一致。

## 对下游模块的影响

- 不要求下游调用点立即修改构造方式。
- 后续模块可逐步从 `raise VCGFileError(f"... {path}")` 迁移到 `raise VCGFileError("...", path=path)`。
- `vcg.py` 直接抛 `VCGError` 的问题未在本任务内修改，应留到 CLI 错误处理任务。

## 开发阶段验证

- `uv run python -m py_compile src\vcg_exceptions.py`
