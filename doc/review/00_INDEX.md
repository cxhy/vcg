# Linus 风格代码评审汇总

> 日期: 2026-05-10
> 范围: `src/` 下 12 个 Python 文件
> 执行方式: 每个文件由独立 agent 并行评审；主会话只汇总，不改源码。
> 说明: 本轮评审基于当前 `refactor/code-cleanup` 分支，上一轮重构文档已归档到 `doc/archive/refactor-2026-05-10/`。

## 总结

整体已经比上一轮 review 好很多：`eval`、全局 `chdir`、实例端口计数等早期硬伤已经清掉。但 Parser 管线仍然是核心风险区，问题从“代码显然烂”变成了更危险的“能返回 AST，但 AST 可能是脏的”。

最该优先修的不是再拆类，而是把输入契约收紧：lexer/preprocess/parser 一旦发现不能正确理解源码，就必须失败，而不是继续生成看似合法的 Verilog。

## 评分分布

| 级别 | 数量 | 文件 |
|------|------|------|
| 🟢 好品味 | 0 | - |
| 🟡 凑合 | 9 | `__init__.py`, `vcg_exceptions.py`, `vcg_execution_engine.py`, `vcg_file_processor.py`, `vcg_instance_manager.py`, `vcg_logger.py`, `vcg_rule_manager.py`, `vcg_wires_manager.py`, `VerilogAst.py` |
| 🔴 红区 / 垃圾边缘 | 3 | `VerilogLexer.py`, `VerilogParser.py`, `VerilogPreprocess.py` |

## 报告清单

| # | 文件 | 报告 | 评分 | 最严重问题 |
|---|------|------|------|------------|
| 00 | `src/__init__.py` | `00___init__.md` | 🟡 | 空文件本身正确；真正问题是项目把 `src` 当运行时包名。 |
| 01 | `src/vcg_exceptions.py` | `01_vcg_exceptions.md` | 🟡 | 结构化异常字段基本没被生产 raise 点使用；`VCGSyntaxError` 仍缺语义来源。 |
| 02 | `src/vcg_execution_engine.py` | `02_vcg_execution_engine.md` | 🟡 | `print(..., end='')` 输出模型会生成错误文本；DSL 语法错误被归 runtime。 |
| 03 | `src/vcg_file_processor.py` | `03_vcg_file_processor.md` | 🟡 | `expand_path()` 被 monkey patch，破坏 engine 原始路径校验契约。 |
| 04 | `src/vcg_instance_manager.py` | `04_vcg_instance_manager.md` | 🟡 | `module_name` 不校验真实 AST 模块，可能静默生成错误实例。 |
| 05 | `src/vcg_logger.py` | `05_vcg_logger.md` | 🟡 | 文件 handler 标称 DEBUG，但父 logger 先过滤，文件 DEBUG 全量记录是假的。 |
| 06 | `src/vcg_rule_manager.py` | `06_vcg_rule_manager.md` | 🟡 | `*` 同时承担通配符/占位符/乘法语义，注释和字面量处理会生成错误 Verilog。 |
| 07 | `src/vcg_wires_manager.py` | `07_vcg_wires_manager.md` | 🟡 | `module_name` 是假参数；greedy 可能覆盖“不生成 wire”的下游决策。 |
| 08 | `src/VerilogAst.py` | `08_VerilogAst.md` | 🟡 | `ExpressionCalculator` 的系统函数占位符和大整数处理可能静默算错宽度。 |
| 09 | `src/VerilogLexer.py` | `09_VerilogLexer.md` | 🔴 | 词法错误只 log 并跳过，关键字大小写折叠破坏 Verilog 语义。 |
| 10 | `src/VerilogParser.py` | `10_VerilogParser.md` | 🔴 | `parse_errors` 非空仍可能返回 AST，Parser 成功边界是坏的。 |
| 11 | `src/VerilogPreprocess.py` | `11_VerilogPreprocess.md` | 🔴 | 先裁 module 再预处理，module 前宏/include guard/条件上下文会被丢掉。 |

## P0 修复顺序

1. **Parser 成功边界收紧**
   `VerilogParser.parse_string()` / `parse_file()` 只要 lexer/parser 错误非空，就必须抛 `VCGParseError`，不能返回 AST。

2. **Lexer 错误进入统一错误通道**
   `VerilogLexer.t_error()` 不能只 log 后跳过；非法字符、坏数字字面量必须让 Parser 或调用方失败。

3. **Preprocess 数据流重排**
   先处理整文件条件编译和宏上下文，再按目标 module 抽取声明区；不要先裁掉 module 前上下文。

4. **目标 module 契约生效**
   `InstanceManager` / `WiresManager` 当前把 `module_name` 当日志文本。需要 Parser/AST 暴露真实 module name，并在 manager 层校验。

5. **RuleManager 字符串替换语义收紧**
   先修 `1 /* comment */` 字面量扩展、`WIDTH*2` 被误替换、注释占位符碰撞这些会生成错误 Verilog 的问题。

## P1 修复顺序

1. `vcg_execution_engine.py`: 修 `print(..., end='')` 输出模型；Python DSL `SyntaxError` 应归 `VCGParseError` 或更明确的语法错误。
2. `vcg_file_processor.py`: 用 engine 显式 `base_dir` 取代 monkey patch `expand_path()`。
3. `vcg_instance_manager.py`: 过滤 `localparam`，避免当成可 override 参数。
4. `vcg_wires_manager.py`: 从端口生成 wire 时优先保留 `range_string`，不要用 `width` 重建并丢失方向/数组语义。
5. `VerilogAst.py`: 修系统函数占位符碰撞和大整数 float 精度丢失。
6. `vcg_logger.py`: 明确 logger/handler level 契约；如果文件日志承诺 DEBUG，就不要被父 logger 截断。
7. `vcg_exceptions.py`: 迁移 raise 点到 `path/lineno/column/snippet` 结构化字段，而不是继续把上下文塞进字符串。

## 不建议立即做的事

- 不要先做大规模 class 拆分。现在最大风险不是类太长，而是错误输入没有 fail loud。
- 不要给 `__init__.py` 加 re-export 或初始化副作用。空文件是当前包导入的正确标记。
- 不要为了性能先缓存 parser table。错误契约不干净时，缓存只是让错误更快传播。
- 不要继续在字符串上做更多特殊分支。Rule/Wire/Port 语义要结构化，否则补一个洞会挖两个新洞。

## 建议下一批 TASK

1. `TASK-09`: Lexer + Parser 错误契约收紧
   范围包括 `VerilogLexer.t_error()`、数字字面量规则、`VerilogParser.parse_errors` 成功边界、lexer 错误接入。

2. `TASK-10`: Preprocess 目标 module 与宏上下文重排
   范围包括整文件条件编译扫描、按 `module_name` 抽取目标 module、多 module 文件行为。

3. `TASK-11`: Manager module_name 契约
   范围包括 AST 暴露 module name、`InstanceManager` / `WiresManager` 校验目标模块，避免静默用错端口集合。

4. `TASK-12`: Rule/Wire 生成语义修复
   范围包括 `*` 替换 token 化、注释安全占位、wire range 数据源修正。
