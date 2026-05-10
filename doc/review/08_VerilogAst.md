# Linus 风格技术评审：src/VerilogAst.py

## 品味评分

黄牌，6/10。

这份代码比旧版本干净不少：`frozen=True`、`add_parameter_info()`、`Builder.build()` 不再戳 manager 私有字段，这些是正确方向。但它还没到好品味。核心问题是 AST 层把"数据模型"和"字符串补丁"混在一起，尤其是宽度表达式计算：看起来聪明，实际会静默生成错误结果。

## 核心判断

值得修，但不值得大拆重写。

真正该先修的是 `ExpressionCalculator`，因为它会把合法 Verilog 表达式算错，而这个 `width` 会被实例化、连线规则和 wire 生成继续消费。数据结构层的 `PortDeclaration -> PortFactory -> PortInfo` 和 manager 包装类是复杂度债务，不是今天的致命 bug。先修正确性，再谈瘦身。

## Linus 三问

1. 这是个真问题还是臆想出来的？
   是真问题。`ExpressionCalculator().parse_width_expression("$clog2(DEPTH)+D0")` 当前会得到 `2*$clog2(DEPTH)`，合法参数名 `D0` 被 `$clog2(...)` 占位符吞了。

2. 有更简单的方法吗？
   有。别用会和用户标识符碰撞的字符串占位符，别把 SymPy 整数转成 float 再转回 int。AST 应该保存结构化数据，字符串只应该在最后渲染时出现。

3. 会破坏什么吗？
   修宽度计算不应该破坏 userspace，只会修正错误结果。收紧 `add_port(**kwargs)` / `add_parameter(**kwargs)` 的未知字段处理会破坏依赖"静默忽略 typo"的调用方，所以要先告警、再收紧。

## 关键洞察

- 数据结构：`PortInfo.width` 同时返回 `int`、`float`、`str` 和魔法字符串 `"array"`。这不是类型系统，这是让下游猜谜。
- 复杂度：`ExpressionCalculator` 用正则把 Verilog 系统函数替换成 `D0`、`D1`，再交给 SymPy，最后用字符串替换拼回来。这里有两套语法系统，边界非常脆。
- 风险点：`PortInfo.width` 是下游规则和 wire 宽度生成的入口。一旦 AST 层算错，后面只能生成错误 Verilog，而且通常不会报错。

## 按严重度排序的问题

### P1：`$` 系统函数占位符会污染合法标识符

位置：`src/VerilogAst.py:96-107`，`src/VerilogAst.py:114-118`

`_handle_dollar_funcs()` 把 `$clog2(DEPTH)` 替换成 `D0`，然后 `_format_result()` 对最终字符串做无边界的 `replace()`。这有两个直接后果：

- 表达式里本来就有参数 `D0` 时，占位符和用户符号撞车。
- 表达式里有 `D01` 时，`D0` 会被替换成 `$clog2(DEPTH)` 的前缀，字符串被撕烂。

实测当前行为：

```text
$clog2(DEPTH)+D0  -> 2*$clog2(DEPTH)
$clog2(DEPTH)+D01 -> $clog2(DEPTH)+$clog2(DEPTH)1
```

这不是边角问题。`D0`、`D1` 是完全合法且常见的 Verilog 参数或信号名。AST 层不能把用户标识符当内部临时变量用。

修法：使用不会进入用户命名空间的 SymPy `Dummy`/私有 symbol 映射，回填时按精确 token 回填。更简单的保守方案是：表达式包含 Verilog 系统函数时不要尝试跨系统函数化简，只做明确安全的 `X-1:0 -> X` 规则。

### P1：大整数表达式会被 float 转换截断精度

位置：`src/VerilogAst.py:109-112`

`_format_result()` 对所有 numeric result 都先 `float(result)`，再判断是否能转 `int`。这对硬件宽度表达式是坏主意。Python/SymPy 本来能精确表示大整数，这里主动把它降级成 IEEE float。

实测当前行为：

```text
ExpressionCalculator().parse_width_expression("2**70+1")
-> 1180591620717411303424
```

正确结果应该是 `1180591620717411303425`。少 1。硬件位宽少 1 不是"显示误差"，是直接生成错误结构。

修法：先判断 `result.is_Integer`，直接 `int(result)`。只有明确需要小数时才转 float；对非整数有理数，宁可返回字符串，也不要静默损失精度。

### P2：数组端口的 `width == "array"` 是字符串魔法，不是 AST

位置：`src/VerilogAst.py:155-177`，`src/VerilogAst.py:203-214`

`port_type` 可以返回 `ARRAY_2D` / `ARRAY_3D`，`range_string` 也会拼数组维度，但 `width` 对所有数组直接返回 `"array"`。这把结构化信息丢掉了。调用方如果把 `width` 当宽度表达式处理，很容易得到类似 `[array-1:0]` 的垃圾输出。

如果数组还没真正支持，就不要在 AST 里假装支持。如果要支持，就把 packed range、unpacked dimensions、element width 分开存。`"array"` 这种哨兵字符串只会把类型错误推迟到生成 Verilog 时爆炸。

### P2：`frozen=True` 只是表面冻结，`array_dims` 仍可原地修改

位置：`src/VerilogAst.py:122-152`，`src/VerilogAst.py:243-250`

`PortDeclaration` 和 `PortInfo` 是 frozen dataclass，但 `array_dims` 是 `List[str]`。字段不能重新赋值，不代表列表不能 `append()`。`PortFactory.to_info()` 只在 build 时 copy 一次，生成后的 `PortInfo.array_dims` 仍然是可变对象。

这违反项目自己写下的不可变 AST 原则。更糟的是，`port_type` 和 `range_string` 都是动态 property，外部改了 `array_dims`，同一个 AST 对象的语义就变了。

修法：内部用 tuple。为了兼容构造时传 list，可以在 `__post_init__` 中转换，或者新增只读属性返回 tuple。不要靠 docstring 要求调用方"请勿 mutate"，那不是工程约束。

### P2：Builder 静默忽略未知字段，会把 typo 变成合法 AST

位置：`src/VerilogAst.py:329-338`，`src/VerilogAst.py:341-352`

`add_port()` 过滤掉所有非 dataclass 字段，`add_parameter()` 只读固定 key，未知 kwargs 全部静默消失。这个 API 在 parser 层使用，静默吞错就是坏品味：调用方写错 `msb` / `msb_expr`，结果不是失败，而是生成一个缺字段的端口。

兼容性上可以理解历史包袱，但核心构建器不应该无声接受垃圾输入。

修法：短期在未知字段出现时打 warning。中期给 parser 内部用明确参数签名的私有方法，公共 `**kwargs` 只作为兼容层保留。长期把 `**kwargs` 从核心路径拿掉。

### P3：`PortDeclaration -> PortFactory -> PortInfo` 仍然是概念重复

位置：`src/VerilogAst.py:122-153`，`src/VerilogAst.py:227-251`

`PortDeclaration` 和 `PortInfo` 字段基本相同，`PortFactory.to_info()` 主要是在复制字段并补一个默认 `net_type="wire"`。这不是抽象，这是搬运。

我不建议现在硬删，因为项目文档已经把这些名字当公共 API 保留下来了。但从长期设计看，一个 `PortInfo` 加上"是否 complete"已经足够。以后做 breaking/refactor 分支时，应该把这个中间层干掉。

### P3：Manager 包装类仍然是对 `dict` 的薄封装

位置：`src/VerilogAst.py:256-309`

`_OrderedRegistry` 维护 `_items` 加 `_order`，但 Python 3.7+ 的 `dict` 已经保序。再加上 `_parameters` / `_parameter_order` 这种 live alias，内部结构被测试和外部兼容性钉死了。

这不是当前最该修的点，但它说明 AST 的数据所有权还没理顺。真正的模型应该是：AST 拥有有序的 parameters 和 ports，manager 不要成为第二套状态命名。

## 改进方向

1. 先修 `ExpressionCalculator` 的两个 P1：占位符必须 token-safe，大整数必须精确。
2. 给 `PortInfo.width` 定义清楚的返回契约。不要再让 `"array"` 混在宽度表达式里。
3. 把 `array_dims` 从 list 收敛成不可变序列。AST 对象建完后语义不能被外部 append 改掉。
4. 对 Builder 未知 kwargs 做显式告警或错误。静默忽略只适合兼容 shim，不适合 parser 核心路径。
5. 下一轮重构再处理 `PortDeclaration` / `PortFactory` / manager 薄封装。别为了瘦身先动公共 API，先把错误结果修掉。

最终结论：这份文件现在是"能用但脆"。真正危险的是它在 AST 层制造了看似合理的错误宽度。先把宽度计算变成可信的，再谈架构洁癖。
