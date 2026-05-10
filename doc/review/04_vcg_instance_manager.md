# src/vcg_instance_manager.py Linus 风格技术评审

评审日期: 2026-05-10
评审范围: `src/vcg_instance_manager.py`，只读 `CLAUDE.md`、`PROJECT.md`、调用处、Parser/AST 相关契约和现有测试。

## 品味评分

黄牌，凑合。

这个文件的结构比旧版干净：`PortConnection` / `ParameterConnection` 是对的，小函数也没有明显的缩进地狱，异常类型也没有再被一锅端。问题不在代码长得丑，而在它丢掉了 AST 里已经有的关键语义，然后默默生成可能错误的 Verilog。这种 bug 最恶心：不崩，直接污染下游。

## 核心判断

不值得保留现状。必须修两个语义漏洞：

1. `module_name` 是 public API 参数，但当前只用于日志和渲染，不校验解析出来的真实模块名。
2. `ParameterInfo.param_type` 已经区分 `parameter` / `localparam`，但实例化参数覆盖时完全忽略，可能生成非法 parameter override。

其余问题都是小修小补。别搞大重构，先把数据契约用起来。

## Linus 三问

1. 这是真问题吗？

是。`Instance("x.v", "foo", "u_foo")` 是用户直接写在 VCG DSL 里的核心功能。现在如果 `x.v` 里实际模块叫 `bar`，代码会生成 `foo u_foo (...)`，但端口和参数来自 `bar`。这不是格式问题，这是 silent wrong code。

2. 有更简单的方法吗？

有。AST 已经有 `ast.module_name`，参数对象已经有 `param_type`。不用新抽象，不用新 Manager，不用把 Parser 改成多模块索引器。第一刀就是在 InstanceManager 里做校验和过滤。

3. 会破坏什么吗？

会。给 `module_name` 加校验可能破坏那些把它当“输出模块别名”的未文档化用法。但 `doc/MANUAL.md` 把它定义成“模块名称 / 要实例化的模块名称”，不是别名。保持错误行为不是兼容，是继续给用户挖坑。最小破坏方案是先按文档契约校验；如果真需要别名，另加显式参数，别让一个名字承担两个意思。

## 关键洞察

- 数据结构: `VerilogAST` 已经携带模块名，`ParameterInfo` 已经携带参数类型。`InstanceManager` 把这两块语义丢了，只拿 ports/parameters 裸列表渲染。
- 复杂度: 当前不需要重写渲染器。真正的复杂度来自“API 参数”和“AST 事实”没有统一来源。
- 风险点: 这是代码生成器。它生成错 Verilog 时，用户看到的是综合/仿真阶段爆炸，而不是 VCG 在源头告诉他“你实例化错模块了”。

## 问题列表

### P0: `module_name` 没有约束解析结果，能静默生成错误实例

位置: `src/vcg_instance_manager.py:57`, `src/vcg_instance_manager.py:61`, `src/vcg_instance_manager.py:78`, `src/vcg_instance_manager.py:135`, `src/vcg_instance_manager.py:139`

`generate_instance(file_path, module_name, instance_name)` 接收 `module_name`，但解析时只做：

```python
ast = self._parse_verilog_file(file_path)
ports = ast.get_port_info()
parameters = ast.get_parameter_info()
```

然后渲染时直接用传入的 `module_name`：

```python
lines.append(f"{module_name} {instance_name} (")
```

这意味着真实模块名和输出模块名可以完全不一致。例子：

```verilog
module bar(input clk); endmodule
```

调用：

```python
Instance("bar.v", "foo", "u_foo")
```

当前行为会生成 `foo u_foo`，端口却来自 `bar`。如果 `foo` 真实存在但端口不同，这就是更隐蔽的错。

更糟的是，`VerilogPreprocess`/`VerilogParser` 当前流程取的是文件里的第一个 module，不是按 `module_name` 搜索目标 module。`module_name` 在这里给了用户一个假的选择感。

修法：

```python
ast = self._parse_verilog_file(file_path)
actual_module_name = getattr(ast, "module_name", None)
if actual_module_name != module_name:
    raise VCGSyntaxError(
        f"Requested module '{module_name}' but parsed '{actual_module_name}' from {file_path}"
    )
```

如果未来要支持一文件多模块，那是 Parser/Preprocess 的能力扩展，不应该让 InstanceManager 假装已经支持。

### P1: `localparam` 会被当成可 override 参数渲染

位置: `src/vcg_instance_manager.py:111` 到 `src/vcg_instance_manager.py:120`

`VerilogParser` 会把 `parameter` 和 `localparam` 都放进 `ParameterInfo`，并保留 `param_type`。但 InstanceManager 只看名字：

```python
param_value = self.rule_manager.resolve_param_connection(param_name)
if param_value is not None:
    connections.append(ParameterConnection(parameter=param, value=param_value))
```

这会让宽泛规则污染 `localparam`：

```python
ConnectParam("*", "1")
```

遇到：

```verilog
module m #(parameter WIDTH = 8, localparam DEPTH = 16) (...);
```

可能生成：

```verilog
m #(
    .WIDTH              (1),
    .DEPTH              (1)
) u_m (
```

`localparam` 不是给实例化覆盖用的。这个输出不该从生成器里出来。

修法很简单：

```python
if getattr(param, "param_type", "parameter") != "parameter":
    continue
```

如果想让用户知道规则命中了不可覆盖参数，可以加 debug 日志。别把它塞进 `#(...)`。

### P2: public 输入没有基本 Verilog identifier 校验

位置: `src/vcg_instance_manager.py:57`, `src/vcg_instance_manager.py:135`, `src/vcg_instance_manager.py:137`, `src/vcg_instance_manager.py:139`

`module_name` 和 `instance_name` 原样进入输出。空字符串、带空格、带换行、带分号，都能生成明显非法甚至结构被打断的 Verilog。

这不是安全问题，VCG DSL 本来就是受信 Python。但这是糟糕的错误定位：用户拼错实例名，VCG 不报，后面 Verilog 工具报一坨语法错。

修法：

按项目 Parser 当前支持的 ID 语法校验即可：

```python
^[A-Za-z_][A-Za-z0-9_$]*$
```

如果将来要支持 escaped identifier，再显式扩展。不要现在就假装任意字符串都是合法模块名。

### P2: `set_alignment()` 接受会让渲染器崩掉的值

位置: `src/vcg_instance_manager.py:149`, `src/vcg_instance_manager.py:163`, `src/vcg_instance_manager.py:170`, `src/vcg_instance_manager.py:197`

`set_alignment(self, align: int)` 直接赋值：

```python
self._ALIGN = align
```

然后用于动态 format width：

```python
f".{connection.parameter.name:<{self._ALIGN}}({connection.value})"
```

负数会触发格式化异常，非整数语义也不清楚。这个 setter 是 public API，就别让它把对象设置成半坏状态。

修法：

```python
if not isinstance(align, int) or align < 1:
    raise ValueError("alignment must be a positive integer")
```

注意兼容性：如果已有测试或用户依赖 `0`，先明确记录历史行为，再决定是否收紧。不要悄悄接受坏状态。

### P3: 空端口模块输出可读性差，但不是致命问题

位置: `src/vcg_instance_manager.py:134` 到 `src/vcg_instance_manager.py:143`

无端口模块当前输出类似：

```verilog
empty_module u_empty (
);
```

这大概率是合法的，但不如：

```verilog
empty_module u_empty ();
```

这不是 P0，不要为了它重写渲染器。等前两个语义 bug 修完，再顺手处理。

## 改进方向

1. 先把 AST 事实变成契约：`ast.module_name` 必须和 `module_name` 一致。不一致就抛 VCG 自家异常，别生成假实例。
2. 参数覆盖只允许 `param_type == "parameter"`。`localparam` 直接跳过，必要时 debug 记录。
3. 给 `module_name`、`instance_name`、`alignment` 做最小输入校验，让错误在 VCG 层暴露。
4. 保留现有 `PortConnection` / `ParameterConnection` 数据结构。它们是这个文件里品味正确的部分，别为了“重构”把它拆烂。
5. 多模块文件支持不要在 InstanceManager 里硬拼。要么 Parser 支持按模块名选择 AST，要么 InstanceManager 明确只接受单模块文件并校验模块名。

## 结论

这个文件不需要大手术，但必须补上语义检查。当前最坏的问题不是代码复杂，而是它把用户明确给出的模块名当成装饰，然后输出看起来正常、实际可能完全错误的 Verilog。代码生成器最不能容忍这种沉默失败。
