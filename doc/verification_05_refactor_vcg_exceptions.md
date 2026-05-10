# VERIFICATION: TASK-05

## 测试结果

| 命令 | 结果 |
|------|------|
| `uv run python -m py_compile src\vcg_exceptions.py` | PASS |
| `uv run pytest tests/test_vcg_exceptions.py -v` | PASS, 9 passed |
| `uv run pytest tests/test_vcg_execution_engine.py -v` | PASS, 16 passed |
| `uv run pytest tests/test_vcg_file_processor.py -v` | PASS, 17 passed |
| `uv run pytest tests/ -v` | PASS, 662 passed |

## 覆盖场景

| 测试用例 | 类别 | 结果 |
|----------|------|------|
| `test_plain_message_str_remains_unchanged` | 兼容性 | PASS |
| `test_subclasses_are_caught_by_base_class` | 继承关系 | PASS |
| `test_pathlike_lineno_column_and_snippet_are_preserved` | 结构化上下文 | PASS |
| `test_path_without_line_formats_location` | 边界条件 | PASS |
| `test_line_without_path_uses_unknown_location` | 边界条件 | PASS |
| `test_column_without_path_or_line_uses_placeholder_line` | 边界条件 | PASS |
| `test_path_argument_accepts_pathlike` | 类型兼容 | PASS |
| `test_all_exports_match_exception_hierarchy` | 公开接口 | PASS |
| `test_all_exported_values_are_error_classes` | 公开接口 | PASS |

## 发现的问题

首轮聚焦测试收集失败：

- 现象：`ModuleNotFoundError: No module named 'src'`
- 根因：新测试没有沿用仓库现有测试文件的 `sys.path` 初始化模式。
- 修复：在 `tests/test_vcg_exceptions.py` 中加入与其他测试一致的 project root 插入逻辑。

未发现产品代码问题。

## 剩余风险

- `vcg.py` 仍有直接 `raise VCGError(...)`，这不是本任务范围，应在 CLI 错误处理任务中修复为具体子类。
- `VCGSyntaxError` 仍是保留异常类型，Lexer/Parser 是否使用它需要后续任务决策。
