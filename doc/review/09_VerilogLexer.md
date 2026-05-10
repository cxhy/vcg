# Linus 风格技术评审：`src/VerilogLexer.py`

审查范围：只评审 `src/VerilogLexer.py`。`VerilogParser.py` 和测试只作为调用链证据，不展开评审。

## 品味评分

黄灯偏红：能跑窄路径，但词法契约不干净。最大问题不是正则写得丑，而是 lexer 在入口处偷偷改写、吞掉、误分类源码，然后把脏 token 流交给 Parser。Parser 后面再努力也只是擦屁股。

## 核心判断

值得修，而且应该先修 lexer 的契约。VCG 的核心任务是从 Verilog 模块里提取端口和参数；lexer 是整个 Parser 管线的第一道边界。这里不能“记录日志然后继续”，不能把合法 Verilog 标识符当关键字，也不能把合法数字字面量拆成半个数字加一个 ID。

## Linus 三问

1. 这是个真问题还是臆想出来的？

   真问题。最小样例已经能复现：`module m(input @clk); endmodule` 中非法字符被 `t_error()` 跳过，后续调用链仍可能构造出 `m` 和 `clk` 的 AST。坏输入被清洗成看似可用的输入，这是解析器最糟糕的失败模式。

2. 有更简单的方法吗？

   有。lexer 只做两件事：把源码切成 token；遇到不能切的源码就产生明确错误。不要在 lexer 里半吊子地解释字符串、吞非法字符、大小写折叠关键字。

3. 会破坏什么吗？

   会破坏当前错误行为：现有测试把大写 `MODULE` / `Input` 当关键字，这是不符合 Verilog 大小写敏感规则的。修正后这些测试要改。真正需要保护的是合法 Verilog 输入和下游 AST 契约，不是错误兼容性。

## 关键洞察

- 数据结构：核心数据不是一堆正则，而是 token 契约：`type` 必须准确，`value` 必须有一致语义。现在 `INTNUMBER_*` 保留源码风格的一部分，`STRING_LITERAL` 却去掉引号并解码转义，`ID` 又混进关键字、系统函数和反引号宏。
- 复杂度：多个小正则看起来简单，但没有统一的“字面量策略”和“错误策略”，导致复杂性泄漏到 Parser。
- 风险点：最危险的是静默跳过非法字符。它让后续阶段拿到的不是原始程序，而是被 lexer 私自修过的程序。

## 问题清单

### P0：词法错误被日志吞掉，非法源码会继续进入 Parser

位置：`src/VerilogLexer.py:228`

`t_error()` 只记录日志，然后 `t.lexer.skip(1)`：

```python
logger.error(...)
t.lexer.skip(1)
```

这不是错误处理，这是删除证据。lexer 没有 `errors` 状态，没有异常，没有错误 token，调用者无法可靠知道输入已经坏了。当前调用链里，非法字符可以被跳过后继续归约；`@clk` 会变成 `clk`。这会产生错误 AST 或至少产生误导性的 Parser 错误。

正确行为很简单：词法错误必须进入结构化错误通道。要么 fail fast 抛 VCGParseError/词法异常，要么收集 `LexError(line, column, char)` 并由 Parser 在返回 AST 前强制失败。不要只写 logger。

### P1：关键字大小写折叠，破坏 Verilog 的大小写敏感语义

位置：`src/VerilogLexer.py:210`

```python
t.type = self.reserved.get(t.value.lower(), 'ID')
```

Verilog 是大小写敏感语言。`module Module; endmodule` 里第二个 `Module` 是合法标识符，不是 `MODULE` 关键字。现在 lexer 会把它当关键字，合法模块名、端口名、参数名都可能被误杀。

这不是“用户写法宽容”，这是语言规则错误。关键字表应该只匹配精确小写关键字；需要兼容非标准大写关键字也不该默认打开。

### P1：数字字面量规则不是 Verilog 规则，还会部分匹配

位置：`src/VerilogLexer.py:190`

当前规则只接受小写 base specifier，且只接受纯 0/1、0-7、十六进制确定值：

- `8'HFF` 被拆成 `INTNUMBER_DEC("8")` + `ID("HFF")`
- `8'shFF` 被拆坏
- `4'b10xz` 被拆成 `INTNUMBER_BIN("4'b10")` + `ID("xz")`
- `8'hFx` 被拆成 `INTNUMBER_HEX("8'hF")` + `ID("x")`

Verilog 常见数字字面量包含大小写 base、可选 signed、以及 `x/z/?` 未知态。lexer 不支持完整子集可以接受，但不能“吃一半”。部分匹配比拒绝更坏，因为 Parser 后面看到的是伪造 token 流。

需要把 based number 作为一个整体匹配，并明确支持/拒绝合法范围。非法 based literal 应该作为词法错误报告，而不是拆成 number + ID。

### P2：字符串 token 在 lexer 阶段丢失源码语义

位置：`src/VerilogLexer.py:177`

`STRING_LITERAL` 去掉引号并手写解码 `\"`、`\n`、`\t`、`\\`。这导致 Parser 只能拿到已经失真的值。例子：`parameter S = "abc"` 的默认值会变成 `abc`，下游再也不知道它原来是字符串字面量而不是标识符文本。

lexer 不应该在没有统一 AST value 类型的情况下做语义解码。最少也要保留源码拼写，或把 token value 变成结构化值：`raw` 和 `decoded` 分开。

### P2：`ID` 同时承载普通标识符、系统函数和预处理语法

位置：`src/VerilogLexer.py:210`

```python
r'[a-zA-Z_`$][a-zA-Z_0-9`$]*'
```

这把 `` `define``、`$display`、普通 `clk` 都塞进 `ID`。系统函数如 `$clog2` 也许对表达式有用，但反引号宏属于预处理阶段；如果预处理后仍有反引号，应该是未展开宏或指令残留，不该假装成普通 ID。

另外，合法的 escaped identifier（例如 `\foo.bar `）完全不支持。VCG 可以选择不支持完整 Verilog，但这个边界必须明确，不要用一个过宽的 ID 正则掩盖不同语义。

## 改进方向

1. 先定义 lexer 契约：token value 到底保留源码文本，还是输出语义值。不要对数字保留一半源码、对字符串直接解码。
2. 词法错误改成结构化错误。删除“只 log + skip”的行为；Parser 返回 AST 前必须确认 lexer 没有错误。
3. 关键字匹配改为大小写敏感：`self.reserved.get(t.value, 'ID')`。
4. 重写 number literal 规则：支持 Verilog 常见 based literal（大小写 base、可选 signed、`x/z/?`、下划线），并避免部分匹配。
5. 拆清 `ID`：普通 identifier、system identifier、残留 preprocessor token 至少要有清楚策略。支持不了 escaped identifier 就明确报错或文档化。
6. 补测试时别只测 happy path。必须覆盖：非法字符导致 parse fail、大写标识符不被当关键字、`8'HFF`、`8'shFF`、`4'b10xz`、字符串参数保留字面量语义、CRLF 输入。

一句话结论：这个 lexer 现在像一个“尽量把东西凑成 token”的过滤器，而不是编译前端的边界。先把错误和 token value 契约收紧，Parser 后面的复杂度会少一截。
