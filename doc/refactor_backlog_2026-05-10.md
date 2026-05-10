# 2026-05-10 重构剩余清单

| 字段 | 值 |
|------|----|
| 来源 | 继续重构前的架构盘点 |
| 依据 | `doc/review/00_INDEX.md`、`doc/decisions/*`、当前 `src/` 实现 |
| 状态 | backlog |

## 已完成或基本完成

这些内容不应重复开新任务，除非后续验证发现回归。

| 模块 | 状态 | 依据 |
|------|------|------|
| package/CLI import 路径 | 已完成关键修复 | `3c1c70c refactor: package src/ and move CLI entry to project root` |
| `VerilogLexer.py` 字符串转义 bug | 已完成关键修复 | `18a3c94 fix: correct STRING_LITERAL escape order in lexer` |
| `VerilogLexer.py` 死代码清理 | 已做一轮 | `a074837 refactor: clean up VerilogLexer.py dead code and normalize error handling` |
| `vcg_instance_manager.py` 端口计数恒 0 | 已完成关键修复 | `2f9ecd5 fix: count port connections directly instead of grepping generated text` |
| `VerilogParser.py` silent failure | 已完成一轮结构性重构 | `doc/decisions/2026-04-25_parser_refactor.md` |
| `VerilogAst.py` | TASK-01 全链完成 | `doc/task_01_refactor_verilogast.md`、`doc/check_01_refactor_verilogast.md` |
| `vcg_logger.py` | 已完成手工重构 | `doc/delivery_manual_vcg_logger_refactor.md` |
| `vcg_rule_manager.py` | 已完成结构性重构 | `doc/delivery_manual_vcg_rule_manager_refactor.md` |

## P0：下一批最应该重构

### 1. `src/vcg_file_processor.py`

当前仍是最高优先级。核心问题：

- `process_file()` 仍使用 `os.chdir()` 修改全进程 CWD。
- `VCGBlock` 是可变对象，`generated_content` 后填，违反不可变约束。
- `_extract_vcg_blocks()` 不显式处理 nested/orphan/unterminated `VCG_BEGIN`/`VCG_END`。
- `_inject_generated_content_for_blocks()` 仍依赖 `current_block_id` 与已有 `VCG_GEN_BEGIN_<id>` 的隐式同步。
- `except Exception` 包装成 `VCGFileError`，错误阶段和原异常类型丢失。
- 仍使用手动 `set_file_context()`/`clear_file_context()`，应改用 `vcg_logger.file_context()`。
- 源文件尾部还有 `test()` 与 `__main__` 硬编码调试入口。

建议拆成一个独立 TASK：冻结 `VCGBlock`，新增 `ExecutedBlock`，按行号区间重写注入逻辑，彻底移除 `os.chdir()`。

### 2. `src/VerilogPreprocess.py`

基本未重构。核心问题：

- 名为 preprocess，但不处理 ``define`` / ``undef`` / 宏体展开。
- 条件编译状态仍是 dict 栈，`condition` 等字段语义冗余。
- 仍用正则和行扫描处理 Verilog 结构，注释、属性、跨行声明、字符串里的 `;` 都有风险。
- `preprocess_file()` / `preprocess_string()` 仍用 `RuntimeError` 和宽泛 `except Exception`。
- 文件尾部仍有 `__main__` 调试代码。

建议先决定方向：缩小职责为 `ModulePortExtractor`，还是补成真正预处理器。不要继续在当前正则实现上小修。

### 3. `src/vcg_execution_engine.py`

核心架构可保留，但还没清理到位：

- `execute()` 仍用 `except Exception` 把所有 VCG 子类包装成 `VCGRuntimeError`，缺 `from e`。
- `OrderedOutputManager` 仍有 `add_text_output()` / `add_instance_output()` / `add_wires_output()` 三个重复接口。
- 仍有 6 个 `_create_*_func()` 闭包工厂，样板代码偏多。
- `expand_path()` 不检查路径是否存在，错误会延迟到下游。
- `__builtins__` 全开放，至少要在接口文档中明确“VCG 脚本是可信 Python 代码”。

建议作为中等规模 cleanup TASK，目标是删样板、保留 DSL 行为不变。

## P1：部分修过，但还没有完成结构性重构

### 5. 根目录 `vcg.py`

package import 已修，但 CLI 本体仍保留 review 里的多数问题：

- `parse_macros_argument()` 仍可能返回 `None` / `list` / `dict` 三种形态。
- 文件不存在仍抛 `VCGError` 父类，而不是 `VCGFileError`。
- `setup_vcg_logging()` 在文件存在性校验之后才执行。
- `except Exception` 仍打印 `"Unknow Error"`，无 traceback，退出码不区分未知错误。
- `--debug` 参数仍未接入实际行为。
- 成功和错误输出仍主要走 `print`。

建议做一个小 TASK：CLI 错误处理 + macros 数据契约统一。

### 6. `src/vcg_instance_manager.py`

真 bug 已修，剩余是数据结构和渲染清理：

- `_generate_port_connections()` 仍返回两个 dict：`connections` 与 `port_infos`，隐含 key 同步契约。
- 应引入 `PortConnection(frozen=True)`，渲染层不再检查 `if port_name in port_infos`。
- `_ALIGN = 18` 仍是 magic number，注释列用 `_ALIGN * 2`。
- `_render_parameter_section()` 与 `_render_port_section()` 仍重复处理“最后一项不加逗号”。
- `set_alignment()` / `get_alignment()` 是否保留需要 grep 外部调用后决定。

建议与 `vcg_wires_manager.py` 分开做，避免输出格式回归面太大。

### 7. `src/vcg_wires_manager.py`

异常包装已有改善，但宽度模型仍没重构：

- `width` 仍是 int / str / range-string / expression / multi-dim string 混合语义。
- `_format_wire_width()` 仍靠 `isdigit()`、`startswith("[")`、operator sniffing 分类。
- `_is_multi_dimensional()` 仍靠 `']['` 判断，空格形式会漏判。
- `_format_wire_declaration()` 混合宽度选择、对齐和最终声明拼接。
- `VerilogParser` 跨多次调用复用是否安全仍需审计。

建议先做低风险止血：`_is_multi_dimensional()` 改正则、拆声明格式化；ADT 化宽度应单独评估，因为会影响 AST/RuleManager 契约。

### 8. `src/VerilogLexer.py`

已清理一轮，但 review 中仍有未落地项：

- 是否真正 raise `VCGSyntaxError` 需要核对并补测试。
- `ID` 规则是否仍把 `` ` `` / `$` 当普通标识符，需决定是否拆 `MACRO_REF` / `SYSTEM_TASK`。
- 关键字表是否仍存在“两份真相”需要继续收敛。
- `build()` / `input()` / `token()` 的 lazy build 与类型注解还可清理。

建议先不要和 Preprocess 同时改宏相关 token，否则边界会互相牵连。

## P2：横切清理项

### 9. `src/vcg_exceptions.py`

异常层级仍只是 5 个空类：

- 没有 `message` / `path` / `lineno` 等结构化字段。
- `VCGSyntaxError` 当前主要是 import，实际 raise 使用不足。
- 缺 `__all__` 和类 docstring。
- 仍缺测试约束“不要直接 raise VCGError 父类”。

建议在 CLI/FileProcessor/Preprocess 重构前先做最小增强：保持构造兼容，新增可选结构化字段。

### 10. 全仓异常处理统一

当前仍可搜到多处 `except Exception`。并非全部都必须删除，但需要逐处分类：

- 应直接透传：`VCGFileError` / `VCGParseError` / `VCGSyntaxError` / `VCGRuntimeError`。
- 包装未知异常时必须 `raise ... from e`。
- 不应把运行时错误伪装成 parse/file error。

建议作为每个模块重构的验收标准，而不是单独大扫除。

### 11. 类型注解、未用 import、源文件调试入口

剩余模块里还有 `typing.List/Dict/Optional/Tuple` 旧风格、未用 import、源文件尾部 `__main__` 调试入口等问题。优先级低于行为重构，但每个模块改到时应顺手清掉。

## 建议执行顺序

1. `vcg_file_processor.py`：先拆掉 `os.chdir()` 和注入状态机。
2. `VerilogPreprocess.py`：先做方向决策，再写 TASK；不要盲目补丁。
3. `vcg_execution_engine.py`：清异常、输出管理器和 DSL 闭包工厂。
4. `vcg.py`：CLI 数据契约和错误处理。
5. `vcg_instance_manager.py` / `vcg_wires_manager.py`：分别收敛数据结构和渲染。
6. `VerilogLexer.py`：宏/system-task token 与 syntax error 策略。
7. `vcg_exceptions.py`：结构化字段和异常纪律测试。
