# CHECK: TASK-03

## 检查范围

- 读取 `CLAUDE.md`、TASK-03 task/delivery/verification 文档。
- 读取 `src/VerilogPreprocess.py`、`src/VerilogParser.py`、`tests/test_VerilogPreprocess.py`、`tests/test_VerilogParser.py`。
- 只读运行 `uv run python -c ...` 做预处理输出和 Parser AST smoke 检查。
- 只读运行 `uv run pytest tests/test_VerilogPreprocess.py tests/test_VerilogParser.py -q` 做聚焦回归确认。
- 复核 dev/tester 对 block comment leak feedback 的修复。

## 生成代码检查

本任务不涉及 InstanceManager/WiresManager 生成例化或 wire 声明代码，未执行 Verilog lint。

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 例化语法 | N/A | TASK-03 仅重构 Verilog 预处理。 |
| wire 声明 | N/A | TASK-03 未修改生成 wire 的路径。 |
| Parser 输入形态 | PASS | 额外 smoke 中通过的样例最终输出均为 `module ...` 开头、`endmodule` 结尾，模块体 `assign` / internal `wire` 未泄漏。 |

## AST 正确性检查

| 检查项 | 结果 | 说明 |
|--------|------|------|
| `preprocess_string()` 输出契约 | PASS | 条件编译、V95、V2001 样例输出均保持 Parser 可消费的 module header + port/parameter declarations + `endmodule`。 |
| `define` / `undef` 条件编译端口集合 | PASS | `FEATURE_A` 经 `define` 生效，`undef FEATURE_A` 后后续 `ifdef FEATURE_A` 不生效；AST 端口为 `clk`, `data_a`, `done`, `result`，不含 `data_b`, `data_default`, `stale`。 |
| 行注释中的 `;` 和预处理指令 | PASS | `// comment with ; and \`ifdef COMMENT_ONLY`、行尾 `// ; \`endif ignored` 未截断 header，也未污染条件栈；AST 端口为 `clk`, `valid`。 |
| 块注释中的预处理指令 | PASS | 块注释中的 `` `ifdef`` / `` `endif`` 不改变条件栈，符合 TASK-03 条件编译扫描目标。 |
| 块注释中的端口声明 | PASS/已修复 | 复核原 FAIL 样例，`input hidden;` 不再出现在最终预处理输出；Parser AST ports 只有 `clk`。 |
| module 前 attribute 最终保留 | PASS/RISK | `remove_pre_module_content()` 不丢 module，但 `preprocess_string()` 最终输出不保留 `(* keep_hierarchy = "yes" *)`。当前目标若仅是端口/参数 AST，不影响 AST；若后续要求保留 attribute 元数据，这是功能风险。 |
| `localparam` / parameter | PASS | V2001 header 中 `parameter WIDTH`、`localparam DEPTH` 可解析；V95/body 声明中 `parameter WIDTH`、`localparam HALF` 可解析。 |
| V95 样例 | PASS | `module legacy(clk, rst_n, data, ready);` + body port declarations 解析端口 `clk`, `rst_n`, `data`, `ready`，模块体 `assign` 未进入预处理输出。 |
| V2001 样例 | PASS | ANSI header、多行端口、`logic` 类型、参数化位宽可解析。 |

## 已修复问题

### FIXED-1: 块注释内端口声明不再污染预处理输出和 AST

复现样例：

```verilog
module block_comment_leak(
  input wire clk
);
  /* `ifdef COMMENT_ONLY
     input hidden;
     `endif */
endmodule
```

修复前 `preprocess_string()` 输出曾包含：

```verilog
module block_comment_leak(
  input wire clk
);
     input hidden;
endmodule
```

修复前 AST 端口集合为 `clk`, `hidden`。

复核结果：`VerilogPreprocess().preprocess_string()` 输出为：

```verilog
module block_comment_leak(
  input wire clk
);
endmodule
```

`VerilogParser().parse_string()` AST 端口集合为 `clk`，不含 `hidden`。

## 残余风险

- Attribute 行当前不进入最终预处理输出；本检查按“当前目标只是端口/参数 AST”判定为不影响 AST。如果未来 AST 需要记录 module attributes，需要新增明确需求和 Parser/AST 支持。
- TASK-03 明确非目标包括完整宏展开和 include 展开；本检查未要求这些能力。

## 命令结果

| 命令 | 结果 |
|------|------|
| `uv run python -c ...` | 退出码 1：首次综合 smoke 在 `comment_noise_v2001` 发现 `hidden` 伪端口，确认块注释声明污染 AST。 |
| `uv run python -c ...` | 退出码 0：复核脚本确认 `conditional_attr_v2001`、`v95_body_decls`、`line_comment_noise` PASS；确认 `block_comment_decl_leak` 出现 `['clk', 'hidden']`。 |
| `uv run pytest tests/test_VerilogPreprocess.py tests/test_VerilogParser.py -q` | 161 passed in 6.51s。 |
| `uv run python -c ...` | 退出码 0：block comment 专项复核 PASS；最终预处理输出不含 `input hidden`，AST ports 为 `['clk']`。 |
| `uv run python -c ...` | 退出码 0：综合 smoke 覆盖条件编译、V95、V2001、line comment、block comment；全部 PASS。attribute 最终仍不保留。 |
| `uv run pytest tests/test_VerilogPreprocess.py tests/test_VerilogParser.py -q` | 163 passed in 6.61s。 |

## 结论

TASK-03 预处理重构对常规 Parser 输入、条件编译端口筛选、attribute 不丢 module、V95/V2001 参数和端口解析总体可用；现有聚焦测试通过。

原 checker 发现的 block comment leak 已复核修复：块注释中的端口声明不会泄漏到最终预处理输出，也不会生成伪 AST 端口。保留的残余风险是 attribute 行最终不进入预处理输出；当前仅以端口/参数 AST 为目标时不影响结果。
