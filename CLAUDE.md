# VCG (Verilog Code Generator)

> 在 Verilog 文件中嵌入 Python 脚本，自动生成模块例化、信号连接和线网声明。
> 技术架构和设计细节见 PROJECT.md。

## 一、技术栈

- **Python >=3.14** (pyproject.toml)
- **PLY >=3.11** — 词法/语法分析
- **sympy** — 表达式求值
- **pytest >=9.0.3** — 测试框架
- **uv** — 包管理 (严禁 pip install)

## 二、开发命令

```bash
# 运行全部测试
uv run pytest tests/ -v

# 运行单个测试模块
uv run pytest tests/test_VerilogParser.py -v

# 运行 VCG 处理文件
uv run python vcg.py <verilog_file> --log-level DEBUG

# CLI 参数
#   --debug          调试模式
#   --macros M1=v1,M2   传入宏定义
#   --log-level {DEBUG|INFO|WARNING|ERROR|CRITICAL}
#   --log-file FILE  日志输出到文件
#   --quiet          安静模式 (仅错误)
```

## 三、编码规范

### 不可变性
- 创建新对象而非修改现有对象 (frozen dataclass)
- Builder 创建新 AST, 不修改已有对象

### 文件与函数
- 文件 <800 行, 函数 <50 行
- 多个小文件优于一个大文件

### 异常处理
- 使用 VCGError 层级: VCGFileError / VCGParseError / VCGSyntaxError / VCGRuntimeError
- 不用通用 `except Exception` 吞掉有语义的异常, 按类型分别处理后 re-raise

### 日志
- `get_vcg_logger('ModuleName')`, 层级式命名 (VCG.ModuleName)

### 命名
- 模块文件: `vcg_` 前缀 snake_case 或 `Verilog` 前缀 PascalCase
- 类: PascalCase, 函数/变量: snake_case, 常量/参数: UPPER_CASE
- Verilog 实例名: `u_<name>`, 信号: `snake_case`, 输出寄存器: `_r` 后缀

### 测试
- 测试文件: `test_<模块名>.py`, 放 tests/ 目录
- Mock: 直接替换实例属性, 不 patch 已在 `__init__` 中创建的对象
- `Mock(name=...)` 中 name 是保留字段, 需先创建 Mock 再赋值 `.name`
- 使用 `Mock(spec=RealClass)` 确保接口一致

## 四、Agent 协作体系

项目配置了 4 个 agent skill (`.claude/skills/`), 通过 doc/ 目录文档沟通:

| Agent | 触发词 | 职责 | 模型 |
|-------|--------|------|------|
| vcg-architect | 架构师/architect/设计方案/规划 | 需求拆解、接口设计、进度把控、风险上报 | Opus 4.6 |
| vcg-python-dev | python开发/编写代码/实现功能 | 按任务单编码、写交付文档 | Sonnet 4.6 |
| vcg-python-tester | 验证/测试/编写测试 | 编写测试、运行验证、输出验证报告 | Sonnet 4.6 |
| vcg-verilog-checker | verilog检查/检查AST/lint | 生成代码语法检查 + AST 正确性检查 | Sonnet 4.6 |

**工作流**: architect 出方案(doc/) → 用户确认 → dev 编码 → tester 验证 → checker 检查 → 用户确认

**文档协议**:
- 任务单: `doc/task_<编号>_<简述>.md`
- 交付文档: `doc/delivery_<编号>_<简述>.md`
- 验证报告: `doc/verification_<编号>_<简述>.md`
- 检查报告: `doc/check_<编号>_<简述>.md`
- 问题反馈: `doc/feedback_<编号>_<简述>.md`

**异常升级**: tester→dev 修复, checker→architect 评估

## 五、记忆系统

| 层级 | 文件 | 内容 | 更新时机 |
|------|------|------|----------|
| 长期 | `PROJECT.md` | 技术决策、架构设计、模块依赖 | 里程碑完成、重大决策后 |
| 细节 | `doc/decisions/YYYY-MM-DD_<简述>.md` | 每次会话的具体技术决策 | 每次会话结束 |

- CLAUDE.md（本文件）= 项目规范（怎么做）
- PROJECT.md = 技术架构 + 决策历史（是什么 + 为什么）
- 归档: doc/decisions/ 超过 10 个文件或里程碑完成时, 提炼关键结论到 PROJECT.md, 原文移入 `doc/decisions/archive/YYYY-MM/`
