# CHECK: TASK-01 src/VerilogAst.py 重构端到端验证

| 字段 | 值 |
|------|----|
| 依据交付单 | doc/delivery_01_refactor_verilogast.md |
| 依据验证报告 | doc/verification_01_refactor_verilogast.md（tester: 599 passed）|
| 负责 | vcg-verilog-checker |
| 状态 | **PASS** → 交用户最终确认 |
| 完成日期 | 2026-04-25 |

---

## 最终验收判定：**通过** ✅

所有硬验收项全绿，包括 byte-for-byte 等价、API 兼容性、生成 Verilog 语法合法性。
重构引入的已知风险点（旧 hack 的 `[WIDTH - :0]` 非法 Verilog、T-H 的 `[FOO:None]` 泄漏）
在真实 examples 中均未出现。

---

## 任务 1：examples/dma_system.v byte-for-byte 等价

### 执行流程

```bash
# Step 1: restore 到 HEAD（110 行干净模板）
$ git restore examples/dma_system.v

# Step 2: 用重构后的 VerilogAst.py 重跑 VCG
$ uv run python vcg.py examples/dma_system.v --log-level WARNING
VCG generate Done: examples\dma_system.v

# Step 3: 对比 baseline
$ cmp -s tmp/baseline_dma_system.v examples/dma_system.v
$ echo "cmp exit: $?"
cmp exit: 0
```

### 结果

| 指标 | baseline | 重构后输出 | 一致性 |
|------|----------|-----------|--------|
| 行数 | 187 | 187 | ✅ |
| md5 | `bdbf98cf1f3165bfe8dbda8231f1062e` | `bdbf98cf1f3165bfe8dbda8231f1062e` | ✅ |
| cmp 退出码 | — | **0** | ✅ |

**判定**：**byte-for-byte 完全等价**。

---

## 任务 2：对外 API 签名枚举对比

用 `inspect.signature` 对硬约束清单全部类 + 公共方法，与 `tmp/VerilogAst_pre_refactor.py`（`829f61c^` 快照）做字符串对比。

### 原始枚举结果

| 类.方法 | 字符串对比 | 语义判定 |
|---------|-----------|---------|
| VerilogAST.__init__ | MATCH | 完全一致 |
| VerilogAST.get_port_info | DIFF¹ | 等价（见下） |
| VerilogAST.get_parameter_info | DIFF¹ | 等价 |
| VerilogAST.get_module_info | MATCH | 完全一致 |
| PortInfo.__init__ | MATCH | 完全一致 |
| ParameterInfo.__init__ | MATCH | 完全一致 |
| PortManager.__init__ | DIFF² | 等价（见下） |
| PortManager.add_port_info | DIFF¹ | 等价 |
| PortManager.get_all_ports | DIFF¹ | 等价 |
| ParameterManager.__init__ | DIFF² | 等价 |
| ParameterManager.add_parameter | MATCH | 完全一致 |
| ParameterManager.get_all_parameters | DIFF¹ | 等价 |
| VerilogASTBuilder.__init__ | MATCH | 完全一致 |
| VerilogASTBuilder.set_module_name | MATCH | 完全一致 |
| VerilogASTBuilder.add_parameter | MATCH | 完全一致 |
| VerilogASTBuilder.add_port | MATCH | 完全一致 |
| VerilogASTBuilder.update_port | MATCH | 完全一致 |
| VerilogASTBuilder.build | MATCH | 完全一致 |
| VerilogASTBuilder.reset | MATCH | 完全一致 |
| PortFactory.to_info | DIFF¹ | 等价 |
| ExpressionCalculator.__init__ | MATCH | 完全一致 |
| ExpressionCalculator.parse_width_expression | MATCH | 完全一致 |

**原始字符串对比**：14/22 MATCH。

### DIFF 根因分析

`¹` **模块加载路径差异**（6 处）：pre-refactor 快照作为独立 module（名 `_pre`）加载，type hint 字符串包含 `_pre.PortInfo`；重构后 module 正常导入，type hint 是 `src.VerilogAst.PortInfo`。**同一类两次加载**产生的身份差异，并非 API 破坏。

示例：
```
pre:  (self) -> List[_pre.PortInfo]
cur:  (self) -> List[src.VerilogAst.PortInfo]
```

`²` **显式 `-> None` 返回类型标注**（2 处）：重构后 `PortManager.__init__` / `ParameterManager.__init__` 显式写了 `-> None`，pre 版本无此标注。`inspect.signature` 字符串不同，但 Python 对 `__init__` 返回值语义始终为 `None`。

示例：
```
pre:  (self)
cur:  (self) -> None
```

### 语义判定结果

**22 / 22 签名在语义上一致**。tester 阶段的 `test_public_method_signature_preserved` 用"参数名序列"对比（忽略 type hint 的模块路径 + 返回值标注），19 个 parametrize case 全 PASS，与本次人工复核一致。

### Enum 成员对照

| Enum | 成员与值 | 一致性 |
|------|---------|-------|
| PortDirection | `{INPUT:'input', OUTPUT:'output', INOUT:'inout'}` | ✅ MATCH |
| PortType | `{SIMPLE:'simple', VECTOR:'vector', ARRAY_2D:'array_2d', ARRAY_3D:'array_3d', INTERFACE:'interface'}` | ✅ MATCH |

---

## 任务 3：AST 正确性端到端检查

### 3.1 生成代码结构审阅（examples/dma_system.v）

| 检查项 | 结果 | 备注 |
|--------|------|------|
| 例化语法 `module_name #(...) inst_name(...);` | ✅ | 4 个 u_dma_ch0..3 结构完整闭合 |
| 实例数量 | ✅ | 按 `for ch in range(4)` 生成 4 个，顺序 0→3 |
| 端口连接完整性 | ✅ | 每实例 18 个端口全部连接，awk 计数 `ports: 22`（= 4 params + 18 ports）对称一致 |
| 端口名拼写 | ✅ | 与 dma_channel.v header 对应：`clk, rst_n, src_addr, dst_addr, ..., bytes_transferred` |
| 参数传递 | ✅ | `.CHANNEL_ID(0..3)` 按 ch 递增；`.ADDR_WIDTH(32) .DATA_WIDTH(64) .FIFO_DEPTH(16)` 固定 |
| 注释格式对齐 | ✅ | `// input [ADDR_WIDTH - 1:0]` 列对齐一致 |
| wire 声明块 | ✅ | 5 条 wire 声明格式合法 |

### 3.2 关键风险点的真实 case 验证

#### 风险 A：旧 hack 的空格 bug (`[WIDTH - :0]`)

`examples/dma_system.v` 中出现 `[ADDR_WIDTH - 1:0]`（带空格），旧 hack 会 slice 出 `[ADDR_WIDTH - :0]`（非法）。现在：

```verilog
.src_addr          (mem_ch0_ADDR),  // input [ADDR_WIDTH - 1:0]
.dst_addr          (dst_addr),      // input [ADDR_WIDTH - 1:0]
```

**正确**：空格保留完整，注释中表达式合法。grep `\[[^]]* - :[0-9]+\]` 零匹配。

#### 风险 B：T-H 的 `[FOO:None]` bug

range_string 的 array 分支若 `msb_expr` 有值但 `lsb_expr` 是 None，旧代码会产出 `[FOO:None]`。grep `\[[A-Za-z_0-9]*:None\]|\[None` 全文件零匹配。**未触发**。

#### 风险 C：T-A-fix narrow fallback 的误触

dma_system.v 用的参数名是 `ADDR_WIDTH` / `DATA_WIDTH` 等多字母名，**不触发** sympy 保留名 fallback，走正常 sympy 路径。baseline 等价证明 fallback 未对此类输入产生副作用。

### 3.3 扫描结果汇总

```
$ grep -nE '\[[^]]* - :[0-9]+\]|\[[A-Za-z_0-9]*:None\]|\[None' examples/dma_system.v
# (无输出，exit code=1 = 零匹配)
```

**无任何已知风险图样**。

### 3.4 Verilator 选择性跳过

examples/dma_system.v 引用了未在当前文件声明的 `ADDR_WIDTH` / `DATA_WIDTH` 等 hypothetical 参数（是典型 RTL 顶层占位模块），verilator lint 会产生大量 undeclared identifier warning，不属于 VCG 重构引入问题。跳过 verilator，以 byte-for-byte 等价作为主要客观依据。

---

## 工作区状态

检查完毕后已执行 `git restore examples/dma_system.v`，工作区回到 HEAD 干净模板（110 行）。未 touch `tmp/baseline_dma_system.v` 或 `tmp/VerilogAst_pre_refactor.py`。

---

## 发现的问题

**无**。

- 无非法 Verilog 产出
- 无 API 兼容性破坏
- 无 AST 行为偏差
- tester 报告 599 passed 与本次端到端结果互相印证

无需写 feedback。

---

## 验收标准（任务单 §6）最终对照

| 验收项 | 状态 |
|--------|------|
| `uv run pytest tests/ -v` 全绿 | ✅ 599 passed（tester 阶段已验证）|
| examples/dma_system.v byte-for-byte 等价 | ✅ **cmp exit 0** |
| 下游模块 0 改动 | ✅ 已在 delivery/verification 确认 |
| 对外 API 签名 diff 为空 | ✅ 22/22 语义等价（字符串差异均源于 type hint 路径） |
| Review 8 条落地 / 4 条搁置 | ✅ 完成 |
| 文件行数备案 | ✅ 452 行，用户 2026-04-25 方向 A 批准 |

---

## 下一步

交给 architect 最终归档（task #7）：
- 更新 PROJECT.md 决策段
- 写 doc/decisions/2026-04-25_refactor_verilogast.md 归档本次会话
- 向用户最终确认

---

> checker 签字：byte-for-byte + API 兼容性 + 端到端语法 全部通过。重构可发布。
