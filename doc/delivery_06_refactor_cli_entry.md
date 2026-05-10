# DELIVERY: TASK-06

## 修改文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `vcg.py` | 修改 | 重构 CLI 参数解析、日志级别解析、错误处理和返回码 |
| `tests/test_vcg_cli.py` | 新增 | 覆盖 macros 解析、成功路径、错误路径和 debug 行为 |
| `doc/task_06_refactor_cli_entry.md` | 新增 | 定义 CLI 入口重构边界和验收标准 |

## 实现说明

- `parse_macros_argument()` 现在返回 `dict[str, str] | None`，不再在 list/dict 之间切换。
- `main()` 改为 `main(argv: list[str] | None = None) -> int`，便于测试和外部调用。
- `if __name__ == "__main__"` 负责 `sys.exit(main())`。
- 日志初始化先于文件存在性校验。
- `--debug` 在未显式传 `--log-level` 时映射为 `DEBUG`。
- 显式 `--log-level` 优先级高于 `--debug`。
- 文件不存在使用 `VCGFileError("File missing", path=file_path)`。
- 未知异常文案修正为 `"Unknown Error"`。
- DEBUG 模式下未知异常通过 `logger.exception("Unknown CLI error")` 保留 traceback。

## 需要验证的测试点

1. `parse_macros_argument(None)`、空字符串、空白字符串返回 `None`。
2. `WIDTH,DEPTH` 返回 `{"WIDTH": "", "DEPTH": ""}`。
3. `WIDTH=8,DEPTH=16` 返回稳定 dict。
4. 混合宏 `SIM,WIDTH=8,,DEPTH` 忽略空片段并返回 dict。
5. 成功路径调用 `VCGFileProcessor(macros=...)` 和 `process_file()`，返回 `0`。
6. 文件缺失路径返回 `1`，不调用 processor。
7. `--debug` 和 `--log-level` 优先级正确。
8. 未知异常返回 `1`，stderr 使用 `"Unknown Error"`。
9. DEBUG 下未知异常调用 `logger.exception()`。

## 对下游模块的影响

- `VCGFileProcessor` 现在只会从 CLI 收到 `dict[str, str] | None` 的 macros。下游 `VerilogPreprocess` 已支持 dict 输入。
- CLI 成功消息从 `VCG generate Done: ...` 调整为 `VCG generation done: ...`。
- 入口仍保持 `uv run python vcg.py <file>` 运行方式。

## 开发阶段验证

- `uv run pytest tests/test_vcg_cli.py -v`: 10 passed
- `uv run python -m py_compile vcg.py`
