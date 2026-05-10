# VerilogParser.py Review

> 评审日期: 2026-04-21
> 评审人: Linus (代理)
> 文件路径: src/VerilogParser.py
> 文件规模: 543 行

## 品味评分
🔴 垃圾

## 核心判断

这文件已经从 975 行砍到 540 行，但**它砍掉的是行数，不是问题**。

三件事让我下这个结论：

1. **`parse_file` / `parse_string` 用 `except Exception: return None` 把所有错误吞成 `None`**（`src/VerilogParser.py:78-89`、`src/VerilogParser.py:101-128`）。`PROJECT.md` 决策 1 白纸黑字写着"`except Exception` 不能吞掉 `ValueError`、`FileNotFoundError` 等有明确语义的异常"，分支自己刚为这个修过 8 个测试。结果项目入口的两个公共方法直接犯同样的错。这不是疏忽，这是架构纪律没有落到代码里。

2. **`module_item_assignment` / `module_item_always` / `module_item_instance` 三个 yacc 规则消耗 token 但什么 AST 都不建**（`src/VerilogParser.py:406-415`）。它们存在的唯一目的是让 `module_item_list` 不报错。这不是"做一件事"，这是用语法来吞错——就为了不让 `assign`/`always`/instance 出现时整个解析挂掉。一个真正的 parser 要么解析它要么明确不支持，不能装作解析。更糟的是：`p_module_item_always` 把 always 块的 sensitivity list 解释成 `expression`、把 body 解释成 `expression_list`，这是**错误的语法**——它会接受垃圾输入而沉默。一旦有人误以为 parser 真的看到了 always 块，下游会出隐藏数据问题。

3. **`p_module_declaration` 在 yacc 动作里调用 `self.builder.build()`**（`src/VerilogParser.py:190`）。yacc 动作应该构造数据，不应该执行"完成阶段"。这个 build() 抛 `VerilogASTError` 时被吞掉，并构造一个空 `VerilogAST(module_name)` 顶上去（`src/VerilogParser.py:199`、`:202`、`:217`、`:220`、`:222`），调用方看到的就是"模块名对、端口为空"——一个看起来成功的失败。这是教科书级"silent corruption"。

加分项：precedence 表写得规整、错误恢复规则覆盖面不窄、port_identifier_list/param_assignment_list 用了正经的左递归——但这些救不了上面三件事。

## 关键洞察

- **数据结构**: 唯一的状态是 `self.builder` / `self.ast` / `self.parse_errors` 三块**可变实例属性**，通过 yacc 动作的副作用累积。这违反 CLAUDE.md "不可变性"原则——但更要命的是：解析中途出错时，三块状态的一致性没有任何保证。`p_module_declaration_error` 还能"用残缺 builder 强行 build"（`src/VerilogParser.py:211-220`），这就是依赖 builder 内部容错。一旦 builder 重构，这里就坏。
- **复杂度**: 表达式语法树**不是 AST，是字符串拼接**（`src/VerilogParser.py:438`、`:445`、`:449`、`:453`、`:480`、`:489`、`:505`、`:510`、`:514`）。下游 `ExpressionCalculator` 又得用 sympy 重新解析这些字符串。Parser 解析→拼回字符串→sympy 再解析，这是把 AST 拍扁又重建，纯粹的损耗。`f"{p[1]}{p[2]}{p[3]}"` 还会丢失运算符两侧的空格信息（`a-b` 和 `a - b` 拼出来一样，但 `1 -1` 这种语义会变），sympy 的容错救了你，但这是脆的。
- **风险点**: 最大的破坏性风险是 `parse_file/parse_string` 返回 `None`。所有调用方（`vcg_instance_manager.py`、`vcg_wires_manager.py`）现在不得不写 `if ast is None:` 分支来兜底。这个 `None` 沿调用链向上传播，最终在某个位置被当成"模块没有端口"处理——故障会在远离 root cause 的地方爆。

## 致命问题（按严重度）

### P0
- **`parse_file` 把 `FileNotFoundError` 和所有异常都吞成 `None`**（`src/VerilogParser.py:84-89`）。`FileNotFoundError` 应该 `raise VCGFileError(...) from e`，`UnicodeDecodeError` 应该独立分支，`PermissionError` 同理。当前实现直接违反 PROJECT.md 决策 1。修法：
    ```python
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            verilog_code = f.read()
    except FileNotFoundError as e:
        raise VCGFileError(f"Verilog file not found: {filepath}") from e
    except UnicodeDecodeError as e:
        raise VCGFileError(f"Encoding error in {filepath}: {e}") from e
    return self.parse_string(verilog_code)
    ```
- **`parse_string` 同样问题 + 隐藏数据损坏**（`src/VerilogParser.py:126-128`）。preprocessor / lexer / yacc 内部抛的任何异常被吞成 `None`，调用方无从区分"语法错误"、"宏展开失败"、"文件没有 module 关键字"。必须按类型 re-raise，至少 `raise VCGParseError(...) from e`。
- **`p_module_declaration` 在异常路径构造空 `VerilogAST` 冒充成功**（`src/VerilogParser.py:199`、`:202`）。调用方拿到的是"模块名正确、端口列表空"——看起来是合法模块，实际是 build 失败。下游 `vcg_instance_manager` 会愉快地生成一个零端口的例化。**必须**把异常重新抛出，不要返回伪造的 AST。
- **`p_module_item_always` 语法错误地接受 always 块**（`src/VerilogParser.py:409-411`）。`ALWAYS expression BEGIN expression_list END` 不是 Verilog 的 always 语法——sensitivity list 不是 expression、always body 不是逗号分隔的 expression。这个规则会**把不合法的代码当合法吃下去**且不报错。建议：要么删掉（让 parser 在 always 处明确报错），要么把 always block 的内容用一个"opaque token sequence"消费规则吞掉直到匹配的 `END`。当前写法是最坏的两者结合。

### P1
- **`module_item_assignment` / `module_item_instance` 同样吞 token 不建 AST**（`src/VerilogParser.py:406-408`、`:413-415`）。这违反"做一件事"——名字叫 `_assignment`/`_instance` 但什么也不做。要么改名为 `_skip_assignment` 表明意图，要么真的解析它们。当前是"语法层面的死代码"，让以后维护的人误以为这里真的处理了 assign/instance。
- **`module_item_list` 用 `module_item_list error SEMICOLON` 做错误恢复**（`src/VerilogParser.py:338-343`），但 `error` 不会被记录到 `self.parse_errors`——只有 `p_error` 被触发时才会记录。所以错误恢复**默默吞掉了一段输入**而 parse_errors 列表为空。这是 PLY 错误恢复的经典坑：error 规则匹配本身不调用 p_error。修法：在动作里显式 `self.parse_errors.append(...)`。
- **`p_opt_packed_dimension` 在错误分支用 `p.lineno(1)`，但 `p[1]` 是 `LBRACKET`**（`src/VerilogParser.py:329`）。这能拿到行号是因为 PLY 给所有 token 都附了 lineno，但表达**意图错位**——实际想要的是"出错的位置"，应该用 `p.lineno(2)`（error token 的位置）。其他 `_error` 规则同样问题：`p_param_assignment_error:266` 报的是 `EQUALS` 之前那个 ID 的行（也行，但语义模糊），`p_primary_bit_select_error:484` / `p_primary_part_select_error:493` / `p_concatenation_error:518` / `p_port_declaration_error:306` 一致问题。统一改用 `error` token 自身的位置或最后一个有效 token 的位置，并在 message 里写明"near"。
- **`p_error` 调用 `self.parser.errok()` 然后什么都不返回**（`src/VerilogParser.py:533-538`）。`errok()` 告诉 yacc"我处理好了，继续"，但同时**没有 discard 当前 token、也没有 lookahead 推进**。在很多语法里这会导致 yacc 在同一个错误 token 上反复触发——典型的死循环风险。正确做法：要么 `self.parser.errok()` + `self.parser.token()` 跳过一个 token，要么完全靠 `error` 规则恢复，不要两者混用。
- **`unused import: setup_vcg_logging`**（`src/VerilogParser.py:26`）。这就是 ruff 一行就能查出的低级垃圾，过 lint 都过不去。
- **`p_opt_port_list` 没有 error 恢复**（`src/VerilogParser.py:269-273`），但 `p_opt_parameter_list` 有（`:230-234`）。两者形态对称，错误恢复策略却不对称——一定是漏写。port list 写错的概率比 parameter list 高得多。

### P2
- **`get_module_info` 在 ast 为 None 时返回空 dict 而不是 None**（`src/VerilogParser.py:152-158`）。看起来"友好"，实际制造特殊情况——调用方现在要区分"返回的 dict 是真的没有端口"还是"parse 失败假装空 dict"。要么 raise，要么返回 None，**不要返回看起来像合法值的伪数据**。
- **`p_module_item_declaration_param` 调用 `add_parameter`，但 V2001 header 已经走 `p_parameter_declaration` 也调用 `add_parameter`**（`src/VerilogParser.py:382-387` vs `:247-253`）。当一个模块同时在 header `#(...)` 和 body 都写了同名 parameter（Verilog 不合法但 parser 不挡），builder 是覆盖、报错还是追加？`VerilogParser` 不知道、也不该知道——但**至少要在 docstring 里说明 builder 的契约**。当前是"祈祷 builder 行为正确"。
- **precedence 表的 `COND` 和 `COLON` 同优先级 right-assoc**（`src/VerilogParser.py:162`）。Verilog LRM 里 `?:` 是 right-assoc 没问题，但把 `COLON` 单独列出来是 PLY 的特殊技巧（因为 `?:` 是双 token），如果 `COLON` 在别处（比如 `[msb:lsb]`）也参与移位归约，这里的优先级会**意外影响**那些规则。检查过 `LBRACKET expression COLON expression RBRACKET` 是否会被 precedence 影响——理论上 LBRACKET/RBRACKET 限定了上下文，但这是非显式依赖，应在注释里说明。
- **expression 拼字符串丢空格**（`src/VerilogParser.py:438`、`:445` 等多处）。`f"{p[1]}{p[2]}{p[3]}"` 把 `a + b` 拼成 `a+b`，对 sympy 多数情况无害，但对 Verilog 数字字面量 `8'd 10` 这类（虽然不合法但 lexer 可能容错）会拼成歧义串。最低限度加空格：`f"{p[1]} {p[2]} {p[3]}"`。
- **`p_module_declaration_error` 重复了 `p_module_declaration` 的 build 逻辑**（`src/VerilogParser.py:206-224` vs `:183-204`）。两段几乎一样的 try/except VerilogASTError/Exception，提取成 `_finalize_ast(module_name)` 私有方法。当前是 ~15 行重复代码。
- **`__init__` 调用 `yacc.yacc(module=self, ...)`，每次实例化重建 parser**（`src/VerilogParser.py:61`）。PLY 的 yacc 表生成是**昂贵的**（毫秒级，对于复杂语法可达秒级）。批量解析时每个实例都重建。建议：classmethod 缓存或模块级单例 parser table。`write_tables=False` 还放弃了 PLY 的 parser.out 缓存机制。
- **零类型注解在 yacc 规则里**（整个文件 `def p_*` 全部 `def p_xxx(self, p):` 没有返回类型）。yacc 规则确实不容易标注（`p` 是 `YaccProduction`），但至少 `parse_file`/`parse_string`/`get_module_info` 返回类型已经标了，规则方法可以加 `-> None` 让 mypy 安静。

## Linus 式改进方向

1. **杀死所有 `except Exception: return None`**。Parser 是数据管线的入口，**入口禁止吞错**。把 `parse_file`/`parse_string` 改成抛 `VCGParseError` / `VCGFileError`，让上层决定怎么报告用户。当前的 None 返回值制造了一个"成功路径=AST，失败路径=None"的二态接口，调用方每次都要 if 判断，本身就是特殊情况——好品味是**消除这个 None**，让接口只有一种成功形态。

2. **`p_module_declaration` 异常时不要构造空 AST**。直接 `raise`，让 yacc 把 production 标记为失败，让 `parse_string` 抛出 VCGParseError。"返回伪造的合法对象"是 silent corruption 的根源。

3. **`module_item_assignment/always/instance` 三选一**：(a) 真解析它们建 AST，(b) 用一个统一的 `module_item_skip` 规则消费 token 直到 SEMICOLON 或匹配的 BEGIN/END，并在动作里 log debug "skipped non-port construct"，(c) 把这些规则删了让 parser 在遇到时**明确报错**——上层调用方目前根本不需要 always/instance 的 AST，那就别假装支持。**最差的做法是当前这个：吃下去、不报错、不建 AST、还用错误的语法定义。**

4. **错误恢复要记录错误**。`p_error` 和 `error` token 规则必须**双向**记录到 `self.parse_errors`。当前只有 p_error 记录，导致 `module_item_list error SEMICOLON` 这种恢复路径完全静默。一个简单的不变式：**parse 完成后，如果 parse_errors 非空，则 ast 不可信**。

5. **expression 改回真 AST**（如果有时间）。当前"字符串拼接 + sympy 再解析"是双重解析。一个 dataclass `BinOp(op, left, right)` / `UnaryOp(op, operand)` / `Literal(value)` 的轻量 expression AST 配合 visitor 模式生成字符串，比当前实现清楚 10 倍，且消灭"拼接丢空格"这类 footgun。如果短期不动，**至少在拼接处加空格**。

6. **删掉 unused import**（`src/VerilogParser.py:26`）。30 秒的事，没借口。

7. **`get_module_info` 失败时返回 None 或抛异常，不要返回空 dict 顶上**（`src/VerilogParser.py:154-158`）。和第 1 条同源——不要造伪数据。

8. **parser 实例化优化**（如果 profiling 显示慢）：模块级缓存 yacc table，或允许传入预生成的 parser。这不是 P0，但批量处理大型 Verilog 项目时会很明显。

**总结**：这文件最大的问题不是行数，是**它表面上能跑、实际上把错误全藏起来**。540 行精简版本继承了旧版本的所有静默故障，还多了几个错误的 yacc 规则。重构应该先把 silent failure 都改成 fail loud，再考虑数据结构。当前状态：能 demo，不能上生产。
