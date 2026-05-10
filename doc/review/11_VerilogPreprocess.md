# VerilogPreprocess.py Linus 风格技术评审

评审范围: `src/VerilogPreprocess.py`

只读上下文: `CLAUDE.md`, `PROJECT.md`, `src/VerilogParser.py`, `src/vcg_instance_manager.py`, `src/vcg_wires_manager.py`, `tests/test_VerilogPreprocess.py`, `tests/test_VerilogParser.py`, TASK-03 归档交付文档。

## 品味评分

红色: 垃圾边缘。

这不是说每一行都烂。`ConditionalFrame` 比旧的 dict 栈强，异常类型也比以前干净。但核心数据流还是错的: 它把 Verilog 源文件当成几段字符串先裁掉、再补救。预处理器最不能做的事就是先丢上下文。这里正是这么干的。

## 核心判断

值得修，而且必须修。当前文件会让合法 Verilog 在三个真实场景下坏掉:

1. module 前的 ``define`` / include guard / 条件包裹会被先裁掉，后续条件编译拿不到上下文。
2. 多 module 文件永远取第一个 module，下游却用用户传入的 `module_name` 渲染实例名，可能生成名字正确、端口错误的代码。
3. "预处理"不展开宏值，`WIDTH=32` 这种用户输入对参数值和位宽没有实质作用。

这不是风格问题。这会污染 AST，然后 `Instance()` / `WiresDef()` 生成错误 Verilog。

## Linus 三问

1. 这是个真问题吗？
   是。常见 Verilog 文件有 include guard、文件头宏、多 module 文件。当前实现不是“不支持高级语法”，而是会把常规工程结构解析错。

2. 有更简单的方法吗？
   有。不要先 `remove_pre_module_content()`。先对整文件做条件编译扫描，保留原始行号和 active 状态；再按目标 module 抽取声明区。数据结构对了，特殊情况会少一半。

3. 会破坏什么吗？
   修复会改变部分旧行为: 以前错误通过或错误失败的文件会变成正确结果。公开 API 可以不破坏，但必须把 `module_name` 这类目标选择能力传到 Parser/Preprocess 层，或明确声明永远只解析第一个 module。

## 关键洞察

- 数据结构: 当前核心数据是一个被反复裁剪的 `str`。正确核心数据应该是带 `raw_line`, `visible_code`, `line_no`, `active` 的行流，或者直接是 lexer token 流。
- 复杂度: `in_module`, `header_complete`, `declaration`, `header_visible_lines`, `in_block_comment` 这些状态是在弥补错误抽象。真正的阶段只有: 条件过滤、module 选择、声明抽取。
- 风险点: 最危险的不是抛异常，而是静默产生错误端口集合。下游会用这个错误 AST 生成看起来很整齐的错误代码。

## 严重问题

### P0-1 预处理顺序反了，module 前条件上下文被丢掉

位置: `src/VerilogPreprocess.py:327-334`, `src/VerilogPreprocess.py:94-104`, `src/VerilogPreprocess.py:177-195`

`preprocess_string()` 先调用 `remove_pre_module_content()`，再调用 `process_conditional_compilation()`。这直接丢掉 module 前所有预处理指令。

最小复现:

```verilog
`define ENABLE
module m;
`ifdef ENABLE
  input en;
`endif
endmodule
```

当前输出会丢掉 `input en;`，因为 ``define ENABLE`` 在条件编译前已经被裁掉。

include guard 更糟:

```verilog
`ifndef M_V
`define M_V
module m;
  input clk;
endmodule
`endif
```

当前流程从 `module m;` 开始处理，最后碰到孤立的 ``endif``，抛 `VCGParseError`。这是合法 Verilog 的常规写法，不是什么边角语法。

根因很简单: 预处理器先删除了预处理器需要的输入。这个顺序不能靠再加一个 if 修。

### P0-2 文件级设计硬编码“第一个 module”，会生成错误端口集合

位置: `src/VerilogPreprocess.py:94-104`, `src/VerilogPreprocess.py:106-136`, `src/VerilogPreprocess.py:346-358`

`_find_module_line()` 找第一个 `module` 就返回，`extract_module_ports_section()` 到第一个 `endmodule` 就结束。这个文件没有任何目标 module 概念。

下游 `Instance(file_path, module_name, instance_name)` 和 `WiresDef(file_path, module_name, ...)` 都暴露了 `module_name`，但这个预处理器永远取文件里的第一个 module。结果就是:

- 文件第一个 module 是 helper，用户请求 top。
- AST 端口来自 helper。
- 渲染出来的实例名却是 top。

这比直接失败更坏。用户会得到语法上可能正确、语义上完全错误的 Verilog。

### P1-1 `macros` 的值基本没用，所谓宏展开是假的

位置: `src/VerilogPreprocess.py:43-78`, `src/VerilogPreprocess.py:273-292`

`macros` 被解析成 `dict[str, str]`，``define NAME value`` 也保存了 value。但后续只在 `ifdef` / `ifndef` / `elsif` 里检查 key 是否存在，从不替换 parser 可见文本。

所以这些输入实际不会按用户直觉工作:

```verilog
module m #(parameter WIDTH = `DATA_WIDTH)(
  input [`DATA_WIDTH-1:0] data
);
endmodule
```

传入 `{"DATA_WIDTH": "32"}` 后，参数值和位宽仍然带反引号宏名。测试里 `assert '8' in param_value or 'WIDTH' in param_value` 这种断言把问题掩盖了。要么实现最小 object-like macro expansion，要么把文档和命名改成“只支持条件编译宏存在性判断”。现在的接口在撒谎。

### P1-2 注释剥离器不懂字符串，会破坏合法参数

位置: `src/VerilogPreprocess.py:294-313`, `src/VerilogPreprocess.py:364-373`

`_code_visible_to_preprocessor()` 看到 `//` 就截断，看到 `/*` 就进入块注释。它没有字符串状态。

合法 Verilog:

```verilog
module m;
  parameter URL = "http://example";
  parameter TEXT = "a;b";
  input clk;
endmodule
```

`http://` 会被当成行注释开头，字符串里的 `;` 会被 `_line_ends_statement()` 当成语句结束。PLY lexer 明明已经支持 `STRING_LITERAL`，这里却在 lexer 前用手写扫描器损坏输入。这就是重复造半个 lexer 的代价。

### P1-3 行号诊断被裁剪流程破坏

位置: `src/VerilogPreprocess.py:177-193`, `src/VerilogPreprocess.py:327-331`

条件编译的 `line_no` 是在裁剪后的内容上重新从 1 开始数。真实文件第 200 行的 orphan/unterminated 可能被报成第 4 行。解析器错误最需要准确位置，这里把定位信息主动丢了。

如果用带原始行号的行流，这个问题自然消失。

### P2-1 attribute 保留是半截修复

位置: `src/VerilogPreprocess.py:94-104`, `src/VerilogPreprocess.py:106-136`, `src/VerilogPreprocess.py:354-355`

`remove_pre_module_content()` 会把紧邻 module 前一行的 attribute 留下来，但 `extract_module_ports_section()` 在 `in_module` 之前跳过所有非 module 行，所以最终 `preprocess_string()` 输出不会保留 attribute。

当前 AST 只关心端口和参数，这不是立即 P0。但代码看起来像“保留 attribute”，实际最终输出又丢掉 attribute。这种半承诺会误导后续维护者。

### P2-2 module 识别过窄，合法写法会漏掉

位置: `src/VerilogPreprocess.py:357-358`

`_is_module_start()` 只接受 `module\s+\w+\b`。它不接受同一行 attribute:

```verilog
(* keep_hierarchy = "yes" *) module m(input clk);
endmodule
```

也不接受 escaped identifier。项目可以暂时不支持 escaped identifier，但同一行 attribute 是常见写法。更关键的是，这又暴露了同一个问题: 用正则匹配语言结构。

### P2-3 有死 helper 和松散 API 边角

位置: `src/VerilogPreprocess.py:340-362`

`_strip_line_comment()` 当前未被使用。`clear_macros()` 没有返回类型标注。``ifdef`` 没有宏名时被当成 false，而不是语法错误。这些单独都不致命，但它们说明这个文件没有明确的输入契约边界。

## 改进方向

1. 先改数据流，不要继续补 if。
   `preprocess_string()` 应该先在整文件上跑条件编译扫描，得到带原始行号的 active 行流；然后选择目标 module；最后抽取 header/body declarations。

2. 把 module 选择变成显式数据。
   预处理器至少要能按 module name 找 module range。兼容旧 API 可以默认第一个 module，但 `VerilogParser` / manager 路径不能继续假装 `module_name` 被使用了。

3. 停止用无状态正则剥注释。
   写一个小 scanner，跟踪 `CODE`, `LINE_COMMENT`, `BLOCK_COMMENT`, `STRING` 四种状态。分号、directive、module 起点只在 `CODE` 状态有效。

4. 对宏能力做诚实取舍。
   如果目标只是条件编译，文档删掉“宏展开”，`macros` value 不要制造假期待。如果要支持 CLI `WIDTH=32`，先实现最小 object-like macro expansion，不碰函数式宏和 include。

5. 测试补真实失败样例。
   必加: module 前 ``define``、include guard、多 module 文件请求第二个 module、字符串参数含 `//` 和 `;`、同一行 attribute + module。现在的测试太容易让伪预处理器过关。

结论: 当前版本比旧版本少了一些明显炸点，但核心抽象还没修。预处理器的第一原则是保留足够上下文再决定丢什么；这个文件反过来做，所以继续堆 helper 只会制造更多特殊情况。
