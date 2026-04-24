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

- **VerilogPreprocess**: 宏展开 + 去除 module 前内容
- **VerilogLexer**: PLY 词法分析, 支持 Verilog 数字格式 (含下划线分隔)
- **VerilogParser**: PLY yacc, 同时支持 Verilog-1995 (body 声明) 和 Verilog-2001 (ANSI header)
- **VerilogASTBuilder**: Builder 模式积累 PortDeclaration, `build()` 时通过 PortFactory 转为 PortInfo
- **ExpressionCalculator**: 用 sympy 计算参数化宽度表达式, 失败时回退为字符串

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
