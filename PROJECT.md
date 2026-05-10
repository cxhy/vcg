# VCG 项目决策记录 (PROJECT.md)

> 长期记忆：记录技术架构、设计细节和重要决策。
> 与 CLAUDE.md 的分工：CLAUDE.md = 项目规范（怎么做），PROJECT.md = 技术架构 + 决策历史（是什么 + 为什么）。

## 记忆系统说明

- **PROJECT.md**（本文件）：长期记忆，里程碑或重大决策后更新
- **doc/decisions/**：细节决策日志，每次会话的具体技术决策
- **归档**：里程碑完成或 doc/decisions/ 超过 10 个文件时，提炼关键结论到 PROJECT.md，原文移入 `doc/decisions/archive/YYYY-MM/`

---

## 项目架构

### 项目结构

```
src/
├── vcg.py                   # CLI 入口
├── vcg_exceptions.py        # 异常层级: VCGError → File/Parse/Syntax/Runtime
├── vcg_file_processor.py    # 主编排器: 提取 VCG 块 → 执行 → 注入结果
├── vcg_execution_engine.py  # Python 执行上下文 (Connect/Instance/WiresDef 等)
├── vcg_rule_manager.py      # 规则引擎: 通配符匹配、LIFO 优先级
├── vcg_instance_manager.py  # 模块例化代码生成
├── vcg_wires_manager.py     # wire 声明生成 (lazy/greedy 模式)
├── VerilogLexer.py          # PLY 词法分析
├── VerilogParser.py         # PLY 语法分析 (支持 V95 + V2001)
├── VerilogAst.py            # AST 数据结构 + Builder + ExpressionCalculator
├── VerilogPreprocess.py     # 预处理器 (`ifdef/`ifndef/宏展开)
├── vcg_logger.py            # 单例日志 (ContextVar 文件上下文)
└── verilog.bnf              # 语法规范文件
```

### 模块依赖关系

```
vcg.py
 └─ vcg_file_processor.py
     └─ vcg_execution_engine.py
         ├─ vcg_rule_manager.py      (规则匹配)
         ├─ vcg_instance_manager.py  (例化生成)
         │   └─ VerilogParser
         └─ vcg_wires_manager.py     (线网生成)
             └─ VerilogParser

VerilogParser.py
 ├─ VerilogLexer.py
 ├─ VerilogAst.py        (PortDeclaration → PortInfo, ParameterInfo)
 └─ VerilogPreprocess.py
```

### 核心数据流

```
Verilog 文件 → VCGFileProcessor 提取 //VCG_BEGIN...//VCG_END 块
  → VCGExecutionEngine 执行嵌入的 Python 代码
    → Connect/ConnectParam 注册规则到 VCGRuleManager
    → Instance() 调用 VerilogParser 解析目标模块, 用规则解析连接, 生成例化代码
    → WiresDef() 类似, 生成 wire 声明
  → 结果注入 //VCG_GEN_BEGIN_X...//VCG_GEN_END_X 区域
  → 写回文件
```

### Parser 管线

当前 Verilog 前端保留 `VerilogLexer` / `VerilogParser` / `VerilogAst` /
`VerilogPreprocess` 命名，因为这些模块长期上允许扩展为更完整的
Verilog/SystemVerilog 解析器。但当前实现的稳定目标不是完整编译器，而是
目标 module 的 module-level declaration 子集解析。

- **VerilogPreprocess**: 在整文件范围处理条件编译和宏上下文，定位目标
  module，并向 Parser 提供该 module 的声明相关文本。预处理阶段不能先裁掉
  module 前上下文再处理条件编译。
- **VerilogLexer**: PLY 词法分析。当前服务于 module-level declaration
  子集；声明区域内的词法错误必须进入结构化错误通道。
- **VerilogParser**: PLY yacc。当前支持 Verilog-1995 body 声明、
  Verilog-2001 ANSI header、header/body 中的 `parameter` / `localparam`、
  端口声明，以及表达式子集。非声明型 body item 可以被跳过，但不能被误建模
  为 AST。
- **VerilogASTBuilder**: Builder 模式积累 `PortDeclaration` /
  `ParameterInfo`，`build()` 时通过 `PortFactory` 转为 `PortInfo`。
- **ExpressionCalculator**: 用 sympy 计算参数化宽度表达式，无法安全化简时
  回退为字符串，不能静默损失 Verilog 源码语义。
- **verilog.bnf**: 当前支持子集的语法规范文件。它必须和
  `VerilogParser.py` 同步维护，不能作为历史草稿长期漂移。

当前解析范围的核心边界：

- 必须解析目标 module 的 header 参数、ANSI/V95 端口、body 内
  `parameter` / `localparam`、body 内端口声明。
- 必须为未来 SystemVerilog 的 data type、interface port、modport、
  packed/unpacked dimensions 预留数据模型扩展点。
- 暂不实现的 body 语句（如 `assign`、instance、always、generate）可以在
  不影响声明提取时跳过；如果出现在声明区域或破坏声明边界，必须失败。
- 发现 lexer/parser/preprocess 错误时不能返回看似成功的 AST。

### 规则系统

- LIFO 优先级: 后定义的规则优先匹配
- 通配符 `*` 转为正则捕获组, `$1`/`$2` 引用捕获内容
- 支持函数表达式: `${upper(*)}`, `${replace(*,old,new)}`
- 方向过滤: 规则可限定只匹配 input/output/inout

### 测试结构

每个 src 模块都有对应 `tests/test_*.py`, 总计约 6400 行测试代码:

| 测试文件 | 覆盖模块 |
|----------|----------|
| test_VerilogLexer.py | 词法 token 识别 |
| test_VerilogParser.py | 语法解析 (V95/V2001) |
| test_VerilogAst.py | AST 构建、Port/Parameter 管理 |
| test_VerilogPreprocess.py | 宏处理、条件编译 |
| test_vcg_rule_manager.py | 规则匹配、优先级、函数表达式 |
| test_vcg_instance_manager.py | 例化生成、端口/参数连接 |
| test_vcg_wires_manager.py | wire 生成、lazy/greedy 模式 |

测试夹具: `tests/test_top.v`, `tests/sub_module.v`

---

## 分支状态

### develop_refactor_parser (当前)

本分支对 Parser 管线进行了重大重构:
- VerilogAst.py 从 ~1150 行精简到 ~400 行 (引入 PortDeclaration/PortInfo 分离)
- VerilogParser.py 从 ~975 行精简到 ~540 行
- 删除了旧的 vcg_connect_manager.py, 功能合并到 rule_manager
- 新增 ~6400 行测试代码
- Bug 已修复: 532 tests all passed (详见 doc/bugfix_progress.md)

---

## 决策记录

### 2026-04-11: Parser 重构分支 bug 修复

**背景**: `develop_refactor_parser` 分支对 Parser 管线做了重大重构（VerilogAst 从 ~1150 行精简到 ~400 行），但存在 8 个测试失败。

**决策 1: 异常处理链必须保留异常类型语义**
- `except Exception` 不能吞掉 `ValueError`、`FileNotFoundError` 等有明确语义的异常
- 正确做法：在通用 `except Exception` 前按类型分别 `raise`
- 理由：调用方依赖异常类型做分支判断，包装后语义丢失

**决策 2: Mock 策略 — 直接替换实例属性，不 patch 类**
- 如果对象在 `__init__` 中实例化（如 `self.parser = VerilogParser(...)`），后续 `with patch('...VerilogParser')` 无效
- `Mock(name='xxx')` 中 `name` 是 Mock 保留字段，不会成为属性
- 理由：4 个测试因此"假通过"（TST-1~4），浪费了大量排查时间

**决策 3: sympy 作为必需依赖**
- ExpressionCalculator 依赖 sympy 计算参数化宽度表达式，必须在 pyproject.toml 中声明
- 理由：未声明导致 5 个测试模块整体 import 失败

### 2026-04-11: Agent 协作体系建立

**背景**: 项目进入持续迭代阶段，需要结构化的 agent 协作流程。

**决策 4: 4 agent 分工 + 文档驱动协作**
- architect（Opus）: 架构设计、任务拆解、进度把控
- python-dev（Sonnet）: 代码实现
- python-tester（Sonnet）: 测试验证
- verilog-checker（Sonnet）: 生成代码 + AST 双重检查
- 理由：避免单 agent 上下文爆炸，文档沟通保证可追溯

**决策 5: agent 间通过 doc/ 文档沟通，用户确认后推进**
- 不自动调度，每步由用户确认
- 理由：用户对 Verilog 领域知识最终负责，自动调度可能放大错误

### 2026-04-25: VerilogAst.py 模块级重构（依 review 11）

**背景**: Linus 风格评审 `doc/review/11_VerilogAst.md` 列出 12 条 issue（P0×2、P1×3、P2×7），包含 1 个真 bug、1 处封装违反、3 处死代码。

**决策 6: frozen dataclass 三件套 + Builder 改用 dataclasses.replace**
- PortDeclaration / PortInfo / ParameterInfo 均 `frozen=True`
- VerilogASTBuilder.add_port 内部改 `dataclasses.replace`，对外签名与行为完全不变
- `array_dims: List[str]` 保留为 list（维持对外签名），docstring 标注"请勿 in-place mutate"
- 理由：落实 CLAUDE.md 不可变性铁律；frozen 只冻顶层字段重绑定，`array_dims` 约定式不可变作为下次迭代的收敛余地

**决策 7: 抽取 _OrderedRegistry[T] 私有基类替代 Manager 模板重复**
- ParameterManager / PortManager 继承 `_OrderedRegistry[_T]`（文件内私有，下划线起头不导出）
- 保留 `self._parameters = self._items` 等下划线别名，防御性兼容
- 理由：消除两份一模一样的 "dict + order list + add + get_all" 模板，但对外签名与类名保持稳定（硬约束）

**决策 8: ParameterManager.add_parameter_info 新增为 public API**
- 与 PortManager.add_port_info 对称
- Builder.build() 通过此 public API 替代对 `_parameters` / `_parameter_order` 的私有戳穿
- 理由：review #2 的封装违反根治；"只加不改" 扩展不破坏兼容

**决策 9: _calculate_vector_width 改 sympy 化简 + narrow 字符串 fallback**
- 删除旧的 `endswith('-1')` 硬编码切片（修掉 `[WIDTH - :0]` 与 `[FOO:None]` 两个隐形 bug）
- 让 sympy 处理 `(msb)-(lsb)+1` 的主路径
- 仅当 sympy 解析失败（sympy 保留名 `N`/`O`/`S`/`Q` 等）且 `lsb=='0'` 且 `msb` 精确匹配 `\s*(.+?)\s*-\s*1\s*` 时，回退到纯字符串化简返回捕获组
- 理由：Linus 原建议"让 sympy 全盘化简"未考虑 sympy 内置符号冲突（`sympify('N-1')` 抛 `TypeError`），narrow fallback 保证 `N-1:0 → N` 这类 Verilog 常见写法不回归

**决策 10: 保留 PortDeclaration 与 PortFactory（搁置 review #4）**
- review 原建议合并 PortDeclaration/PortInfo、删 PortFactory
- 因 PortFactory 在硬约束保留清单中（类名 + `to_info` 签名必须稳定），合并会导致 `to_info` 退化为 identity
- 取舍：保留 PortDeclaration+PortFactory 现状，只做 frozen。次佳但与硬约束一致
- 其他因硬约束搁置的 review 条目：#10 PortDirection 强制启用（会破坏下游字符串协议）、#11 ARRAY_2D/3D 分类重设计（属 AST 层级重设计）

**决策 11: LOC 偏差可接受**
- 任务单预估 330-350 行，实际 452 行（+58）
- 成因：强制 docstring（frozen 语义 / update_port 别名 / narrow fallback 注释）+ 抽基类 + T-A-fix
- 理由：代码质量与文档自解释性优先于 LOC 预算；docstring 全部为任务单显式要求

**决策 12: 死异常类删除**
- PortNotFoundError / ParameterNotFoundError 全仓 0 raise / 0 catch，删除
- VerilogASTError 保留（VerilogParser.py:205 在 catch）
- 理由：review #12 的纯清理，不在硬约束保留清单

**交付物**（7 commit + 3 doc）：
- `829f61c..2157c2d`: T-A/B/C/D/E/F-I + T-A-fix
- `110cae1`: tester 新增 72 项测试
- doc/task_01 / delivery_01 / verification_01 / check_01 / feedback_01 全链

**验收结果**：
- pytest: 599 passed, 0 failed（527 原有 + 72 新增）
- examples/dma_system.v byte-for-byte 等价（md5 `bdbf98cf...`, cmp exit 0）
- 下游 VerilogParser / InstanceManager / WiresManager / RuleManager 0 改动
- 对外 API 22/22 签名语义等价

### 2026-05-10: Verilog 前端当前解析边界与长期命名策略

**背景**: 新一轮 Linus 风格 review 指出 `VerilogLexer.py` /
`VerilogParser.py` / `VerilogPreprocess.py` 存在错误边界、预处理顺序和声明
建模问题。讨论确认这些问题部分来自早期设计取舍：VCG 当前只需要从目标
module 提取参数和端口，因此有意忽略大量完整 Verilog 语法。但这种简化没有
被清楚表达在架构和 BNF 中，导致代码一边跳过语法，一边又像完整 parser 一样
返回 AST。

**决策 13: 保留 `Verilog*` 命名，不改成 interface-only 命名**
- `VerilogLexer` / `VerilogParser` / `VerilogAst` / `VerilogPreprocess`
  名字继续保留。
- 理由：项目未来可能实现更完整的 Verilog/SystemVerilog parser。当前不通过
  改名收窄长期方向，而是在文档和实现契约中标明“当前支持子集”。

**决策 14: 当前稳定目标是 module-level declaration 子集**
- 当前必须解析：
  - 目标 module 的 header parameter / localparam。
  - Verilog-2001 ANSI header 端口声明。
  - Verilog-1995 body 端口声明。
  - module body 内的 `parameter` / `localparam`。
  - 宽度表达式、参数默认值、端口 range 所需的表达式子集。
- 当前可以跳过但不建 AST：
  - `assign`
  - module instance
  - `always`
  - `generate`
  - 其他非声明型 body item
- 理由：body 内参数会影响端口宽度和下游生成，不能简单丢弃；但非声明型
  body item 不是 VCG 当前输出所需数据，不应逼迫当前 parser 支持完整语义。

**决策 15: 预处理必须先保留整文件上下文，再选择目标 module**
- `VerilogPreprocess` 长期方向是：整文件条件编译/宏上下文处理 →
  目标 module 定位 → 声明相关文本抽取。
- 不接受“先裁掉 module 前文本，再做条件编译”的数据流。
- 理由：module 前的 ``define``、include guard、条件编译指令属于解析目标
  module 的必要上下文，提前丢弃会污染 AST。

**决策 16: 声明建模要使用 declaration group 思路，并为 SV 预留字段**
- 端口和参数声明不能把每个逗号分隔项都当作完整独立声明。例如
  `input [7:0] a, b` 和 `parameter A = 1, B = 2` 必须共享声明上下文。
- 数据模型应支持“声明属性 + declarator list”的结构，字段至少要考虑：
  direction、net/data type、packed dimensions、unpacked dimensions、
  interface type、modport、signedness、default value。
- 理由：这同时修复当前 ANSI 多端口继承问题，并为 SystemVerilog 的
  `logic signed [W-1:0] a, b`、`axi_if.master m_axi` 等语法预留扩展点。

**决策 17: `src/verilog.bnf` 是当前支持子集规范，不是草稿**
- `verilog.bnf` 必须清理重复和过期规则，并与 `VerilogParser.py` 同步。
- 对暂不支持但未来计划支持的 Verilog/SystemVerilog 语法，应在 BNF 中标记为
  future/unsupported，而不是混在当前 grammar 里。
- 理由：BNF 是后续架构、实现和测试任务的共同依据。如果它和代码漂移，
  review 和任务拆解会反复争论同一个基础边界。

**决策 18: 简化实现必须 fail loud，不能 silent corruption**
- 当前子集内无法正确解析时，必须抛出 `VCGParseError` 或更具体的 VCG 异常。
- 如果 lexer/parser/preprocess 已记录错误，不能返回看似成功的 AST。
- 理由：VCG 的下游会基于 AST 生成 Verilog。错误输入生成“格式正确但语义错误”
  的 instance/wire，比早失败更危险。

**决策 19: include/import 文件发现必须通过显式搜索根**
- Verilog ``include`` 是预处理期文本包含；SystemVerilog `import` 是语法和名字解析
  metadata。二者不能共用语义，也不能把 `import` 当成 include 展开。
- 未来支持 include 时，调用方必须显式传入 `include_roots`，由 include resolver
  搜索文件、处理相对路径、循环 include、最大深度和 source location 映射。
- 未来支持 SystemVerilog package import 时，调用方必须显式传入 `package_roots`
  或 package index，由 import/package resolver 按 package 名查找定义。
- 不允许从 cwd、工程根目录或环境状态隐式猜搜索路径；多个候选命中必须报
  ambiguity error。
- 理由：VCG 会被嵌入不同工程和工作目录中。隐式搜索路径会让同一输入在不同目录下
  解析出不同 AST，比暂时不支持 include/import 更危险。

**对后续任务的约束**:
- Parser 管线重构任务必须先引用本决策，再定义具体 task 范围。
- 不以“完整 Verilog parser”为近期验收目标。
- 不删除 body parameter/localparam 支持。
- 不为短期修复重命名 `Verilog*` 模块。
- 不为 include/import 支持引入隐式文件搜索路径。
- 修改 parser grammar 时必须同步检查并更新 `src/verilog.bnf`。
