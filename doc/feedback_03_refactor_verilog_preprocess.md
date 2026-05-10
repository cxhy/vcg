# FEEDBACK: TASK-03

| 字段 | 值 |
|------|----|
| 来源 | vcg-verilog-checker |
| 严重性 | major |
| 日期 | 2026-05-10 |

## 问题描述

`src/VerilogPreprocess.py` 在 `extract_module_ports_section()` 阶段处理多行块注释时没有维护跨行注释状态。块注释中的端口声明文本会泄漏到最终预处理输出，并被 `VerilogParser` 解析成真实 AST 端口。

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

当前 `preprocess_string()` 输出中包含：

```verilog
     input hidden;
```

Parser AST 端口集合变成 `clk`, `hidden`，其中 `hidden` 是伪端口。

## 根因

`_strip_line_comment()` 每次都以 `in_block_comment=False` 调用 `_code_visible_to_preprocessor()`，没有把多行 `/* ... */` 状态传递给下一行。第一行进入块注释后，下一行 `input hidden;` 被当作普通可见 Verilog 代码。

## 复现步骤

1. 构造上述 Verilog 字符串。
2. 调用 `VerilogPreprocess().preprocess_string(code)`。
3. 用 `VerilogParser().parse_string(code)` 查看 AST 端口。

## 建议修复方向

- 在 `extract_module_ports_section()` 里按行扫描时维护块注释状态。
- 声明开始/结束判断应基于去注释后的可见代码。
- 注入到预处理输出的声明行也不应包含纯注释块内部文本。
- 增加回归测试：块注释中的 `input hidden;` 不出现在预处理输出，也不出现在 Parser AST。
