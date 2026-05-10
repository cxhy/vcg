# src/VerilogParser.py Linus 风格技术评审

评审日期: 2026-05-10
评审范围: 只评审 `src/VerilogParser.py`。只读 `CLAUDE.md`、`PROJECT.md`、`src/VerilogAst.py`、`src/VerilogLexer.py`、`src/VerilogPreprocess.py`、`src/vcg_instance_manager.py`、`src/vcg_wires_manager.py`、`tests/test_VerilogParser.py` 和相关既有 review，用于理解上下游契约。

## 品味评分

🔴 **垃圾，但已经不是旧版那种全面崩坏。**

旧版最恶心的 `except Exception: return None` 和伪造空 AST 已经被砍掉了，这是进步。但当前核心契约仍然错：Parser 已经记录了语法错误，还能返回一个看起来成功的 AST。对代码生成器来说，这不是"容错"，这是 silent corruption 的新形态。

## 核心判断

❌ **不值得保留现状。**

这个文件应该提供一个简单契约：成功返回完整 AST，失败抛 `VCGParseError` / `VCGFileError`。现在它变成了三态：成功 AST、失败异常、带错误的成功 AST。第三态最糟，因为下游 `InstanceManager` / `WiresManager` 直接信 AST 生成 Verilog，错误会跑到更远的地方爆。

必须先修错误契约，再谈语法覆盖率。别先加 SystemVerilog，别先缓存 PLY 表，先让 Parser 不撒谎。

## Linus 三问

1. **这是真问题吗？**
   是。`parse_string()` 当前在 `self.parse_errors` 非空时只打 warning，只要 `self.ast` 不为 `None` 就返回 AST（`src/VerilogParser.py:115-128`）。实测非法字符、额外 token、命名例化里的 `.` 都能在某些路径下返回 AST。

2. **有更简单的方法吗？**
   有。`self.parse_errors` 非空就抛 `VCGParseError`。不要把语法错误降级成 warning。Lexer 也要把非法字符送进同一个错误通道，而不是只写日志。

3. **会破坏什么吗？**
   会破坏那些依赖"坏 Verilog 也返回部分 AST"的测试和脚本。但这不是用户空间契约，这是 bug。项目文档写的是解析 Verilog 模块并提取端口，不是从垃圾输入里猜一个半成品 AST。代码生成器宁可早失败，也不能生成错误 Verilog。

## 关键洞察

- **数据结构**: 真实状态只有 `builder`、`ast`、`parse_errors` 三个实例字段。问题是它们没有被建模成统一结果：`ast != None` 被当成成功，`parse_errors != []` 被当成 warning。两个事实互相打架。
- **复杂度**: yacc action 通过副作用写 builder，最后 `_finalize_ast()` build AST。这个模型能用，但必须有硬性的成功/失败边界。现在错误恢复、日志、AST 构建混在一起。
- **风险点**: 下游直接调用 `parse_file()`，拿端口和参数生成 instance/wire。Parser 返回带错误 AST，就会把"解析失败"变成"生成错 Verilog"。

## 问题列表

### P0 - `parse_errors` 非空仍返回 AST，Parser 契约是坏的

位置: `src/VerilogParser.py:115-128`

当前逻辑：

```python
if self.parse_errors:
    self.logger.warning(...)

if self.ast is None:
    ...
return self.ast
```

这等于说："我知道有语法错误，但只要凑出了 AST，就当成功。"这是 Parser 最不该做的事。

实测这些输入都可能返回 AST，同时 `parse_errors` 非空或 lexer 已报错：

```verilog
module a(input x); endmodule module b(output y); endmodule
module top(input a); child u0 (.a(a)); endmodule
module m(input a@); endmodule
```

最坏的是非法字符多行场景：

```verilog
module m(
  input a@
);
endmodule
```

lexer 打了 `Illegal character '@'`，但 `parse_string()` 返回 `m` 的 AST，`parse_errors` 还是空。这就是 silent corruption。

修法很简单：`self.parse_errors` 非空就抛 `VCGParseError`，不要看 `self.ast`。错误恢复可以继续用于收集更多错误，但最终结果必须失败。

### P0 - Lexer 错误没有进入 Parser 错误通道

位置: `src/VerilogParser.py:105-109`，相关 lexer 行为在 `src/VerilogLexer.py:t_error`

`VerilogLexer.t_error()` 只记录日志并 `skip(1)`。`VerilogParser` 没有任何方式知道发生过非法字符。于是非法字符如果没有触发后续语法错误，就会静默通过。

这直接违反 `parse_string()` docstring 里"词法失败抛 `VCGParseError`"的承诺（`src/VerilogParser.py:93-95`）。

不要靠 logger 传递控制流。lexer 应该积累 lexical errors，或直接抛项目异常。Parser 在 parse 之后检查 lexer 错误并合并进 `VCGParseError`。

### P1 - ANSI 端口声明不继承方向和位宽，解析结果错

位置: `src/VerilogParser.py:266-293`

当前 grammar 把每个逗号分隔项都当成完整 `port_declaration`：

```python
port_list : port_declaration
          | port_list COMMA port_declaration
```

这导致 Verilog 常见写法解析错：

```verilog
module m(
  input [7:0] a, b
);
endmodule
```

当前 AST 是：

```text
a: input [7:0]
b: direction=None, range=""
```

这不是边角语法，这是正常 ANSI header。`b` 应该继承 `input [7:0]`。现在下游会把 `b` 当无方向单 bit 端口，wire/instance 注释和过滤都会错。

根因是数据结构不对：`port_list` 没有携带"当前声明上下文"。正确模型应该先解析一个声明组：`direction + net_type + dimension + identifier_list`，再把同一属性应用到所有名字。不要让第二个名字重新走一遍可选 direction 的规则。

### P1 - Header parameter list 不支持标准的声明内多赋值

位置: `src/VerilogParser.py:214-238`

当前只接受：

```verilog
#(parameter A=1, parameter B=2)
```

但常见写法是：

```verilog
#(parameter A=1, B=2)
```

`parameter_declaration_list` 的逗号层级放错了：它要求逗号后又是完整 `parameter_declaration`，而不是同一个 declaration 下的 `param_assignment_list`。body 参数已经有 `param_assignment_list`（`src/VerilogParser.py:371-400`），header 却没有复用。

这不是"少支持一种风格"，这是同一个语言结构在 header/body 两套规则里行为不一致。

### P1 - `p_error()` 调 `errok()` 但不推进 token，错误恢复边界不可信

位置: `src/VerilogParser.py:529-541`

当前：

```python
self.parse_errors.append(error_msg)
self.parser.errok()
```

没有 discard 当前 token，也没有交给明确的 `error` production 做完整恢复。结果就是 Parser 可能在已经构建 AST 后继续对后续 token 报错，然后 `parse_string()` 又把这些错误降级成 warning 返回 AST。

如果选择依赖 `error` production，就别在 `p_error()` 里假装恢复成功。否则就明确跳过一个 token。两套恢复策略混着用，是 yacc 里最容易制造幻觉的写法。

### P2 - `module_item_instance` 只支持位置例化，不支持命名端口例化

位置: `src/VerilogParser.py:408-411`

当前规则：

```python
module_item_instance : ID ID LPAREN expression_list RPAREN SEMICOLON
```

它能吞 `child u0(a, b);`，但不能吞真实项目里更常见的：

```verilog
child u0 (.clk(clk), .rst_n(rst_n));
```

因为 lexer 连 `.` token 都没有，`VerilogLexer.t_error()` 会把点当非法字符跳过。结合 P0/P0，结果可能是日志报错但 Parser 返回 AST。

如果 Parser 的目标只是提取模块头，那就不要假装解析 instance。更好的方向是让预处理器只交给 Parser 头部和端口/参数声明，body 里的 instance 根本别进 grammar。当前半支持只会误导维护者。

### P2 - 一行模块输入容易把额外 `endmodule` 当作错误 token，但仍返回 AST

位置: `src/VerilogParser.py:101-109`，触发来自预处理后输入

`parse_string()` 无条件解析预处理结果。对于一行模块：

```verilog
module m; endmodule
```

预处理层可能给 Parser 这样的文本：

```verilog
module m; endmodule
endmodule
```

Parser 会先 finalize 出 AST，再对额外 `endmodule` 记录错误。由于 P0，最终仍返回 AST。这暴露的是 Parser 的成功边界太弱：一旦 `module_declaration` reduction 完成，后面的垃圾没有让整个 parse 失败。

Parser 顶层 grammar 应该明确接受 EOF，或者 parse 结束后只要有错误就失败。不要允许"前缀合法，后缀垃圾"成为成功。

### P2 - `_finalize_ast()` 在 yacc action 里写全局实例状态，错误语义靠调用方猜

位置: `src/VerilogParser.py:177-208`

`p_module_declaration()` 里直接调用 `_finalize_ast()`，把 `self.ast` 写成最终结果。这个模型在单模块解析里能跑，但它把 parser action 和最终成功状态绑死了。

一旦后续 token 出错，`self.ast` 已经不为 `None`；一旦 builder build 失败，错误只进 `parse_errors`。最终到底算成功还是失败，全靠 `parse_string()` 后处理。现在后处理是错的，所以这个副作用模型放大了问题。

更干净的做法是让 yacc rule 只返回构建结果，`parse_string()` 拿 parse result 后统一决定成功/失败。短期至少要让 `_finalize_ast()` 只记录 AST，不参与错误吞吐策略。

### P3 - `get_module_info()` 复制了 `VerilogAST.get_module_info()` 的数据投影

位置: `src/VerilogParser.py:130-152`，对比 `src/VerilogAst.py:390-405`

`VerilogParser.get_module_info()` 自己把 `PortInfo` / `ParameterInfo` 转 dict，而 `VerilogAST` 也有 `get_module_info()`。两个方法返回结构还不一样：Parser 版本把端口转 dict，AST 版本返回对象并附带 summary。

这不是立即 bug，但这是重复数据投影。以后字段改名、`PortInfo` 结构扩展、summary 规则调整，两边一定会漂。

建议让 AST 成为唯一信息源：要么 Parser 删除这个 convenience 方法，要么 Parser 只调用一个明确的 AST 序列化方法。不要在 Parser 里维护第二套 view model。

### P3 - PLY parser 每个实例都重建，性能问题先记账

位置: `src/VerilogParser.py:62`

```python
self.parser = yacc.yacc(module=self, debug=debug, write_tables=False)
```

每个 `VerilogParser()` 都重建 yacc 表。`InstanceManager` 和 `WiresManager` 初始化时各自创建 Parser；批量文件时这会浪费时间。

这不是当前最严重的问题。不要为了性能先重构成复杂缓存。等错误契约修干净后，再考虑 parser table 缓存。否则只是把坏行为缓存得更快。

## 改进方向

1. **先杀掉"带错误成功 AST"。** `parse_errors` 或 lexer errors 非空，统一抛 `VCGParseError`。这是第一刀。
2. **把 lexer 错误纳入结构化错误通道。** logger 只能记录现场，不能决定控制流。非法字符必须让 parse 失败。
3. **重做端口声明数据结构。** ANSI header 应该解析成 declaration group：属性 + 名字列表。用数据结构消掉"第二个端口没方向"这种特殊情况。
4. **统一 parameter header/body 规则。** header 也应该支持 `param_assignment_list`，不要维护两套不一致语法。
5. **明确 Parser 目标。** 如果 VCG 只关心模块头和端口/参数声明，就让预处理器裁剪 body，Parser 不要半吊子解析 assign/instance。半支持比不支持更危险。
6. **最后再处理性能和 API 整理。** yacc table 缓存、`get_module_info()` 去重都可以排后。当前先保证失败会失败。

## 结论

当前 `VerilogParser.py` 的最大问题不是少支持几条 Verilog 语法，而是成功/失败边界不可信。一个 Parser 发现错误还返回 AST，就是在给代码生成器喂脏数据。先修错误契约，再修 ANSI 声明组和 parameter list；其他都是二级问题。
