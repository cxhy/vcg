# TASK-02: Refactor `src/vcg_file_processor.py`

| 字段 | 值 |
|------|----|
| 负责 | vcg-python-dev -> vcg-python-tester -> vcg-verilog-checker |
| 依赖 | TASK-01 已完成 |
| 状态 | done |
| 创建 | 2026-05-10 |

## 需求描述

重构 `src/vcg_file_processor.py`，消除文件处理核心路径里的全局副作用、可变块对象、隐式生成块同步和宽泛异常包装，同时保持现有 CLI 与 VCG DSL 行为兼容。

本任务的直接依据：

- `doc/refactor_backlog_2026-05-10.md` P0 #1
- `doc/review/04_vcg_file_processor.md`
- `CLAUDE.md` 不可变对象、异常层级、日志规范

## 范围

### 必须完成

1. `VCGBlock` 改为 `@dataclass(frozen=True)`，不再包含后填的 `generated_content`。
2. 新增 `ExecutedBlock` 或等价不可变结构，表达 `VCGBlock` 与执行输出的对应关系。
3. `_extract_vcg_blocks()` 显式校验：
   - nested `//VCG_BEGIN`
   - orphan `//VCG_END`
   - unterminated `//VCG_BEGIN`
   - malformed / orphan / unterminated `//VCG_GEN_BEGIN_<id>` / `//VCG_GEN_END_<id>`
4. `_inject_generated_content_for_blocks()` 改为基于行号区间替换或插入，不再依赖 `current_block_id` 与扫描到的生成块 id 隐式同步。
5. `process_file()` 不再使用手动 `set_file_context()` / `clear_file_context()`，改用 `vcg_logger.file_context()`。
6. `process_file()` 的异常处理按阶段区分：
   - 文件读写问题：`VCGFileError`
   - VCG 标记结构问题：`VCGParseError` 直接透传
   - 执行错误：保留 `VCGRuntimeError` 语义，不包装成普通读文件错误
   - 包装未知异常时必须 `raise ... from e`
7. 删除文件尾部 `test()` 和 `if __name__ == "__main__"` 调试入口。
8. `_preprocess_vcg_code()` 保留 VCG 块中的空白行，避免改变 Python 块行号和语义。
9. 清理 import、拼写错误、类型注解。

### 兼容性约束

1. `VCGFileProcessor(macros=None)` 与 `process_file(file_path: Path) -> None` 对外调用方式保持兼容。
2. 现有 VCG 块编号从 0 开始，生成标记仍使用：
   - `//VCG_GEN_BEGIN_<id>`
   - `//VCG_GEN_END_<id>`
3. 对已有合法文件，重复运行 `process_file()` 应更新已有生成块内容，而不是重复插入生成块。
4. 对没有生成块的合法文件，应在对应 `//VCG_END` 后插入新的生成块。
5. 本任务默认只修改 `src/vcg_file_processor.py`、相关测试文件和交接文档。不要改 `src/vcg_execution_engine.py`。如果发现不改 execution engine 无法保持相对路径 DSL 行为，写 `doc/feedback_02_refactor_vcg_file_processor.md` 说明原因。

## 接口约束

建议结构：

```python
@dataclass(frozen=True)
class VCGBlock:
    code: str
    start_line: int
    end_line: int
    block_id: int
    gen_start_line: int | None = None
    gen_end_line: int | None = None


@dataclass(frozen=True)
class ExecutedBlock:
    block: VCGBlock
    generated_content: str
```

允许实现采用等价命名，但必须满足：

- VCG 块对象不可变。
- 执行输出不回写到 `VCGBlock`。
- 注入逻辑只依赖明确记录的行号和 block id。

## 验收标准

### 静态/结构

- `src/vcg_file_processor.py` 中不再出现 `os.chdir`。
- 不再 import 或调用 `set_file_context` / `clear_file_context`。
- 文件尾部无硬编码调试入口。
- `VCGBlock` 为 frozen dataclass。
- 不存在无区分的一锅端 `except Exception` 把所有错误包装成 `"Read file Error"`。

### 行为

1. 读取合法文件，能提取多个 VCG 块并保留 block id 顺序。
2. 已存在 `VCG_GEN_BEGIN_0` / `VCG_GEN_END_0` 时，重复运行只替换生成块内部内容。
3. 没有生成块时，运行后在 `VCG_END` 后插入对应生成块。
4. 多个 VCG 块中，生成内容不会因已有生成块顺序或 id 错乱而错配。
5. nested/orphan/unterminated VCG 标记抛 `VCGParseError`。
6. 文件不存在、读写失败抛 `VCGFileError`。
7. 执行引擎抛出的 `VCGRuntimeError` 不被伪装成读文件错误。
8. `tests/test_top.v` 或等价临时 fixture 的端到端生成结果保持合法 Verilog。

### 验证命令

聚焦验证优先：

```bash
uv run pytest tests/test_vcg_file_processor.py -v
```

然后运行相关回归：

```bash
uv run pytest tests/ -v
```

如全量测试受既有问题阻塞，tester 必须在验证报告中列出阻塞项和已通过的聚焦测试。

## 分阶段交付物

### vcg-python-dev

- 修改 `src/vcg_file_processor.py`
- 写 `doc/delivery_02_refactor_vcg_file_processor.md`
- 不修改 `tests/`

### vcg-python-tester

- 新增或更新 `tests/test_vcg_file_processor.py`
- 运行聚焦和回归测试
- 写 `doc/verification_02_refactor_vcg_file_processor.md`
- 如果发现产品代码问题，写 `doc/feedback_02_refactor_vcg_file_processor.md`

### vcg-verilog-checker

- 对涉及 VCG block 注入的 Verilog 样例做只读检查
- 写 `doc/check_02_refactor_vcg_file_processor.md`
- 不修改 `src/`、`tests/`、`examples/`

## 已知风险

- 当前 `VCGExecutionEngine.expand_path()` 以进程 cwd 解析相对路径；移除 `os.chdir()` 可能暴露相对路径兼容性问题。本任务不直接改 engine，开发阶段需要通过最小局部方案或反馈文档处理。
- 生成块行号替换需要注意从后往前应用区间，避免前面替换改变后续行号。
- `splitlines()` 与 `split('\n')` 的尾随换行行为不同，测试必须覆盖文件尾部换行不被意外破坏。
