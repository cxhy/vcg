# DELIVERY: TASK-01 重构 src/VerilogAst.py

| 字段 | 值 |
|------|----|
| 依据任务单 | doc/task_01_refactor_verilogast.md |
| 负责 | vcg-python-dev |
| 状态 | delivered → 交 vcg-python-tester |
| 完成日期 | 2026-04-25 |
| Commit 序列 | `829f61c` → `da4407f` → `820a707` → `432cd01` → `5778b59` → `0244305` → `2157c2d` (7 commits on `refactor/code-cleanup`) |

---

## 1. 修改文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `src/VerilogAst.py` | 修改 | 394 → 452 行，9 个子任务 + 1 个 feedback 修复 |
| `doc/feedback_01_sympy_reserved_names.md` | 新增 | T-A 触发的 sympy 保留名回归反馈 |
| `doc/delivery_01_refactor_verilogast.md` | 新增 | 本文档 |

**未修改**：
- `src/VerilogParser.py / vcg_instance_manager.py / vcg_wires_manager.py / vcg_rule_manager.py`（下游零改动硬约束）
- `tests/`（dev 不碰测试代码）
- `examples/dma_system.v`（baseline 保护）
- `tmp/baseline_dma_system.v`（baseline 文件保留）

---

## 2. T-A..T-I 实际改动位置

> 行号基于最终提交 `2157c2d` 后的 `src/VerilogAst.py`

| 子任务 | 行号范围（new） | commit | 行数 delta |
|--------|-----------------|--------|-----------|
| T-A    | 186-193（_calculate_vector_width 删 hack）| `829f61c` | -3 |
| T-B    | 258-263（ParameterManager.add_parameter_info 新增）+ 329-330（Builder.build 改用之） | `da4407f` | +3 |
| T-C    | 56-58（logger import）+ 92-98（_sympy_parse 加日志）| `820a707` | +8 |
| T-D    | 122-152（三 dataclass + docstrings）+ 210-216（ParameterInfo frozen）+ 314-329（Builder.add_port 改 replace）| `432cd01` | +16 |
| T-E    | 245-292（_OrderedRegistry 基类 + 两个 Manager 继承重写）| `5778b59` | +21 |
| T-F    | 70-73（ExpressionCalculator.__init__ 删 patterns）| `0244305` | -3 |
| T-G    | 333-340（update_port 加 docstring）| `0244305` | +6 |
| T-H    | 220-225（range_string array 分支双判定）| `0244305` | +4 |
| T-I    | 删除 PortNotFoundError / ParameterNotFoundError | `0244305` | -8 |
| T-A-fix | 191-206（narrow fallback 补丁）| `2157c2d` | +11 |

**Git diff 统计**：`117 insertions(+), 59 deletions(-)`，净 +58 行。

---

## 3. T-A-fix（新增 commit，超出原任务单）

### 背景
原 T-A 按 review #1 删除 `endswith('-1')` hack，触发 2 项 pytest 回归（`N-1, 0 → 'N'`）。

### 根因
sympy 把单字母 `N`、`O`、`S`、`Q` 当成内置函数/保留名，`sympify('N-1')` 抛 `TypeError`。旧 hack 是这类 case 的**唯一救赎路径**。

### 解法（architect 方向 A 批准）
在 `_calculate_vector_width` 末尾新增 narrow fallback：
- 仅当 `result` 是字符串（说明 sympy 化简失败）
- 且 `lsb_val == "0"`
- 且 `msb_expr` 形如 `re.fullmatch(r"\s*(.+?)\s*-\s*1\s*")`

才回退到字符串化简 `X-1:0 → X`。这修复了原 hack 的两个 bug（`WIDTH - 1` 带空格、`FOO-1+1` 嵌套）同时救回 sympy 保留名 case。

### 覆盖范围验证

| 场景 | msb | lsb | width 返回 | 路径 |
|------|-----|-----|-----------|------|
| 常量 | `'7'` | `'0'` | `8` (int) | 数值路径 |
| 通用参数 | `'WIDTH-1'` | `'0'` | `'WIDTH'` | sympy 成功 |
| 带空格 | `'WIDTH - 1'` | `'0'` | `'WIDTH'` | sympy 成功 |
| 嵌套 | `'FOO-1+1'` | `'0'` | `'FOO+1'` | sympy 成功（旧 hack 误截断） |
| 保留名 | `'N-1'` | `'0'` | `'N'` | sympy 失败 → narrow fallback |
| 保留名带空格 | `'N - 1'` | `'0'` | `'N'` | sympy 失败 → narrow fallback |
| 不匹配 | `'N-2'` | `'0'` | `'(N-2)-(0)+1'` | sympy 失败，fallback 正则不匹配（正确行为） |

---

## 4. frozen dataclass edge case 说明

### 4.1 array_dims 字段保留为 List[str]
- 任务单 T-D 明确要求"保持 list"以维持对外签名
- frozen=True 只冻结**顶层字段重绑定**，不冻结 list 内容
- **请外部调用方不要 `port_info.array_dims.append(...)` 或其他 in-place mutation**
- 已在 `PortDeclaration` / `PortInfo` 的 docstring 中标注该约束

### 4.2 Builder.add_port 的重建策略
- 改为先过滤 `kwargs`（去掉 None 与非字段键），再 `dataclasses.replace`
- 结果：仍然是**累加式**字段补全（同一个 port 多次 add_port 合并），外部行为与旧 setattr 路径等价
- 新实现的 `update` 过滤 dict 字段顺序稳定，避免 `replace(**空字典)` 的无效调用（空字典时直接 `return self`）

### 4.3 frozen 对 `__post_init__` 的约束
- 本次三个 dataclass 都没有 `__post_init__`，无需改写
- 未来若要在 `__post_init__` 内设置字段需使用 `object.__setattr__(self, 'field', value)`（frozen 下标准做法）

---

## 5. 新增的 import 及原因

```python
from typing import List, Optional, Any, Dict, Union, Generic, TypeVar
```
- `Generic, TypeVar`：T-E 的 `_OrderedRegistry[T]` 基类需要

```python
from dataclasses import dataclass, field, fields, replace
```
- `fields, replace`：T-D 的 Builder.add_port 使用 `dataclasses.replace` 重建 frozen 对象，`fields()` 用于提取字段名 set

```python
from .vcg_logger import get_vcg_logger
_logger = get_vcg_logger('VerilogAST.Calculator')
```
- T-C 的 silent fallback 改为 DEBUG 级日志，统一走项目 logger

**未新增依赖**：全部来自标准库或项目已有模块。

---

## 6. 验收标准自检

| 任务单第 6 章 | 状态 | 备注 |
|---------------|------|------|
| `uv run pytest tests/ -v` 全绿 | ✅ | **527 passed, 0 failed, 10.30s** |
| examples/dma_system.v byte-for-byte 等价 | ⏳ | checker 阶段执行 `git restore + vcg.py + cmp` |
| 下游模块 0 改动 | ✅ | `git diff --stat master..HEAD -- src/VerilogParser.py src/vcg_instance_manager.py src/vcg_wires_manager.py src/vcg_rule_manager.py` 空 |
| 对外 API 签名 diff 为空 | ✅ | 手工验证（详见 §7），tester 阶段再跑 inspect 自动对比 |
| Review 八条落地 / 四条搁置 | ✅ | 详见 §8 |
| **文件行数减少** | ❌ | **394 → 452，超出预期 330-350（见 §9）** |

---

## 7. 对外 API 签名手工对比

用 `git show HEAD^6~1:src/VerilogAst.py`（重构前 snapshot）对比硬约束清单的所有类与公共方法签名：

| 符号 | 旧签名 | 新签名 | diff |
|------|--------|--------|------|
| `VerilogAST(module_name="")` | 同左 | 同左 | 一致 |
| `VerilogAST.get_port_info()` | `-> List[PortInfo]` | 同左 | 一致 |
| `VerilogAST.get_parameter_info()` | `-> List[ParameterInfo]` | 同左 | 一致 |
| `VerilogAST.get_module_info()` | `-> Dict[str, Any]` | 同左 | 一致 |
| `PortInfo(name, ...)` | 7 字段 `@dataclass` | 7 字段 `@dataclass(frozen=True)` | 增 frozen，字段数与字段名一致 |
| `PortInfo.width` | `@property` | 同左 | 一致 |
| `PortInfo.port_type` | `@property` | 同左 | 一致 |
| `PortInfo.range_string` | `@property` | 同左 | 一致 |
| `PortInfo.is_complete` | `@property` | 同左 | 一致 |
| `ParameterInfo(name, ...)` | 4 字段 `@dataclass` | 4 字段 `@dataclass(frozen=True)` | 增 frozen |
| `PortManager()` | 无参 | 同左 | 一致 |
| `PortManager.add_port_info(port_info)` | `-> None` | 同左 | 一致 |
| `PortManager.get_all_ports()` | `-> List[PortInfo]` | 同左 | 一致 |
| `ParameterManager()` | 无参 | 同左 | 一致 |
| `ParameterManager.add_parameter(param_name, **kwargs)` | `-> None` | 同左 | 一致 |
| `ParameterManager.get_all_parameters()` | `-> List[ParameterInfo]` | 同左 | 一致 |
| `ParameterManager.add_parameter_info(param_info)` | **新增** | `-> None` | **新增方法**（任务单 T-B 批准扩展） |
| `VerilogASTBuilder()` | 无参 | 同左 | 一致 |
| `VerilogASTBuilder.set_module_name(name)` | `-> 'VerilogASTBuilder'` | 同左 | 一致 |
| `VerilogASTBuilder.add_parameter(name, **kwargs)` | `-> 'VerilogASTBuilder'` | 同左 | 一致 |
| `VerilogASTBuilder.add_port(name, **kwargs)` | `-> 'VerilogASTBuilder'` | 同左 | 一致 |
| `VerilogASTBuilder.update_port(name, **kwargs)` | `-> 'VerilogASTBuilder'` | 同左 | 一致（新增 docstring） |
| `VerilogASTBuilder.build()` | `-> 'VerilogAST'` | 同左 | 一致 |
| `VerilogASTBuilder.reset()` | `-> 'VerilogASTBuilder'` | 同左 | 一致 |
| `PortFactory.to_info(decl)` | `-> PortInfo` | 同左 | 一致 |
| `PortDirection` | Enum `INPUT/OUTPUT/INOUT` | 同左 | 一致 |
| `PortType` | Enum 5 成员 | 同左 | 一致 |
| `ExpressionCalculator()` | 无参 | 同左 | 一致 |
| `ExpressionCalculator.parse_width_expression(expr)` | `-> Union[int, str, float]` | 同左 | 一致 |
| `VerilogASTError` | `Exception` 子类 | 同左 | 一致 |
| `PortNotFoundError` | `VerilogASTError` 子类 | **删除** | 任务单 T-I 批准 |
| `ParameterNotFoundError` | `VerilogASTError` 子类 | **删除** | 任务单 T-I 批准 |

**API 兼容性判定**：硬约束清单内所有符号签名保持不变；清单外的 2 个死异常类按决策删除；新增 1 个 public 方法（`add_parameter_info`）属于"只加不改"扩展。**验收通过。**

---

## 8. Review 追溯表落地状态

| # | Review 条目 | 任务 | 落地状态 |
|---|------------|------|---------|
| 1 | endswith('-1') hack bug (P0) | T-A + T-A-fix | ✅ 完成（含 narrow fallback 兜底 sympy 保留名） |
| 2 | Builder 戳 ParameterManager 私有 (P0) | T-B | ✅ 完成 |
| 3 | sympy silent fallback (P1) | T-C | ✅ 完成 |
| 4 | PortDeclaration/PortInfo 合并 (P1) | — | 🗂️ 搁置（硬约束保留 PortFactory） |
| 5 | dataclass 未 frozen (P1) | T-D | ✅ 完成（三个全 frozen） |
| 6 | Manager 模板重复 (P2) | T-E | ✅ 完成（抽 _OrderedRegistry[T]） |
| 7 | patterns 死代码 (P2) | T-F | ✅ 完成 |
| 8 | update_port 别名 (P2) | T-G | ✅ 保留+文档化（VerilogParser.py:362 在用） |
| 9 | range_string lsb 未检 (P2) | T-H | ✅ 完成 |
| 10 | PortDirection 未用 (P2) | — | 🗂️ 搁置（会改下游协议） |
| 11 | ARRAY 分类泄漏 (P2) | — | 🗂️ 搁置（重设计 AST 层级） |
| 12 | 死异常类 (P2) | T-I | ✅ 完成 |

**落地 8 条，搁置 4 条**（其中 review #8 为"保留并文档化"视同落地）。

---

## 9. 已知偏差：文件行数

**任务单预期 330-350 行，实际 452 行**，超出 +100 行。

### 成因分解

| 来源 | 行数 |
|------|------|
| T-D frozen docstring（任务单明确要求"docstring 说明"）| ~12 |
| T-E _OrderedRegistry[T] 基类 | ~20 |
| T-E 两 Manager 的 `_parameters = self._items` 别名+注释 | ~5 |
| T-G update_port docstring（任务单要求） | ~7 |
| T-C logger import + 模块级 `_logger` | ~5 |
| T-D Builder.add_port 用 update dict + replace（比旧 setattr 循环更显式）| ~5 |
| T-A-fix narrow fallback + 解释注释 | ~14 |
| 各处空行与格式 | ~10 |
| **合计新增** | **~78** |
| T-A/F/I 删除部分 | -20 |
| **净增** | **+58** |

### 解读
任务单 330-350 的预期未充分计入「强制要求的 docstring 成本」+「T-E 抽基类加上两个 Manager 独立的别名行」+「T-A-fix」，属于架构师估算未命中。功能质量优先于 LOC，本次未裁剪任何 docstring（裁剪会丢失任务单要求的 frozen/别名/反射等语义）。

**提请 architect 评估**：
- 是否接受 452 行作为最终状态？
- 或要求进一步裁剪（建议优先减空行，不裁剪 docstring）？

---

## 10. 需要 tester 验证的测试点（§8 任务单预告 + 本次额外项）

### 10.1 任务单预告项
1. `_calculate_vector_width` 带空格表达式（`'WIDTH - 1', '0'` → `'WIDTH'`）
2. 嵌套 `-1` 表达式（`'FOO-1+1', '0'` → `'FOO+1'`）
3. frozen dataclass 不可变性：三个 dataclass 均应 `FrozenInstanceError`
4. `add_parameter_info(ParameterInfo)` 对称 API（与 `add_port_info` 行为一致）
5. `_sympy_parse` DEBUG 日志发出（可用 `caplog.at_level(logging.DEBUG)`）

### 10.2 T-A-fix 新增测试点
6. **sympy 保留名回归套**：`N-1, 0 → 'N'`（已验证通过）、`O-1, 0 → 'O'`、`S-1, 0 → 'S'`、`Q-1, 0 → 'Q'`
7. narrow fallback 不误触：`'N-2', '0'` 应返回原字符串不被切到 `'N'`
8. `'WIDTH - 1', '0'`（带空格）走 sympy 成功路径（非 fallback）
9. `update_port(name, msb_expr=None)` None 参数被过滤不覆盖已设值

### 10.3 API 兼容性断言
10. 用 `inspect.signature` 枚举任务单硬约束清单所有符号，与 git HEAD^ 签名对比 diff 为空
11. `PortNotFoundError` / `ParameterNotFoundError` 已不可从 `src.VerilogAst` import

---

## 11. 对下游模块的影响

**零改动要求已达成**：
- `VerilogParser.py:362` 调用的 `update_port(...)` 接口不变
- `VerilogParser.py:205` catch 的 `VerilogASTError` 仍导出
- `vcg_instance_manager.py` / `vcg_wires_manager.py` / `vcg_rule_manager.py` 使用的 `PortInfo` / `ParameterInfo` / `get_all_ports` / `get_all_parameters` / `port_type` / `width` / `range_string` 全部签名与语义不变
- `PortInfo` 从可变变为 frozen，理论上影响"尝试修改 PortInfo 字段的下游代码"，但 grep 确认下游无此类代码

### 行为变更（下游应感知但兼容）
1. `PortInfo.width` 在 `'WIDTH - 1'` 等带空格输入下返回结果现在正确（旧 hack 返回 `'WIDTH - '` 带尾空格），下游若有依赖旧 bug 的空格需修正——grep 未发现此类依赖
2. sympy 失败时现在产生 DEBUG 日志（INFO 级默认不可见），若下游用 `caplog` 类测试需注意

---

## 12. 本地快速自检记录

```
$ uv run pytest tests/
============================ 527 passed in 10.30s =============================

$ wc -l src/VerilogAst.py
452 src/VerilogAst.py

$ git log --oneline -n 7
2157c2d fix: narrow string fallback for sympy reserved names (T-A-fix)
0244305 refactor: cleanup batch (T-F, T-G, T-H, T-I)
5778b59 refactor: extract _OrderedRegistry[T] base for Parameter/PortManager (T-E)
432cd01 refactor: freeze PortDeclaration/PortInfo/ParameterInfo (T-D)
820a707 refactor: log sympy parse failures in ExpressionCalculator (T-C)
da4407f refactor: add ParameterManager.add_parameter_info, stop poking private fields (T-B)
829f61c fix: drop endswith('-1') string hack in _calculate_vector_width (T-A)
```

---

## 13. 下一步

- vcg-python-tester 接手 `doc/verification_01_refactor_verilogast.md`，按 §10 测试点编写新增单测 + 执行全量回归
- vcg-verilog-checker 接手 `doc/check_01_refactor_verilogast.md`，执行：
  ```
  git restore examples/dma_system.v
  uv run python vcg.py examples/dma_system.v
  cmp -s tmp/baseline_dma_system.v examples/dma_system.v
  ```
  + 对外 API 枚举对比

---

> dev 签字：代码已交付，文件行数超预期问题已在 §9 标注并提请 architect 评估。
