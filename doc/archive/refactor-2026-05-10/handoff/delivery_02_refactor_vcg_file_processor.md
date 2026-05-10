# DELIVERY: TASK-02

## 修改文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `src/vcg_file_processor.py` | 修改 | 移除 `os.chdir()`、手动 `set_file_context()` / `clear_file_context()`；改用 `file_context()`。 |
| `src/vcg_file_processor.py` | 修改 | 将 `VCGBlock` 改为 frozen dataclass，并新增 frozen `ExecutedBlock` 承载执行输出。 |
| `src/vcg_file_processor.py` | 修改 | 重写 VCG/生成块提取状态机，显式校验 nested/orphan/unterminated/malformed VCG 与 VCG_GEN 标记。 |
| `src/vcg_file_processor.py` | 修改 | 注入逻辑改为基于记录的行号区间从后往前替换或插入生成块，不再依赖扫描时的隐式 block id 同步。 |
| `src/vcg_file_processor.py` | 修改 | `_preprocess_vcg_code()` 保留空白行；删除文件尾部调试入口；清理 import 与类型注解。 |
| `src/vcg_file_processor.py` | 修改 | 在 file processor 内为每个执行引擎实例绑定按被处理文件目录解析相对路径的 `expand_path()`，避免修改 `src/vcg_execution_engine.py`。 |
| `src/vcg_file_processor.py` | 修改 | 代码质量补丁：引入 `_BlockScanState`，将 `_extract_vcg_blocks()` 的 VCG/生成块扫描分支拆成私有 helper，降低单函数长度。 |
| `doc/delivery_02_refactor_vcg_file_processor.md` | 新增 | 记录 dev 阶段交付内容、验证点、命令结果与风险。 |

## 需要验证的测试点

1. 正常路径：包含多个合法 `//VCG_BEGIN` / `//VCG_END` 块的文件应按 0 起始 block id 提取并生成。
2. 已有生成块：存在 `//VCG_GEN_BEGIN_<id>` / `//VCG_GEN_END_<id>` 时，重复运行应只替换该区间内容。
3. 新生成块：没有生成块时，应在对应 `//VCG_END` 后插入新的 begin/end 标记和生成内容。
4. 错序生成块：已有生成块顺序与 VCG 块顺序不一致时，应按显式 id 和行号区间更新，不应错配输出。
5. 标记异常：nested/orphan/unterminated/malformed VCG 或 VCG_GEN 标记应抛 `VCGParseError`。
6. 文件异常：文件不存在、读写失败应抛 `VCGFileError`，并保留原始异常 cause。
7. 执行异常：执行引擎抛出的 `VCGRuntimeError` 应直接透传，不伪装为读文件错误。
8. 相对路径 DSL：`Instance()` / `WiresDef()` 中的相对路径应继续按被处理 VCG 文件所在目录解析。
9. 空白行：VCG Python 块中的空白行应保留，避免改变 Python 行号和块结构。

## 对下游模块的影响

- `VCGFileProcessor(macros=None)` 和 `process_file(file_path: Path) -> None` 对外调用方式保持不变。
- `VCGBlock` 不再包含可变 `generated_content` 字段；执行结果通过 `ExecutedBlock` 表达。下游如果直接依赖 `VCGBlock.generated_content`，需要改为读取执行结果结构。
- 未修改 `src/vcg_execution_engine.py`。相对路径兼容通过 `VCGFileProcessor` 在每个 execution engine 实例上绑定局部 `expand_path()` 实现。
- 未新增依赖。

## 运行过的命令与结果

| 命令 | 结果 |
|------|------|
| `uv run python -m py_compile src\vcg_file_processor.py` | 未通过环境启动阶段：`uv` 初始化 `C:\Users\cxhy1\AppData\Local\uv\cache` 失败，`os error 5` 拒绝访问。 |
| `uv run python -m py_compile src\vcg_file_processor.py`（请求提升权限重试） | 用户中断，未完成。 |
| `uv run python -m py_compile src\vcg_file_processor.py` | 通过。 |

## 偏差与风险

- 按用户要求，本阶段未修改 tests，未运行聚焦 pytest 或全量回归。
- 相对路径兼容采用实例级 monkey patch `expand_path()`，避免修改 execution engine；需要 tester 覆盖 `Instance()` / `WiresDef()` 相对路径场景确认行为。
- 当前实现只在允许范围内修改 `src/vcg_file_processor.py` 和本交付文档，未写 `doc/feedback_02_refactor_vcg_file_processor.md`。
