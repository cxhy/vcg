# DELIVERY: TASK-04

## 修改文件清单
| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `src/vcg_execution_engine.py` | 修改 | 收敛执行异常边界、输出收集接口、DSL 函数绑定和默认路径解析。 |
| `doc/delivery_04_refactor_vcg_execution_engine.md` | 新增 | 记录 dev 阶段交付内容、验证点、命令结果与风险。 |
| `doc/task_04_refactor_vcg_execution_engine.md` | 修改 | 状态更新为 `in_progress`。 |

## 实现摘要
1. `execute()` 现在直接透传 `VCGFileError` / `VCGParseError` / `VCGSyntaxError` / `VCGRuntimeError`。
2. 未知 Python 异常仍包装为 `VCGRuntimeError`，并使用 `raise ... from e` 保留原始 cause。
3. `OrderedOutputManager` 合并为单一 `add()` 接口；生成输出和 print 输出都通过该接口进入有序列表。
4. 删除 `_create_*_func()` 闭包工厂；执行上下文直接绑定 bound method 或 `rule_manager` 方法。
5. `Instance` / `WiresDef` 改为 engine 私有方法 `_instance()` / `_wires_def()`，仍在生成后 reset rules。
6. `_print()` 负责 `print(*args, sep, end)` 的输出规范化，`file is not None` 仍交给原生 `print`，不进入 VCG 输出收集。
7. `expand_path()` 保留环境变量和 `~` 展开；默认路径解析对空路径和不存在路径抛 `VCGFileError`。
8. 在 `VCGExecutionEngine` docstring 中明确 VCG Python DSL 以完整 builtins 执行，本任务不提供 sandbox。
9. 清理未使用 `typing` import，类型注解改为内建泛型风格。

## 需要验证的测试点
1. 正常路径：`execute("print('x')")` 输出仍为 `x`。
2. 输出顺序：多次 `print()`、空行、生成输出混合时顺序保持。
3. DSL 规则：`Connect` / `ConnectParam` / `WiresRule` 只登记规则，`Instance` / `WiresDef` 消费规则后输出并 reset。
4. 异常路径：VCG 自家异常不被二次包装；未知 Python 异常包装为 `VCGRuntimeError` 且 `__cause__` 保留原异常。
5. 路径路径：默认 `expand_path()` 对空路径和缺失文件抛 `VCGFileError`。
6. TASK-02 回归：`tests/test_vcg_file_processor.py` 的相对路径 DSL 用例继续通过。

## 已运行验证
| 命令 | 结果 |
|------|------|
| `uv run python -m py_compile src\vcg_execution_engine.py` | 通过 |
| `uv run pytest tests/test_vcg_file_processor.py -v` | 17 passed |
| inline smoke: `uv run python -` | 通过：覆盖 print、空行、缺失路径 `VCGFileError`、未知异常 cause、`VCGFileError` 透传 |
| 函数长度 AST 检查 | 文件 150 行；最大函数 18 行 |

## 对下游模块的影响
- `VCGFileProcessor` 仍可通过实例级 monkey patch 覆盖 `expand_path()`；TASK-02 的相对路径测试已通过。
- `InstanceManager` / `WiresManager` 调用方式不变。
- `OrderedOutputManager` 的 `add_text_output()` / `add_instance_output()` / `add_wires_output()` 已删除；仓库内无直接调用。若外部私有调用这些方法，需迁移到 `add()`。
- `Connect` / `ConnectParam` / `WiresRule` 在执行上下文中直接绑定 `rule_manager` 方法，参数契约保持不变。

## 偏差和风险
- 未实现 sandbox，符合 TASK-04 非目标；VCG 块仍是可信 Python 脚本。
- 默认 `VCGExecutionEngine.expand_path()` 已 fail-fast，但 `VCGFileProcessor` 的实例级相对路径 monkey patch 当前仍由 file processor 负责；本任务未扩大范围修改 `src/vcg_file_processor.py`。
- `_print()` 的空白行规范化保持旧行为，但 tester 需要补正式单元测试锁定该行为。
