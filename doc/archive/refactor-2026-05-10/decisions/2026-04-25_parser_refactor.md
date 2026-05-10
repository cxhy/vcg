# VerilogParser.py 重构

**日期**: 2026-04-25
**分支**: refactor/code-cleanup
**依据**: `doc/review/10_VerilogParser.md`（Linus 风格评审）

## 核心决策

将 Parser 从"静默吞错、返回 None/伪数据"的二态接口，改为"成功返回 AST 或抛 VCGError 子类"的一态接口。动机：`PROJECT.md` 决策 1 禁止 `except Exception` 吞语义化异常；原实现在 `parse_file` / `parse_string` / `p_module_declaration` 三处制造 silent corruption。

## 变更摘要

### `src/VerilogParser.py`

- **入口抛异常**：`parse_file` 抛 `VCGFileError`（FileNotFoundError/UnicodeDecodeError/OSError 分支分别 `from e`）；`parse_string` 保留 `VCGError` 传播，未识别异常包装为 `VCGParseError`。返回类型从 `Optional[VerilogAST]` 改为 `VerilogAST`。
- **失败出口统一**：`parse_string` 末尾判断 `self.ast is None`，非空时抛 `VCGParseError` 并包含所有 `parse_errors`。
- **移除伪造 AST**：
    - `p_module_declaration` 不再在 `VerilogASTError` 时构造空 `VerilogAST(module_name)`；改为通过新的私有方法 `_finalize_ast` 调用 `builder.build()`，失败时 `self.ast = None` + 追加 `parse_errors`。
    - `p_module_declaration_error`（语法错误版本）同样不再构造 AST，只记录错误。
- **删除死代码规则 `p_module_item_always`**：其文法 `ALWAYS expression BEGIN expression_list END` 在语义上是错的（always 不是逗号分隔的 expression 列表），且 Lexer 没有 `@`、`posedge`、`negedge`、`DOT` 等 token — 真实 `always @(...)` 块根本到不了 parser。删除后 Lexer 出现 3 个 "unused token" 警告（ALWAYS/BEGIN/END），是已知副作用，留给 Lexer 后续清理。
- **module-level `assign` / `instance` 保留**：`tests/sub_module.v:13-14` 有真实 module-level `assign`。规则保留但在动作里加 `logger.debug("skipped module-level assign (not represented in AST)")`，明确"吞 token 不建 AST"的意图。
- **错误恢复可见化**：`module_item_list error SEMICOLON` 从"静默恢复"改为追加 `parse_errors`；`p_opt_port_list` 新增 `LPAREN error RPAREN` 错误产生式，与 `p_opt_parameter_list` 对称。
- **补齐合法语法**：`opt_parameter_list` 增加 `HASH LPAREN RPAREN`（空参数列表是合法 Verilog），避免靠伪数据通过测试。
- **get_module_info**：AST 为 None 时返回 None（不再是空 dict）。
- **expression 拼接加空格**：二元/三元运算符拼接从 `f"{p[1]}{p[2]}{p[3]}"` 改为 `f"{p[1]} {p[2]} {p[3]}"`，降低 sympy 歧义风险。
- **清理 unused import** `setup_vcg_logging`、`pathlib.Path`。

### `src/vcg_instance_manager.py` / `src/vcg_wires_manager.py`

- `_parse_verilog_file` 从 "调 parser + 判 None + 手动 raise" 简化为 `return self.parser.parse_file(file_path)`，让 `VCGFileError`/`VCGParseError` 直接冒泡。
- 顶层 `except FileNotFoundError → raise VCGFileError` 和 `except Exception → raise VCGParseError` 改为 `except (VCGFileError, VCGParseError): raise` + `except Exception → raise VCGRuntimeError`（未预期错误应归类为运行时错误而非语法错误）。

### `tests/test_VerilogParser.py`

- `test_f5_1`/`test_f5_2`：`assert result is None` → `pytest.raises(VCGFileError)`。
- `test_f5_3`…`test_f5_8`、`test_f2_12`、`test_b7`、`test_b8`、`test_f1_4`：permissive/is-None 断言 → `pytest.raises(VCGParseError)`。
- `test_f5_3`（缺 endmodule）保留 permissive：PLY 在 EOF 处可能恢复，接受 AST 或抛异常均可（但 AST 必须非 None）。

### `tests/test_vcg_instance_manager.py`

- 5 个 mock 测试改为让 `parser.parse_file.side_effect` 抛 `VCGFileError`/`VCGParseError`（原版依赖 mock 返回 None 或原生 `FileNotFoundError`，现在是 parser 已经做了该转换）。
- `test_unexpected_exception_handling` 期望类型从 `VCGParseError` 改为 `VCGRuntimeError`。

## 不做的事

- 不重构 expression 为真正 AST（review P2 第 5 项）：工作量大，超出"修正失败路径"核心目标。
- 不缓存 yacc parser table：性能优化非正确性。
- 不统一所有 `_error` 规则的 `p.lineno()` 索引（review P1 多处）：只修了 `p_opt_packed_dimension` 一处（索引明显错），其余行号语义略糊但不影响正确性。
- 不删 Lexer 的 ALWAYS/BEGIN/END 保留字：Parser 已不用，但 Lexer 改动是另一个 review（`09_VerilogLexer.md` 已做过），避免本次 PR 改跨模块。

## 验证

- `uv run pytest tests/` ： 536 / 536 通过（基线 536，重构前受影响的 17 个测试断言已同步更新）。
- `uv run python vcg.py tests/test_top.v`：端到端生成成功（`VCG generate Done`）。
- 手工冒烟：`parse_file('/bad/path')` 抛 `VCGFileError`，`parse_string('module m(input x')` 抛 `VCGParseError`，`get_module_info()` 在 ast 为 None 时返回 `None`。

## 经验

1. "测试通过"不等于"行为正确"：旧 `test_f2_11_empty_parameter_list` 依赖 `get_module_info` 返回空 dict 的伪数据"通过"，但 parser 从未真的解析过 `module m #()`。删掉伪数据后真正语法支持才补上。类似的，`test_f5_*` 系列 permissive 断言 `assert result is None or isinstance(result, object)` 永远为真（None 也是 object），等同于不做断言 — fail-loud 后必须改成 `pytest.raises` 才是真验证。
2. PLY 的 `errok()` 与 `error` 产生式的交互：本项目的 `p_error` 调用 `errok()` 但不消费 token，依赖 `LPAREN error RPAREN` 等规则的 error 符号消耗 token 来恢复。review 担心的 "死循环" 在当前 grammar 下没被触发（实测无问题），强行 `self.parser.token()` 反而破坏 `HASH LPAREN error RPAREN` 的恢复链路（一次尝试后回退）。
3. Silent corruption 的成本：`p_module_declaration` 原本在 build 失败时返回空 `VerilogAST(module_name)`，调用方拿到"模块名正确、端口为空"的 AST，会在远离 root cause 的位置（下游 `instance_manager` 生成零端口例化）爆。fail-loud 让错误停在 root cause。
