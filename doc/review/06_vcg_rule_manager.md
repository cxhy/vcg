# src/vcg_rule_manager.py Linus 风格技术评审

> 评审日期: 2026-05-10
> 评审范围: `src/vcg_rule_manager.py`
> 约束: 只评审本文件；参考 `CLAUDE.md`、`PROJECT.md`、调用处与现有测试；不修改源码。

## 品味评分

🟡 凑合。

这不是垃圾。旧版本里最糟糕的 `eval` 已经没了，规则也已经换成了 `frozen dataclass`，这是正确方向。但这个文件仍然把三件不同的事搅在一个字符串替换锅里：规则匹配、Verilog 表达式、注释保留。结果是一些看起来很聪明的边界处理，实际会生成错误硬件语义。

## 核心判断

❌ 当前实现能跑常见 demo，但还不能算可靠的规则引擎。真正的问题不是函数多，也不是 456 行，而是数据模型仍然不干净：`*` 同时是通配符、目标占位符、Verilog 乘法符号；注释用普通字符串占位符塞回用户文本；非法 DSL 被 warning 后吞掉。硬件代码生成器里这种“猜用户意思”的行为很危险。

## Linus 三问

1. **这是个真问题吗？** 是。规则引擎是 VCG 的核心路径，`Instance()` 和 `WiresDef()` 都依赖它输出最终 Verilog。
2. **有更简单的方法吗？** 有。把 pattern 编译成结构化 token，不要在最终字符串上盲目 `replace('*', ...)`；注释也别用用户可碰撞的文本占位符。
3. **会破坏什么？** 会触碰现有 DSL 的兼容性，尤其是裸 `*` 占位和非法函数 fallback。必须保留旧语法，但可以新增内部 token 化实现，外部行为只修掉明显 bug。

## 关键洞察

- **数据结构**: 文件表面上有 `SignalRule` / `ParamRule` / `WireRule` 三个 dataclass，但 `VCGRuleManager.rules` 仍是 `dict[str, list]` (`src/vcg_rule_manager.py:66-76`)。类型信息在入口处又丢了，后面靠字符串 key 找回。
- **复杂度**: 最复杂的不是行数，而是 `_apply_pattern_substitution()` (`src/vcg_rule_manager.py:235-254`) 这个函数承担了太多语义：匹配组、函数表达式、裸星号替换。它不知道自己处理的是信号名还是 Verilog 表达式。
- **风险点**: 生成 Verilog 时，错误不是“程序崩了”这么好发现，而是输出合法但语义错误的代码。`1 /* comment */` 没扩成全 1、`WIDTH*2` 被替换坏，这类 bug 会直接进入硬件连接。

## 问题列表

### P0: 带注释的 `1` 字面量不会按端口宽度扩展，可能生成错误硬件连接

位置:
- `src/vcg_rule_manager.py:84`
- `src/vcg_rule_manager.py:143-147`
- `src/vcg_rule_manager.py:229-233`
- `src/vcg_rule_manager.py:416-423`

`add_signal_rule()` 先把 `/* ... */` 替换成 `__COMMENT_0__`。后面 `_handle_literal_value_if_needed()` 只认 `value.strip()` 等于 `"0"` 或 `"1"`。所以：

```python
Connect("mask", "1 /* all ones */")
```

对 8 位端口不会生成 `8'b11111111 /* all ones */`，而是保留成 `1 /* all ones */`。这不是格式问题。多位 bus 上 unsized `1` 的语义不是“所有 bit 为 1”。注释功能和字面量扩展功能都是公开能力，组合起来就坏，这就是核心路径 bug。

修复方向：注释抽取后要让 literal 判断看到真实表达式，而不是占位符污染后的字符串。最简单是把目标拆成 `(body, trailing_comments)`，先对 body 做 literal 扩展，再拼回 comments。

### P1: `*` 被同时当作通配符和 Verilog 乘法符号，wire expression 会被破坏

位置:
- `src/vcg_rule_manager.py:218-227`
- `src/vcg_rule_manager.py:235-254`

`_resolve_wire_expression()` 对 `rule.expression` 也调用 `_apply_pattern_substitution()`。只要 source pattern 有通配符，目标里的第一个裸 `*` 都会被捕获组替换。

典型例子：

```python
WiresRule("*", "w_*", expression="WIDTH*2")
```

端口 `data` 会把表达式变成类似 `WIDTHdata2`。这是把 Verilog 表达式当成 pattern 文本处理。函数输出里如果产生 `*`，也会被后续裸星替换二次污染。

修复方向：不要在最终字符串上全局找裸 `*`。编译 target pattern，只有 pattern token 里的占位符能替换；expression 里建议只允许显式 `${*}` / `${*0}` 引用捕获组，普通 `*` 永远保留为 Verilog 运算符。

### P1: 注释占位符使用普通用户字符串，合法信号名会被误替换

位置:
- `src/vcg_rule_manager.py:404-423`

占位符是 `__COMMENT_0__`。这看起来特殊，但它仍然是合法 Verilog identifier 形态。用户目标里本来就可能有这个名字：

```python
Connect("*", "__COMMENT_0__ /* note */")
```

恢复注释时会把用户写的 `__COMMENT_0__` 也替换掉。这个设计味道很差：内部哨兵泄漏进用户命名空间。

修复方向：不要用文本哨兵。用分段结构保存 literal/comment，或者至少生成不可由合法 Verilog identifier 表达的 sentinel，并只替换由本轮抽取产生的位置，不扫整段 result。

### P1: 无效函数表达式被吞掉，错误配置变成看似正常的连接

位置:
- `src/vcg_rule_manager.py:271-284`
- `src/vcg_rule_manager.py:354-365`

`_execute_function_call()` 捕获 `IndexError` / `TypeError` / `ValueError` 后回退到第一个捕获组。结果是这些明显错误都不会失败：

```python
${unknown(*)}
${upper(*9)}
${replace(*, a)}
```

硬件生成器不应该靠 warning 维持“继续跑”。用户写错 DSL，最好在生成阶段失败；至少要有 strict mode。现在的行为会把错误规则悄悄变成另一个合法连接。

兼容性注意：现有测试把 invalid function fallback 当成预期，不能直接硬切。应该先把 fallback 限定到历史兼容路径，新增严格校验入口，并在文档里标记旧行为 deprecated。

### P2: `port_direction` 不校验，拼写错误静默变成永不匹配规则

位置:
- `src/vcg_rule_manager.py:78-90`
- `src/vcg_rule_manager.py:209-216`

`add_signal_rule()` 只做 `.lower()`，不验证只能是 `input` / `output` / `inout`。`Connect("*", "i_*", "inpurt")` 会注册成功，然后对真实端口永远不匹配。更糟的是，`port.direction is None` 时 `_check_port_direction_match()` 返回 `True`，错误方向还能匹配未知方向端口。

修复方向：入口处规范化并校验方向。未知方向是否允许匹配，必须变成明确策略，不要藏在 helper 里。

### P2: 规则集合外层仍是弱类型 dict，dataclass 的收益被打折

位置:
- `src/vcg_rule_manager.py:66-76`
- `src/vcg_rule_manager.py:137-193`
- `src/vcg_rule_manager.py:195-200`

当前写法：

```python
self.rules['signal_rules']
self.rules['param_rules']
self.rules['wire_rules']
```

这比旧 dict rule 好，但还没干净。三类规则已经是不同类型，就应该是三个明确字段：

```python
self.signal_rules: list[SignalRule]
self.param_rules: list[ParamRule]
self.wire_rules: list[WireRule]
```

现在外层 dict 让类型检查、补全、维护都变差，而且任何外部代码都能把 `self.rules['signal_rules']` 塞成错误类型。

## 改进方向

1. **先修语义 bug**：literal 扩展必须在注释恢复前对真实 body 生效；wire expression 里的乘法 `*` 不能被当作占位符。
2. **把 pattern 编译成 token**：支持旧的裸 `*` 语法，但内部表达为 `Literal` / `GroupRef` / `FunctionCall`，不要再对最终字符串做盲替换。
3. **注释改成结构化片段**：别用 `__COMMENT_N__` 这种用户可碰撞字符串。
4. **入口校验**：`port_direction`、函数名、函数参数数量、group index 都应该在规则添加或应用时给出明确错误，不要 warning 后继续猜。
5. **拆掉外层 rules dict**：三个 list 字段足够，`get_rules_summary()` 也不会因此变复杂。
6. **补测试但不要固化坏行为**：新增覆盖 `Connect("x", "1 /* comment */")`、`WiresRule("*", "w_*", expression="WIDTH*2")`、占位符碰撞、非法 group index。现有 invalid fallback 测试需要标注为兼容债。

## 总结

这个文件已经从“危险的字符串执行器”进化成了“能跑的字符串规则器”，但还没到“可靠的代码生成核心”。核心改法不是继续加 if，而是把用户文本拆成结构化数据。只要继续让 `*`、注释、函数表达式在同一条字符串替换流水线上互相踩，后面还会长出同类 bug。
