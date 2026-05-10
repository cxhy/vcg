# DELIVERY: vcg_logger.py refactor

| 字段 | 值 |
|------|----|
| 来源 | 用户直接要求执行 `vcg_logger.py` 重构 |
| 负责 | vcg-python-dev |
| 状态 | delivered |
| 日期 | 2026-05-10 |

## 修改文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `src/vcg_logger.py` | 修改 | 删除 `VCGLoggerManager` 单例壳子，改为模块级 logger/handler；新增 `file_context()`；修正 handler close；日志文件默认追加写入 |
| `tests/test_vcg_logger.py` | 新增 | 覆盖 context token 恢复、旧 `set/clear` API 兼容、重复 setup 关闭旧 handler、日志文件追加 |

## 需要验证的测试点

1. `file_context("x.v")` 退出后恢复进入前的 `ContextVar` 状态，嵌套上下文也能恢复。
2. 旧 API `set_file_context()` / `clear_file_context()` 仍可用，并按 token 恢复上一层上下文。
3. 重复调用 `setup_vcg_logging()` 时，旧 `FileHandler` 被显式关闭。
4. `setup_vcg_logging(log_file=...)` 默认追加写入，不覆盖已有日志内容。
5. 现有 `get_vcg_logger("Module")` 调用仍返回 `VCG.Module` logger。

## 对下游模块的影响

- 保留原有公开 API：`get_vcg_logger`、`setup_vcg_logging`、`set_file_context`、`clear_file_context`。
- 新增 `file_context()`，后续可用于重构 `vcg_file_processor.py` 的手动 set/clear 配对。
- `setup_vcg_logging()` 仍通过 `**kwargs` 对外暴露；新增可选内部参数 `file_mode`，默认 `'a'`。
- 日志文件行为从覆盖改为追加，这是刻意修复 review 中指出的日志现场丢失问题。
