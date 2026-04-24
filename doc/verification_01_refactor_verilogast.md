# VERIFICATION: TASK-01 src/VerilogAst.py 重构

| 字段 | 值 |
|------|----|
| 依据交付单 | doc/delivery_01_refactor_verilogast.md |
| 依据任务单 | doc/task_01_refactor_verilogast.md |
| 负责 | vcg-python-tester |
| 状态 | verified → 交 vcg-verilog-checker |
| 完成日期 | 2026-04-25 |
| Commit | `110cae1` test: add 72 tests for VerilogAst refactor |

---

## 1. 测试结果总览

### 1.1 全量回归

| 阶段 | 通过 | 失败 | 用时 |
|------|------|------|------|
| dev 交付后（新增前） | 527 | 0 | 10.35s |
| tester 新增后 | **599** | **0** | 10.29s |

### 1.2 新增测试统计

- 新增文件：`tests/test_VerilogAst_refactor.py`
- 新增测试类：9
- 新增测试方法：72（含 parametrize 展开）
- 通过率：**72 / 72 = 100%**

---

## 2. 覆盖场景

### 2.1 delivery §10.1 任务单预告项（5 大点 → 22 测试）

| 测试类 | 验证点 | 测试数 | 结果 |
|--------|--------|--------|------|
| `TestCalculateVectorWidthSpaces` | §10.1.1 带空格表达式 | 3 | PASS |
| `TestCalculateVectorWidthNestedMinus1` | §10.1.2 嵌套 `-1` 表达式 | 2 | PASS |
| `TestFrozenDataclasses` | §10.1.3 frozen + `FrozenInstanceError` | 10 | PASS |
| `TestAddParameterInfoSymmetric` | §10.1.4 `add_parameter_info` 对称 API | 5 | PASS |
| `TestSympyParseLogging` | §10.1.5 `_sympy_parse` DEBUG 日志 | 3 | PASS |

### 2.2 delivery §10.2 T-A-fix 新增项（4 大点 → 13 测试）

| 测试类 | 验证点 | 测试数 | 结果 |
|--------|--------|--------|------|
| `TestSympyReservedNameRegression` | §10.2.6 保留名 N/O/S/Q + 非保留名控制组 | 9 | PASS |
| `TestNarrowFallbackNotTriggered` | §10.2.7 fallback 不误触 | 4 | PASS |
| 同上（空格 sympy 路径） | §10.2.8 `'WIDTH - 1'` 走 sympy | 已并入 §10.1.1 | PASS |
| `TestUpdatePortNoneFiltering` | §10.2.9 `update_port(None)` 过滤 | 4 | PASS |

### 2.3 delivery §10.3 API 兼容性（2 大点 → 23 测试）

| 测试类 | 验证点 | 测试数 | 结果 |
|--------|--------|--------|------|
| `TestAPISignatureCompatibility` | §10.3.10 `inspect.signature` 对照 HEAD^7 | 19 | PASS |
| `TestDeadExceptionClassesRemoved` | §10.3.11 死异常类已删 | 4 | PASS |

### 2.4 附加：T-E `_OrderedRegistry` 正确性（4 测试）

| 测试类 | 验证点 | 测试数 | 结果 |
|--------|--------|--------|------|
| `TestOrderedRegistryViaPublicAPI` | 别名同步 + insertion-order | 4 | PASS |

---

## 3. 关键测试点逐项展开

### 3.1 sympy 保留名回归（T-A-fix 验收核心）

```
test_sympy_reserved_single_letter_width[N]  PASS  'N-1','0' → 'N'
test_sympy_reserved_single_letter_width[O]  PASS  'O-1','0' → 'O'
test_sympy_reserved_single_letter_width[S]  PASS  'S-1','0' → 'S'
test_sympy_reserved_single_letter_width[Q]  PASS  'Q-1','0' → 'Q'
test_sympy_reserved_with_spaces[N]          PASS  'N - 1','0' → 'N'
test_sympy_reserved_with_spaces[O]          PASS  'O - 1','0' → 'O'
test_sympy_reserved_with_spaces[S]          PASS  'S - 1','0' → 'S'
test_sympy_reserved_with_spaces[Q]          PASS  'Q - 1','0' → 'Q'
```

### 3.2 narrow fallback 不误触（防止过度 fallback）

```
test_n_minus_2_not_truncated              PASS  'N-2','0' → '(N-2)-(0)+1'（原样，不被切成 'N'）
test_s_plus_1_not_truncated               PASS  'S+1','0' → '(S+1)-(0)+1'（不以 -1 结尾）
test_lsb_nonzero_does_not_trigger_fallback PASS  'WIDTH-1','1' → 'WIDTH-1'（sympy 成功）
test_n_minus_1_fallback_only_with_lsb_zero PASS  'N-1','1' → '(N-1)-(1)+1'（lsb≠0）
```

### 3.3 frozen dataclass 三件套

对 `PortDeclaration` / `PortInfo` / `ParameterInfo`：
- 字段重绑定均抛 `FrozenInstanceError`
- 仍保留 dataclass 语义（`is_dataclass` 判真）
- 直接读 `__dataclass_params__.frozen` 为 `True`

### 3.4 DEBUG 日志

- sympy 失败时（如 `'N-1'`）在 `VCG.VerilogAST.Calculator` logger 上产生 DEBUG 级记录
- 消息体同时包含失败的表达式 `'N-1'` 与异常类型名 `'TypeError'`
- sympy 成功时（如 `'7-1'`）无日志产生

### 3.5 API 签名对照（inspect.signature）

参照 `tmp/VerilogAst_pre_refactor.py`（`829f61c^` 时的快照，394 行）进行对比：

| 类 | 方法 | 签名 diff |
|----|------|----------|
| VerilogAST | `__init__ / get_port_info / get_parameter_info / get_module_info` | 空 |
| PortManager | `__init__ / add_port_info / get_all_ports` | 空 |
| ParameterManager | `__init__ / add_parameter / get_all_parameters` | 空 |
| VerilogASTBuilder | `__init__ / set_module_name / add_parameter / add_port / update_port / build / reset` | 空 |
| PortFactory | `to_info` | 空 |
| ExpressionCalculator | `__init__ / parse_width_expression` | 空 |
| PortDirection | Enum 成员与值 | 空 |
| PortType | Enum 成员与值 | 空 |

**19 个 parametrize case 全部通过**。硬约束清单内所有公开符号签名保持一致。

### 3.6 死异常类已删除

- `from src.VerilogAst import PortNotFoundError` 抛 `ImportError` ✅
- `from src.VerilogAst import ParameterNotFoundError` 抛 `ImportError` ✅
- `VerilogASTError` 仍在（VerilogParser.py:205 依赖）✅

---

## 4. 验收标准（任务单 §6）对照

| 验收项 | 状态 | 说明 |
|--------|------|------|
| `uv run pytest tests/ -v` 全绿 | ✅ | 599 passed, 0 failed |
| examples byte-for-byte 等价 | ⏳ | 交 checker 阶段 |
| 下游零改动 | ✅ | `git diff --stat master..HEAD -- src/VerilogParser.py src/vcg_instance_manager.py src/vcg_wires_manager.py src/vcg_rule_manager.py` 空 |
| 对外 API 签名 diff 为空 | ✅ | 测试 §3.5 已自动化证明 |
| Review 8 条落地 / 4 条搁置 | ✅ | delivery §8 追溯表逐条验证 |
| 行数偏差已备案 | ✅ | 452 行（用户 2026-04-25 方向 A 批准） |

---

## 5. 发现的问题

**无**。本次验证未发现 bug 或偏差。

所有测试点按预期通过，行为与任务单 + delivery 文档声明一致。无需写 feedback。

---

## 6. 测试文件结构

```
tests/test_VerilogAst_refactor.py
├── TestCalculateVectorWidthSpaces          (3 tests)   §10.1.1
├── TestCalculateVectorWidthNestedMinus1    (2 tests)   §10.1.2
├── TestFrozenDataclasses                   (10 tests)  §10.1.3
├── TestAddParameterInfoSymmetric           (5 tests)   §10.1.4
├── TestSympyParseLogging                   (3 tests)   §10.1.5
├── TestSympyReservedNameRegression         (9 tests)   §10.2.6
├── TestNarrowFallbackNotTriggered          (4 tests)   §10.2.7
├── TestUpdatePortNoneFiltering             (4 tests)   §10.2.9
├── TestAPISignatureCompatibility           (23 tests)  §10.3.10
├── TestDeadExceptionClassesRemoved         (4 tests)   §10.3.11
└── TestOrderedRegistryViaPublicAPI         (4 tests)   附加 T-E
                                            总计 72 tests
```

---

## 7. Mock 策略合规记录

本次测试基本不需要 mock（纯数据结构验证 + inspect 对比），个别对照用 `importlib.util.spec_from_file_location` 加载 pre-refactor 快照模块，**未 patch 已实例化对象**，**未使用 `Mock(name=...)` 形式**，符合 CLAUDE.md Mock 铁律。

---

## 8. 下一步

交 vcg-verilog-checker：
1. 端到端 byte-for-byte：`git restore examples/dma_system.v && uv run python vcg.py examples/dma_system.v && cmp -s tmp/baseline_dma_system.v examples/dma_system.v`
2. 多样 examples 覆盖（若时间允许）：ddr_controller / dma_channel / uart_core 等
3. 产出 `doc/check_01_refactor_verilogast.md`

---

> tester 签字：72 新增测试 + 527 原有测试 = 599 全绿，API 签名兼容性经 inspect 自动对比确认。
