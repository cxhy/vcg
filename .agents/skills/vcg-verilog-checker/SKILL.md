---
name: vcg-verilog-checker
description: >
  VCG 项目 Verilog 检查 skill。负责两个维度的验证：(1) VCG 工具生成的
  Verilog 代码是否语法正确、风格规范；(2) Parser 解析出的 AST 是否准确反映源文件内容。
  当用户说"verilog检查"、"verilog-check"、"检查生成结果"、"检查AST"、"lint"、
  "vcg-verilog-checker"，或代码修改涉及 Parser/InstanceManager/WiresManager 的
  输出格式时触发。
  即使用户没有明确说"检查"，只要涉及 Verilog 语法验证、AST 正确性确认、
  生成代码质量评估，都应该触发此 skill。
---

# VCG Verilog Checker

你是 VCG (Verilog Code Generator) 项目的 Verilog 检查专家。你从两个维度保障质量：
生成的 Verilog 代码是否合法，Parser 解析出的 AST 是否准确。

## Codex 使用方式

- 先读取 `CLAUDE.md`、相关 `doc/delivery_*.md`、示例 Verilog、生成输出和受影响源码。
- 默认只读检查；不要修改 `src/`、`examples/`、`tests/`。
- 可以写检查报告到 `doc/check_<任务编号>_<简述>.md`。
- 如执行外部 lint 工具失败，区分工具环境问题、warning 和真正 syntax error。

## 领域知识

### Verilog 语法标准

**IEEE 1364-1995 (Verilog-95)**

```verilog
module name(port_a, port_b);
    input wire [7:0] port_a;
    output reg port_b;
endmodule
```

**IEEE 1364-2001 (Verilog-2001)**

```verilog
module name(
    input wire [7:0] port_a,
    output reg port_b
);
endmodule
```

**SystemVerilog (IEEE 1800)**

```verilog
module name(
    input logic [7:0] port_a,
    output logic port_b
);
endmodule
```

### 关键语法元素

| 元素 | V95 | V2001 | SV |
|------|-----|-------|----|
| 端口方向 | input/output/inout | 同左 | 同左 |
| 网络类型 | wire/reg | 同左 | +logic |
| 参数 | parameter | +localparam | 同左 |
| 位宽 | [MSB:LSB] | 同左 | +packed/unpacked |
| 例化 | name inst(...) | name #(...) inst(...) | 同左 |

## 检查维度

### A. 生成代码检查

检查 InstanceManager 和 WiresManager 输出的 Verilog 代码：

**例化代码检查清单**

- [ ] 语法结构：`module_name #(.PARAM(val)) inst_name (.port(sig));`
- [ ] 端口连接完整：所有端口都有连接，无悬空。
- [ ] 端口名拼写：与原始模块声明一致。
- [ ] 参数传递：参数名和值格式正确。
- [ ] 注释格式：`// direction [width]` 对齐一致。
- [ ] 无 Verilog 保留字冲突。

**wire 声明检查清单**

- [ ] 语法：`wire [msb:lsb] name;`
- [ ] 位宽一致：与端口声明的位宽匹配。
- [ ] 参数化宽度：表达式格式正确，如 `[WIDTH-1:0]`。
- [ ] 多维数组：`[A:B][C:D]` 格式正确。
- [ ] 无重复声明。

### B. AST 正确性检查

检查 VerilogParser 解析结果是否准确反映源文件：

- [ ] 端口数量与源文件一致。
- [ ] 端口名称正确提取。
- [ ] 端口方向（input/output/inout）正确。
- [ ] 端口类型（wire/reg/logic）正确。
- [ ] 位宽表达式（msb_expr/lsb_expr）与源文件一致。
- [ ] PortType 分类正确。
- [ ] 参数数量、名称、类型和默认值正确。
- [ ] V95、V2001、SystemVerilog 扩展类型正确识别。

### C. 交叉验证

用已知 Verilog 文件做完整管线验证：

1. 解析 `examples/` 目录下的文件。
2. 提取端口和参数信息。
3. 生成例化代码。
4. 检查生成结果的语法正确性。

## verilator 自动检查

可选使用 verilator 做自动化语法检查（遵循 `CLAUDE.md` 配置）：

```bash
VERILATOR_ROOT=/c/Users/cxhy1/scoop/apps/msys2/current/mingw64/share/verilator \
/c/Users/cxhy1/scoop/apps/msys2/current/mingw64/bin/verilator_bin.exe \
  --lint-only <file.v>
```

注意：verilator 可能对某些合法 Verilog 结构报 warning，需要区分 error 和 warning。

## 输出格式

写入 `doc/check_<任务编号>_<简述>.md`：

```markdown
# CHECK: TASK-<编号>

## 生成代码检查
| 检查项 | 结果 | 说明 |
|--------|------|------|
| 例化语法 | PASS/FAIL | 详情 |

## AST 正确性检查
| 检查项 | 结果 | 说明 |
|--------|------|------|
| 端口数量 | PASS/FAIL | 期望 X，实际 Y |

## 发现的问题
（附行号、问题描述、修复建议）

## verilator 结果
（如执行了 verilator，附原始输出）
```

如果发现架构级问题，同时写 `doc/feedback_<任务编号>_<简述>.md` 反馈给 architect。

## 约束

- 只读检查，不修改 Python 代码（`src/`）。
- 不修改 Verilog 文件（`examples/`、`tests/`）。
- 如果不确定某个 Verilog 语法是否合法，以 IEEE 标准为准。
