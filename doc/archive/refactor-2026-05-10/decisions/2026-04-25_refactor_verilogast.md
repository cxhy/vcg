# 2026-04-25: VerilogAst.py 模块级重构

## 概览

依据 Linus 风格评审 `doc/review/11_VerilogAst.md` 对 `src/VerilogAst.py` 做模块级重构。
四 agent 协作流程完整走通：architect → dev → tester → checker → 归档。

## 时间线

| 阶段 | 产出 | commit |
|------|------|--------|
| architect | `doc/task_01_refactor_verilogast.md`（含 review 条目↔任务追溯表、硬约束、风险） | — |
| 用户 gate 1 | 4 个关键冲突决策（PortFactory / 死异常 / Manager 扩展 / 搁置清单） | — |
| 用户 gate 2 | 3 个策略决策（frozen 执行 / diff 接受规则 / baseline 采集方式） | — |
| dev T-A..T-I | 6 个 commit，pytest 525→525 通过 + 2 回归 | 829f61c..0244305 |
| dev → architect | `doc/feedback_01_sympy_reserved_names.md`（sympy 保留名 `N` 冲突） | — |
| 用户 gate 3 | 方向 A：narrow fallback 补丁 | — |
| dev T-A-fix | re.fullmatch 精确匹配的 fallback | 2157c2d |
| 用户 gate 4 | 接受 LOC 偏差（452 vs 330-350） | — |
| tester | 72 项新测试 + 599 passed 全绿 | 110cae1 |
| checker | byte-for-byte 等价 + API 22/22 语义等价 + AST 端到端审阅 | — |
| 归档 | 本文件 + PROJECT.md 决策 6-12 | — |

## 用户决策点归档（共 5 轮 gate）

### Gate 1：review 冲突取舍
1. **PortFactory 保留原样**（方案 B），放弃 review #4 合并建议
2. **允许删除** PortNotFoundError / ParameterNotFoundError
3. **允许**"只加不改"扩展 Manager：add_parameter_info + _OrderedRegistry[T]
4. **搁置** review #10 PortDirection 启用、#11 ARRAY 分类重设计

### Gate 2：实施策略
5. **三 dataclass 全部 frozen=True**，Builder 用 dataclasses.replace
6. **byte-for-byte 等价**为硬验收，任何 diff 找用户
7. **立刻跑当前 HEAD** 采 baseline 到 `tmp/baseline_dma_system.v`

### Gate 3：T-A 回归修复
8. **方向 A**：保留 6 个 commit，加 narrow fallback 补丁
   - 触发条件：sympy 失败（result 是 str）+ lsb=='0' + `re.fullmatch(r'\s*(.+?)\s*-\s*1\s*')`
   - 防误触边界：`N-2, 0`、`S+1, 0`、`lsb!=0` 均正确保持原样

### Gate 4：行数偏差
9. **接受 452 行**最终状态（+58 vs 预估）

### Gate 5：最终验收
10. **通过归档**

## 关键技术洞见

### sympy 保留名陷阱

单字母 `N`、`O`、`S`、`Q` 是 sympy 的内置函数/保留符号，`sympify('N-1')` 抛
`TypeError: unsupported operand type(s) for -: 'function' and 'One'`。

这导致 Linus review #1 的"让 sympy 全盘化简"方案不完备——`WIDTH-1` 能工作，
但 `N-1` 会回归。narrow fallback 是 sympy 保留名下的必要补救，不是"坏品味"。

**记住**：`sympify` 在 Verilog 参数名命名规则（字母数字下划线）下并非无条件可用，
边界集至少包括 `{E, I, N, O, S, Q, C}`。

### frozen dataclass 对 List 字段

`@dataclass(frozen=True)` 只防顶层字段重绑定，对 `array_dims: List[str]` 这类
mutable 字段的 `.append()` / 切片赋值无保护。本次保留 list（维持对外签名），
用 docstring 约定式不可变。下次迭代可评估改 `Tuple[str, ...]`——但会破坏字面语义
（len、迭代仍可用，但 Hash 行为改变）。

### "只加不改"的 API 扩展策略

硬约束"公共方法签名不变"不阻止**新增**方法。本次给 ParameterManager 加
`add_parameter_info(ParameterInfo)` 是对称扩展（匹配 PortManager.add_port_info），
Builder.build() 改用之后封装违反消失。**这是破坏/非破坏变更的边界最清晰案例**。

### _OrderedRegistry[T] 的别名保险

```python
class ParameterManager(_OrderedRegistry[ParameterInfo]):
    def __init__(self) -> None:
        super().__init__()
        self._parameters = self._items       # 别名，非拷贝
        self._parameter_order = self._order  # 别名，非拷贝
```

这些别名是零成本的防御措施：万一有外部代码偷读下划线字段（grep 未见，
但保险），能继续工作。tester 专门加了 `pm._parameters is pm._items` 断言。

## 对未来工作的指引

1. **Lexer/Parser 层的类似重构**可套用本次流程：architect 出 task + 用户 gate，
   dev 逐 commit，tester 写对照测试，checker 做 byte-for-byte 回归
2. **baseline 归档是必备步骤**：任何会改变生成代码的重构，先 `cp example.v
   tmp/baseline_*.v` 保存参考
3. **feedback 文档要写根因**：本次 feedback_01 不是简单"测试挂了"，而是详细分析
   了 sympy 保留名语义+备选方案对比，这让用户决策更高效
4. **LOC 预估务必计入 docstring 成本**：任务单的 330-350 行预估失准，
   核心原因是低估了强制 docstring；下次预估加 15-20% 文档余量

## 关联文档

- `doc/task_01_refactor_verilogast.md` - 原始任务单
- `doc/delivery_01_refactor_verilogast.md` - dev 交付单
- `doc/verification_01_refactor_verilogast.md` - tester 验证报告
- `doc/check_01_refactor_verilogast.md` - checker 端到端报告
- `doc/feedback_01_sympy_reserved_names.md` - sympy 保留名回归分析
- `doc/review/11_VerilogAst.md` - 原始 Linus 评审

## 关联 commit

```
2157c2d fix: narrow string fallback for sympy reserved names (T-A-fix)
0244305 refactor: cleanup batch (T-F, T-G, T-H, T-I)
5778b59 refactor: extract _OrderedRegistry[T] base for Parameter/PortManager (T-E)
432cd01 refactor: freeze PortDeclaration/PortInfo/ParameterInfo (T-D)
820a707 refactor: log sympy parse failures in ExpressionCalculator (T-C)
da4407f refactor: add ParameterManager.add_parameter_info, stop poking private fields (T-B)
829f61c fix: drop endswith('-1') string hack in _calculate_vector_width (T-A)
110cae1 test: add 72 tests for VerilogAst refactor (TASK-01 verification)
```

## 验收数据

- pytest: **599 passed, 0 failed**（527 原有 + 72 新增）
- examples/dma_system.v: **cmp exit 0**（md5 `bdbf98cf1f3165bfe8dbda8231f1062e`）
- API 兼容性: **22/22 签名语义等价**
- 文件行数: 394 → 452（+58，用户批准）
- 下游改动: **0 字节**
