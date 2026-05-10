# VERIFICATION: TASK-08

## 测试结果

| 命令 | 结果 |
|------|------|
| `uv run pytest tests/test_vcg_wires_manager.py -q` | PASS: `51 passed` |
| `uv run pytest tests/test_vcg_wires_manager.py tests/test_vcg_instance_manager.py tests/test_vcg_rule_manager.py -q` | PASS: `178 passed` |

## 覆盖场景

| 测试类别 | 覆盖内容 | 结果 |
|----------|----------|------|
| 文件解析 | 真实 parser 解析 V2001 样例并生成全部 greedy wire | PASS |
| 异常路径 | missing file、`VCGParseError`、`VCGSyntaxError`、未知异常包装 | PASS |
| 方向过滤 | `None` / `INPUT` / `Output` / `inout` / 非法方向 | PASS |
| 生成模式 | greedy/lazy 六种 rule matched × wire name 状态 | PASS |
| 宽度格式 | 标量、整数、数字字符串、单维 range、多维 range、参数名、表达式 | PASS |
| rule width 优先级 | rule width 覆盖 port width，空 rule width fallback 到 port width | PASS |
| 对齐渲染 | 默认 spacing、自定义 spacing、长 prefix 单空格 | PASS |
| 边界条件 | 空路径、空 module name、空端口列表、特殊 wire 名称 | PASS |
| 相关模块回归 | InstanceManager 与 RuleManager 契约 | PASS |

## 发现的问题

未发现产品代码问题。

测试阶段额外确认：旧测试中大量 `patch('src.vcg_wires_manager.VerilogParser')` 在
`WiresManager` fixture 创建后无效，本次已重写为直接替换 `wires_manager.parser` 或直接测试纯 helper。

## 残余风险

`VerilogParser` 当前对 SystemVerilog packed 多维端口（如 `[7:0][3:0]`）仍会记录语法错误并只返回单维向量信息。TASK-08 只保证 WiresManager 对已经传入的多维宽度字符串不误改写，未修改 Parser/AST 多维能力。
