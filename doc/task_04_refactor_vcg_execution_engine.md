# TASK-04: Refactor `src/vcg_execution_engine.py`

| 字段 | 值 |
|------|----|
| 负责 | vcg-python-dev -> vcg-python-tester -> vcg-verilog-checker |
| 依赖 | TASK-02 已完成，TASK-03 已完成 |
| 状态 | completed |
| 创建 | 2026-05-10 |

## 需求描述

重构 `src/vcg_execution_engine.py`，保留当前 VCG Python DSL 行为，同时收敛执行边界的异常语义、输出收集接口、路径解析和 DSL 函数绑定方式。

本任务依据：

- `doc/refactor_backlog_2026-05-10.md` P0 #3
- `doc/review/05_vcg_execution_engine.md`
- `doc/task_02_refactor_vcg_file_processor.md` 中相对路径 DSL 兼容要求
- `CLAUDE.md` 异常层级、函数长度、类型注解和日志规范

## 范围

### 必须完成

1. `execute()` 不再把 VCG 自家异常统一包装成新的 `VCGRuntimeError`：
   - `VCGFileError`
   - `VCGParseError`
   - `VCGSyntaxError`
   - `VCGRuntimeError`
   以上异常必须直接透传。
2. `execute()` 包装未知 Python 异常时必须使用 `raise VCGRuntimeError(...) from e`，保留 cause chain。
3. `OrderedOutputManager` 合并 `add_text_output()` / `add_instance_output()` / `add_wires_output()` 为单一输出追加接口，例如：

   ```python
   class OrderedOutputManager:
       def add(self, text: str) -> None: ...
       def get_final_output(self) -> str: ...
       def clear(self) -> None: ...
   ```

   输出顺序和最终拼接语义必须保持兼容。
4. `print` wrapper 负责把 `print(*args, sep, end)` 规范化成输出段，再交给 `OrderedOutputManager.add()`；manager 不应知道 `print` 的特殊情况。
5. 删除 6 个 `_create_*_func()` 闭包工厂，改成普通 bound method 或直接绑定已有 method：
   - `print` -> engine method
   - `Instance` -> engine method
   - `WiresDef` -> engine method
   - `Connect` -> `rule_manager.add_signal_rule`
   - `ConnectParam` -> `rule_manager.add_param_rule`
   - `WiresRule` -> `rule_manager.add_wire_rule`
6. `expand_path()` 对空字符串或不存在路径 fail-fast：
   - 空路径抛 `VCGFileError`
   - 不存在路径抛 `VCGFileError`
   - 保留环境变量和 `~` 展开行为
   - 保留 `VCGFileProcessor._bind_file_relative_paths()` monkey patch 的兼容性；不要破坏相对路径按被处理文件目录解析的现有行为
7. 在 `VCGExecutionEngine` 文档或代码注释中明确：VCG 块中的 Python 代码以完整 Python builtins 执行，输入必须被视为可信脚本；本任务不做 sandbox。
8. 清理未使用 import，类型注解使用 Python 3.14 内建泛型风格（如 `list[str]`、`dict[str, object]`）。
9. 单文件和函数长度保持规范：文件 <800 行，函数 <50 行。

### 非目标

本任务不改变 DSL 语义：

- 不禁用 `exec`。
- 不收紧 `__builtins__`。
- 不改 `Connect` / `ConnectParam` / `WiresRule` / `Instance` / `WiresDef` 的参数契约。
- 不修改 `src/vcg_file_processor.py` 的相对路径 monkey patch 方案，除非 tester 证明必须联动；如必须联动，先写 feedback。
- 不重构 `InstanceManager` / `WiresManager` 的渲染逻辑。
- 不改变生成 Verilog 文本格式，除非现有格式由明显 bug 导致，且必须通过 checker 复核。

## 接口约束

必须保持以下公开 API 可调用：

```python
OrderedOutputManager()
OrderedOutputManager.get_final_output() -> str
OrderedOutputManager.clear() -> None

VCGExecutionEngine(macros=None)
VCGExecutionEngine.expand_path(path_str: str) -> str
VCGExecutionEngine.execute(python_code: str) -> str
```

允许删除或改名以下私有 helper：

```python
_create_instance_func()
_create_wires_def_func()
_create_connect_func()
_create_connect_param_func()
_create_wires_rule_func()
_create_custom_print_func()
```

允许新增私有 helper / 私有方法，例如：

```python
def _print(self, *args, sep=" ", end="\n", file=None, flush=False) -> None: ...
def _instance(self, file_path: str, module_name: str, instance_name: str) -> None: ...
def _wires_def(self, file_path: str, module_name: str, port_type: str | None = None, pattern: str = "greedy") -> None: ...
def _add_generated_output(self, output: str) -> None: ...
```

如果为了兼容旧测试需要保留 `add_text_output()` / `add_instance_output()` / `add_wires_output()`，只能作为薄兼容 wrapper 调用 `add()`，并在 delivery 文档解释原因；优先删除重复接口。

## 兼容性要求

1. `execute("print('x')")` 仍返回 `"x"`。
2. `print()` 空行行为保持：只打印换行时最终输出中保留空行位置。
3. 多次 `execute()` 调用前仍清空 `rule_manager` 和 `output_manager`。
4. `Instance(...)` 生成后仍自动 reset rules。
5. `WiresDef(...)` 生成后仍自动 reset rules。
6. `Connect(...)` / `ConnectParam(...)` / `WiresRule(...)` 仍只登记规则，不直接输出。
7. 用户脚本中显式 `print(..., file=sys.stderr)` 仍绕过 VCG 输出收集器，交给 Python 原生 `print`。
8. 不存在文件在 `Instance("missing.v", ...)` 或 `WiresDef("missing.v", ...)` 路径展开阶段应更早抛 `VCGFileError`。
9. TASK-02 已验证的相对路径行为必须继续通过：从不同 cwd 处理 VCG 文件时，`Instance("sub.v", ...)` / `WiresDef("sub.v", ...)` 仍按被处理文件所在目录解析。

## 验收标准

### 静态/结构

- `src/vcg_execution_engine.py` 中不再出现 `_create_instance_func`、`_create_wires_def_func`、`_create_connect_func`、`_create_connect_param_func`、`_create_wires_rule_func`、`_create_custom_print_func`。
- `OrderedOutputManager` 不再包含三份重复的 `add_*_output` 主逻辑。
- `execute()` 中 VCG 自家异常透传，未知异常包装使用 `raise ... from e`。
- 无未使用的 `typing.List` / `Dict` / `Tuple` import。
- 文件 <800 行，函数 <50 行。

### 行为

1. `print` 输出、空行输出、多个输出段顺序保持。
2. `Connect` / `ConnectParam` / `WiresRule` rule registration 能被 `Instance` / `WiresDef` 消费。
3. `Instance` / `WiresDef` 输出加入 `OrderedOutputManager` 的顺序和原行为一致。
4. VCG 自家异常不被二次包装。
5. 未知脚本异常包装为 `VCGRuntimeError` 且 `__cause__` 指向原异常。
6. `expand_path()` 对缺失文件抛 `VCGFileError`。
7. `tests/test_vcg_file_processor.py` 中相对路径 DSL 回归继续通过。

## 验证命令

聚焦验证：

```bash
uv run pytest tests/test_vcg_file_processor.py -v
```

建议新增 `tests/test_vcg_execution_engine.py` 后运行：

```bash
uv run pytest tests/test_vcg_execution_engine.py -v
```

回归验证：

```bash
uv run pytest tests/ -v
```

## 分阶段交付物

### vcg-python-dev

- 修改 `src/vcg_execution_engine.py`
- 写 `doc/delivery_04_refactor_vcg_execution_engine.md`
- 不修改 `tests/`

### vcg-python-tester

- 新增或更新 `tests/test_vcg_execution_engine.py`
- 必须跑 `tests/test_vcg_file_processor.py` 验证 TASK-02 相对路径兼容
- 必须跑全量 `tests/ -v`
- 写 `doc/verification_04_refactor_vcg_execution_engine.md`
- 如果发现产品代码问题，写 `doc/feedback_04_refactor_vcg_execution_engine.md`

### vcg-verilog-checker

- 只读检查 DSL 生成输出是否仍是合法 Verilog 片段：
  - `Instance(...)` 生成例化
  - `WiresDef(...)` 生成 wire 声明
  - `print(...)` 混合文本输出顺序
- 写 `doc/check_04_refactor_vcg_execution_engine.md`

## 已知风险

- `VCGFileProcessor` 当前通过实例级 monkey patch 改写 `expand_path()`，本任务中的 fail-fast 不能破坏该机制。
- `__builtins__` 全开是明确保留的设计边界；不要在本任务中做 sandbox，否则会破坏现有 VCG Python DSL 能力。
- `OrderedOutputManager.add()` 的空字符串/空行语义容易引发生成文本格式回归，tester 必须覆盖。
- 如果删除 `add_*_output` 导致旧测试或外部私有调用失败，应优先评估是否保留薄兼容 wrapper，而不是恢复重复实现。
