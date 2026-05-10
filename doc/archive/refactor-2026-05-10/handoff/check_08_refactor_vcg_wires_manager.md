# CHECK: TASK-08

## 生成代码检查

| 检查项 | 结果 | 说明 |
|--------|------|------|
| wire 声明语法 | PASS | 真实 `tests/sub_module.v` output 端口生成 `wire [WIDTH-1:0] data_out;` 与 `wire           valid;`，符合 `wire [range] name;` / `wire name;` 结构。 |
| 位宽一致性 | PASS | `data_out` 源端口为 `[WIDTH-1:0]`，生成声明保留 `[WIDTH-1:0]`；`valid` 为标量，生成无 range。 |
| 参数化宽度 | PASS | 参数化 range 未被误改写为 `[(WIDTH-1:0)-1:0]`。 |
| 表达式/赋值结构 | PASS | 本 smoke 不含赋值表达式；Python 测试覆盖 `wire name = expr;` 和带宽度赋值声明。 |
| 重复声明 | PASS | output 端口 smoke 生成 2 行，对应 `data_out` / `valid`，无重复。 |

## AST 正确性检查

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 端口方向 | PASS | `generate_wires_def(..., "output")` 只处理 output 端口。 |
| 端口位宽 | PASS | Parser 提供的 `PortInfo.width` / `range_string` 足以让 WiresManager 渲染参数化和标量 output。 |
| 多维端口 AST | N/A | TASK-08 未修改 Parser/AST。验证报告已记录 Parser 当前不完整支持 `[7:0][3:0]` packed 多维端口；本任务只保证 WiresManager 对传入多维字符串不误改写。 |

## 执行的 smoke

```text
uv run python -c "<generate WiresManager output from tests/sub_module.v and regex-check declarations>"
```

输出：

```verilog
wire [WIDTH-1:0] data_out;
wire           valid;
CHECK_PASS
```

## 发现的问题

未发现 TASK-08 引入的生成 Verilog 问题。

## verilator 结果

未执行 verilator。本次检查对象是 wire 声明片段而非完整 module；已用结构正则和现有 pytest 回归验证声明形态。
