# CHECK: TASK-07

## 生成代码检查

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 参数覆盖语法 | PASS | `sub #(` + `.WIDTH(16)` + `) u_sub (` 结构正确 |
| 端口连接语法 | PASS | `.port(signal)` 格式正确，最后一项无尾逗号 |
| 端口顺序 | PASS | `clk`、`data_in`、`data_out`、`done` 保持源模块顺序 |
| 信号规则 | PASS | `clk -> sys_clk`、`data_in -> bus_data`、`data_out -> bus_out` |
| 默认连接 | PASS | 未匹配的 `done` 使用自身名称 |
| 注释格式 | PASS | 保留方向与位宽注释 |

## Smoke 输出

```verilog
sub #(
    .WIDTH             (16)
) u_sub (
    .clk               (sys_clk),       // input
    .data_in           (bus_data),      // input [WIDTH - 1:0]
    .data_out          (bus_out),       // output [WIDTH - 1:0]
    .done              (done)           // output
);
```

## 执行命令

使用临时 `sub.v`，通过 `InstanceManager` 和 `VCGRuleManager` 直接生成例化。

首次运行遇到 sandbox 对 `uv` cache 的访问限制：

```text
Failed to initialize cache ... os error 5
```

随后按环境规则提升权限重跑，命令 PASS。

## 发现的问题

未发现生成 Verilog 结构问题。
