# TASK-06: Refactor CLI Entry

| 字段 | 值 |
|------|----|
| 负责 | vcg-python-dev -> vcg-python-tester |
| 依赖 | TASK-05 |
| 状态 | completed |
| 创建 | 2026-05-10 |

## 需求描述

根目录 `vcg.py` 是 CLI 入口，职责应限制为参数解析、日志初始化、调用 `VCGFileProcessor`、返回清晰退出码。当前存在宏参数返回类型不稳定、文件错误抛父类、`--debug` 未接入、未知错误拼写错误且缺调试栈等问题。

## 范围

本任务只修改：

- `vcg.py`
- CLI 相关测试
- TASK-06 交付/验证文档

不修改下游处理器、Parser、生成器行为。

## 接口约束

### `parse_macros_argument`

目标签名：

```python
def parse_macros_argument(macros_str: str | None) -> dict[str, str] | None:
```

行为：

- `None` 或空白字符串返回 `None`。
- `A,B` 返回 `{"A": "", "B": ""}`。
- `A=1,B=2` 返回 `{"A": "1", "B": "2"}`。
- `A,B=2` 返回 `{"A": "", "B": "2"}`。
- 空片段如 `A,,B` 忽略。

### `main`

目标签名：

```python
def main(argv: list[str] | None = None) -> int:
```

行为：

- 不直接调用 `sys.exit()`，由 `if __name__ == "__main__"` 包装。
- 成功返回 `0`，失败返回 `1`。
- 先初始化日志，再做文件存在性校验。
- 文件不存在抛/处理 `VCGFileError`，并带 `path` 上下文。
- `--debug` 在未显式传 `--log-level` 时等价于 `--log-level DEBUG`。
- 显式 `--log-level` 优先级高于 `--debug`。
- 未知异常输出 `"Unknown Error"`，不再使用 `"Unknow Error"`。
- DEBUG 日志级别下，未知异常通过 logger 输出 traceback。

## 验收标准

1. 新增 CLI 测试覆盖：
   - macros 解析统一返回 dict。
   - `main(argv)` 成功路径调用 processor 并返回 0。
   - 文件不存在返回 1，stderr 为 VCG Error。
   - `--debug` 映射 DEBUG。
   - 显式 `--log-level` 覆盖 `--debug`。
   - 未知异常返回 1，stderr 使用 `"Unknown Error"`，DEBUG 下调用 `logger.exception`。
2. 编译通过：
   - `uv run python -m py_compile vcg.py`
3. 聚焦测试通过：
   - `uv run pytest tests/test_vcg_cli.py -v`
4. 回归测试通过：
   - `uv run pytest tests/test_vcg_exceptions.py -v`
   - `uv run pytest tests/test_vcg_file_processor.py -v`
   - `uv run pytest tests/ -v`

## 风险

- 改变成功消息文本可能影响外部脚本。本任务保留 stdout 成功提示，但改为语义更清晰的 `VCG generation done: <path>`。
- `parse_macros_argument()` 返回类型从 list/dict 混合改为 dict，依赖 list 形态的外部调用需要迁移；下游 `VerilogPreprocess` 已支持 dict。
