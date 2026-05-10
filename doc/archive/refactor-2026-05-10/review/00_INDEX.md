# Linus 式代码评审 — 总索引

> 评审日期: 2026-04-21
> 分支: `develop_refactor_parser`
> 评审范围: `src/` 下 12 个 Python 源文件
> 评审方式: 每文件由独立 agent 完成，主控仅汇总
> 评审风格: Linus Torvalds — 直接、技术导向、零废话

---

## 评分分布

| 级别 | 数量 | 文件 |
|------|------|------|
| 🟢 好品味 | 0 | — |
| 🟡 凑合 | 6 | vcg.py, vcg_exceptions.py, vcg_logger.py, vcg_execution_engine.py, vcg_wires_manager.py, VerilogAst.py |
| 🔴 垃圾 | 6 | vcg_file_processor.py, vcg_rule_manager.py, vcg_instance_manager.py, VerilogLexer.py, VerilogParser.py, VerilogPreprocess.py |

**一句话: 12 个文件零个达到"好品味"，半数被定级为"垃圾"。Parser 管线和核心管理器全部沦陷。**

---

## 报告清单

| # | 文件 | 评分 | 最致命问题（一句话） |
|---|------|------|-----------------------|
| 01 | [vcg.py](01_vcg.md) | 🟡 | `except Exception` 把所有未知错误压成 `Unknow Error`（连拼写都错），无 traceback |
| 02 | [vcg_exceptions.py](02_vcg_exceptions.md) | 🟡 | `VCGSyntaxError` 是死代码（零处 raise）；异常无结构化字段（path/lineno） |
| 03 | [vcg_logger.py](03_vcg_logger.md) | 🟡 | `ContextVar.set()` 不保存 token 无法 reset；setup 不真幂等 |
| 04 | [vcg_file_processor.py](04_vcg_file_processor.md) | 🔴 | `os.chdir` 全局污染 + 双计数器靠"祈祷对齐"对不上 |
| 05 | [vcg_execution_engine.py](05_vcg_execution_engine.md) | 🟡 | `except Exception` 把 4 种 VCG 异常全包成 `VCGRuntimeError`，无 `from e` |
| 06 | [vcg_rule_manager.py](06_vcg_rule_manager.md) | 🔴 | `_execute_function_call` 用 `eval` 沙箱可逃逸 RCE；405 行单类 + 40% 日志噪音 |
| 07 | [vcg_instance_manager.py](07_vcg_instance_manager.md) | 🔴 | 用 `'.(' in line` 解析自己生成的字符串数端口，计数恒为 0 |
| 08 | [vcg_wires_manager.py](08_vcg_wires_manager.md) | 🟡 | `width` 字段缺 ADT，`_format_wire_width` 5 分支阶梯 |
| 09 | [VerilogLexer.py](09_VerilogLexer.md) | 🔴 | 425 行里 117 行是 main/test 死代码；`STRING_LITERAL` 转义顺序错 |
| 10 | [VerilogParser.py](10_VerilogParser.md) | 🔴 | `parse_*` 静默吞异常返 None；build 失败时构造空 AST 顶替 — silent corruption |
| 11 | [VerilogAst.py](11_VerilogAst.md) | 🟡 | `endswith("-1")` 字符串 hack 对带空格表达式吐出非法 Verilog |
| 12 | [VerilogPreprocess.py](12_VerilogPreprocess.md) | 🔴 | 用正则伪装预处理器；不处理 `\`define`/`\`undef`/宏展开 |

---

## 跨文件共性问题（Linus: "好代码没有特殊情况"）

### P0 共性 1: `except Exception` 吞类型语义 (7 个文件犯同一个错)

`vcg.py` / `vcg_file_processor.py` / `vcg_execution_engine.py` / `vcg_instance_manager.py` / `vcg_wires_manager.py` / `vcg_rule_manager.py` / `VerilogParser.py` 全部出现：

```python
except Exception as e:
    raise VCGXxxError(f"... {e}")        # 类型擦除 + 无 from e
```

PROJECT.md 决策 1 明确写了 "按类型分别 raise"。**这条规则在嘴上落地了，代码里没有**。
修复成本: 每文件 5-10 行 except 阶梯，1-2 小时全部清理。

### P0 共性 2: `import` 风格内战，CLI 直接崩溃

主控独立验证（执行 `uv run python src/vcg.py --help`）:
```
ImportError: attempted relative import with no known parent package
  vcg_rule_manager.py:26: from .VerilogAst import PortInfo, PortType
```

| 文件 | 风格 |
|------|------|
| `vcg.py`, `vcg_file_processor.py`, `vcg_execution_engine.py` | 绝对 (`from vcg_logger import ...`) |
| `vcg_rule_manager.py`, `vcg_instance_manager.py`, `vcg_wires_manager.py`, `VerilogParser.py` | 相对 (`from .vcg_logger import ...`) |
| `src/__init__.py` | **不存在** |

测试用 `from src.X` 跑得通，让人误以为代码 OK。**生产路径完全跑不起来**。
**修复二选一**: 全改绝对 + 调整 sys.path 入口；或全改相对 + 加 `src/__init__.py` + 改入口为 `python -m src.vcg`。

### P1 共性 3: 状态机用裸变量

`_inject_generated_content_for_blocks` (file_processor) / `extract_module_ports_section` (preprocess) / `process_conditional_compilation` (preprocess) 都是同一个病：3-5 个布尔/列表变量在 while 循环里互相覆盖。Linus 会说："数据结构错了。"

### P1 共性 4: CLAUDE.md 不可变性规范无人遵守

- `VerilogAst.py`: 三个 dataclass 全部裸 `@dataclass`，没有 `frozen=True`
- `vcg_file_processor.py`: `VCGBlock` 创建后填 `generated_content`
- `vcg_rule_manager.py`: 规则用 dict 而非 frozen dataclass

CLAUDE.md 一开头就写"创建新对象而非修改现有对象 (frozen dataclass)"。零执行。

### P1 共性 5: 死代码 + 测试代码混入源文件

- `VerilogLexer.py`: 117 行 main/interactive/test 在源文件中；约 30 行注释死代码
- `VerilogPreprocess.py`: 文件末尾大段 main 测试代码
- `vcg_file_processor.py`: 末尾有 test() 函数和 main 入口
- `vcg_logger.py`: 单例 Manager 是 Java 病，30+ 行可砍

### P2 共性 6: 全局副作用三宗罪

- `eval` (rule_manager) — RCE 风险，沙箱可逃逸
- `exec` (execution_engine) — 设计本质，但缺 `from e`
- `chdir` (file_processor) — 多线程必炸，最该死

---

## Linus 式总结

**好的部分**:
- 模块依赖图清晰 (vcg.py → file_processor → execution_engine → 三个 manager + parser)
- 异常层级 (VCGError 树) 设计 OK，可惜没人照着用
- AST/Builder 模式 + sympy 表达式求值是合理选择
- 测试覆盖广 (~6400 行 / 532 通过)

**烂的部分**:
- **导入风格混乱让 CLI 死掉**。这一条单独够否决整个分支。
- **过度 logger.debug**。`vcg_rule_manager.py` 一个方法 5 行逻辑配 8 行 log，文件 40% 是日志格式化。读代码像在读日志说明书。
- **状态机用裸变量**。3 处大型状态机全部踩同一个坑。
- **eval / exec / chdir** 三大全局副作用都用上了。
- **重复模板**。InstanceManager ↔ WiresManager 几乎对称；ParameterManager ↔ PortManager 是同一份模板；3 个 resolve_* / 3 个 add_*_output / 6 个 _create_*_func 都是 copy-paste。

**真 bug 清单（按修复优先级）**:

1. **[阻塞]** import 风格 → 让 CLI 跑通
2. **[Day-1]** `vcg_instance_manager.py:64-67` 端口数恒为 0
3. **[Day-1]** `VerilogAst.py:170-171` `endswith("-1")` 对带空格表达式吐非法 Verilog
4. **[Day-1]** `VerilogParser.py:p_module_declaration` build 失败构造空 AST 顶替 — silent corruption
5. **[Day-1]** `VerilogLexer.py:240-243` STRING_LITERAL 转义顺序错
6. **[本周]** 7 个文件的 `except Exception` 阶梯全部按 PROJECT.md 决策 1 重写
7. **[本周]** `_inject_generated_content_for_blocks` 重写成"按行号切片"
8. **[本月]** 拆 `vcg_rule_manager.py`，规则改 frozen dataclass，砍掉 40% 日志
9. **[本月]** `VerilogPreprocess.py` 大幅缩小职责或重写为 PLY token 流

**给项目作者的话**:

文档里写的规范（PROJECT.md 决策 1、CLAUDE.md 不可变性、CLAUDE.md "无 except Exception 吞掉"）已经很好了。问题是代码不照做。

> "Talk is cheap. Show me the code." — 但这次代码先 import 起来再说。

---

## 元信息

- 评审耗时: ~3 分钟主控编排 + 12 个 agent 并发执行
- 单 agent 平均 token 用量: ~38k
- 主控 context 隔离: 完成 — 主控未读任何源文件，所有细节分析均在 agent 内完成
