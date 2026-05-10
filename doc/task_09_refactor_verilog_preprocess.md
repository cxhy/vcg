# TASK-09: 重构 VerilogPreprocess 数据流与声明抽取

| 字段 | 值 |
|------|----|
| 负责 | vcg-python-dev |
| 依赖 | `PROJECT.md` 决策 13-18；`doc/decisions/2026-05-10_verilog_frontend_scope_and_grammar.md`；`doc/design_verilog_frontend_extension_interfaces.md`; `src/verilog.bnf` |
| 状态 | pending_user_confirmation |
| 创建 | 2026-05-10 |
| 范围 | `src/VerilogPreprocess.py` 为主；允许同步更新 `tests/test_VerilogPreprocess.py`；不修改 Parser/Lexer/AST 实现 |

## 需求描述

当前 `VerilogPreprocess.py` 的核心问题是数据流顺序错误：

```text
先裁掉 module 前内容 -> 再做条件编译 -> 再抽取声明
```

这会丢掉 module 前的 ``define``、include guard、条件编译上下文，并让多 module
文件默认取第一个 module。根据长期决策，本轮应改成：

```text
原始文件
  -> 整文件 partial preprocessing / 条件编译扫描
  -> 目标 module 定位
  -> 目标 module 声明相关文本抽取
  -> parser
```

本任务只重构 Preprocess 层，不实现完整 Verilog 预处理器，也不修改
`VerilogParser.py` 的 grammar。

## 设计目标

1. **整文件上下文优先**

   条件编译必须在整文件范围处理，不能先删除 module 前内容。module 前的
   ``define`` / ``undef`` / include guard 必须影响后续目标 module 的条件分支。

2. **Partial preprocessing，而不是完整 macro expansion**

   支持结构性代码切片：

   ```text
   `ifdef / `ifndef / `elsif / `else / `endif / `define / `undef
   ```

   但位宽、参数默认值、表达式中的 object-like macro reference 必须保留原文：

   ```verilog
   input [`WIDTH-1:0] data
   parameter DEPTH = `DEPTH_DEFAULT
   localparam ADDR_W = $clog2(`DEPTH)
   ```

   不实现 ``include``、function-like macro、token pasting、stringification、
   nested macro expansion。

   ``include`` 的处理边界：

   - 当前任务不打开、不展开 include 文件。
   - active ``include`` 位于目标 module 声明抽取范围之外时，可以被丢弃。
   - active ``include`` 位于目标 module header 或 body declaration 子集内时，
     必须抛 `VCGParseError`。
   - 如果 include 文件中的宏会影响条件编译，本轮要求调用方通过 VCG macro
     environment 显式传入，不从 include 文件中推导。

   SystemVerilog `import` 不是预处理指令，不在本任务实现范围内。未来支持时应在
   Parser/AST 层作为 package import metadata 处理，不能当成 ``include`` 文本展开。

   未来 include/import 搜索接口的 guardrail：

   - 本任务不实现 `SearchRoot` / `IncludeResolver` / `ImportResolver` 的完整公共 API。
   - 但 include 检测必须集中在独立 helper 中，未来能替换为
     `IncludeResolver.resolve_include(...)`。
   - 不允许在本任务中硬编码 cwd、项目根目录、文件所在目录之外的隐式搜索策略。
     未来搜索根必须由调用方通过 `include_roots` / `package_roots` 显式传入。
   - 多个候选文件匹配同一 include/package 时，未来必须报 ambiguity error，不能静默
     选第一个；本任务不能写出会阻碍该行为的接口。
   - `import` 不能进入 preprocess directive 分支，也不能在 preprocess 层读取 package
     文件。

3. **声明抽取只保留当前 parser 可消费的子集**

   输出给 parser 的文本应包含：

   - module header。
   - header 中条件编译后仍 active 的端口和参数声明。
   - body 内 `input` / `output` / `inout` 声明。
   - body 内 `parameter` / `localparam` 声明。
   - `endmodule`。

   非声明型 body item 不进入输出：

   - `assign`
   - module instance
   - `always`
   - `generate`
   - 其他非声明型 body item

   如果非声明型 body item 让声明边界无法可靠判断，必须抛 `VCGParseError`，不能猜。

4. **注释和字符串扫描要可靠**

   当前 `_code_visible_to_preprocessor()` 不懂字符串，会把字符串里的 `//`、
   `/* */`、`;` 当成注释或语句结束。需要使用小型 scanner 区分：

   - CODE
   - LINE_COMMENT
   - BLOCK_COMMENT
   - STRING

   只有 CODE 状态下的 directive、module 起点和分号才参与结构判断。

5. **为目标 module 选择预留接口**

   当前 `VerilogParser.parse_file()` 没有传入 `module_name`，`InstanceManager` /
   `WiresManager` 的 `module_name` 也尚未传到 parser。本任务不强行改下游 API，
   但 `VerilogPreprocess` 内部应预留按目标 module 选择的实现边界。

   最低要求：

   - 现有 `preprocess_string(verilog_code: str) -> str` 保持兼容，默认解析第一个
     active module。
   - 可新增兼容扩展接口，例如：

     ```python
     def preprocess_string(
         self,
         verilog_code: str,
         target_module: str | None = None,
     ) -> str:
         ...
     ```

     但不能要求调用方立即修改。

   - 如果实现 target module 参数，找不到目标 module 应抛 `VCGParseError`。
   - 如果同名 module 多次出现，应抛 `VCGParseError`。

## 建议内部数据结构

允许新增私有 dataclass，建议不要暴露为 public API：

```python
@dataclass(frozen=True)
class SourceLine:
    line_no: int
    raw: str
    code: str
    active: bool

@dataclass(frozen=True)
class ModuleSpan:
    name: str
    start_line: int
    end_line: int
    lines: tuple[SourceLine, ...]
```

建议阶段拆分：

1. `scan_visible_code()`：生成带原始行号的行流，注释/字符串安全。
2. `process_conditionals()`：整文件条件编译，生成 active line stream。
3. `find_module_spans()`：在 active code 中定位 module/endmodule 范围。
4. `select_module_span()`：默认第一个 module，或按 target module 精确选择。
5. `extract_declaration_text()`：从目标 module 中抽取 header + module-level declarations。

这些名称不是硬约束，但实现必须体现同等分层，避免继续在一个方法里堆状态。

## 执行步骤

1. **先锁定失败用例**

   在 `tests/test_VerilogPreprocess.py` 中优先补全本任务列出的 P0 行为测试，尤其是
   module 前 ``define``、include guard、字符串中的注释/分号、value-like macro 保留、
   include 位于声明范围内报错。测试应先表达目标行为，再改实现。

2. **实现注释/字符串安全的行扫描**

   把现有 `_code_visible_to_preprocessor()` 升级为小型 scanner，至少区分 CODE、
   LINE_COMMENT、BLOCK_COMMENT、STRING。该阶段只负责产生带原始行号的行流，不做
   module 裁剪。

3. **重排条件编译为整文件处理**

   `process_conditional_compilation()` 的行为保持可调用，但内部必须基于整文件 active
   line stream 工作。所有结构性指令先完成条件栈处理，再进入 module 选择。

4. **增加 module span 定位和目标选择**

   在 active 行流中定位所有 module/endmodule span。未传 `target_module` 时选择第一个
   active module；传入时必须精确匹配，找不到或重复命中都抛 `VCGParseError`。

5. **重写声明抽取**

   从选中的 `ModuleSpan` 中抽取 header、body 端口声明、body parameter/localparam 和
   `endmodule`。非声明 body item 不输出；如果语句边界无法可靠跳过，直接抛
   `VCGParseError`。

6. **集中处理 unsupported directive / include**

   active ``include`` 或其他 unsupported directive 如果落入最终声明文本，必须抛
   `VCGParseError`。落在目标声明范围外可以丢弃。实现形态应为独立 helper，未来可接
   `IncludeResolver`。

7. **保留兼容 wrapper**

   `preprocess_string()` / `preprocess_file()` 返回 `str` 的旧接口必须继续工作。历史上
   没有下划线的 `remove_pre_module_content()`、`extract_module_ports_section()` 已被
   测试和文档直接使用，建议保留为兼容 wrapper；如果开发阶段决定删除或改变语义，
   delivery 文档必须明确列为兼容性破坏，并给出迁移理由。

## 接口约束

### 必须保持兼容

- `VerilogPreprocess(macros=None)` 构造方式不变。
- `read_file(file_path: str) -> str` 行为不变。
- `preprocess_file(file_path: str) -> str` 兼容现有调用。
- `preprocess_string(verilog_code: str) -> str` 兼容现有调用。
- `process_conditional_compilation(content: str) -> str` 如保留，外部可继续调用。
- `remove_pre_module_content(content: str) -> str`、`extract_module_ports_section(content: str)`
  若保留，应作为兼容 wrapper，不再作为新数据流的核心实现点。
- `get_macros() -> Dict[str, str]` 返回副本。
- `clear_macros()` 保持可用，并补返回类型 `-> None`。

### 允许新增

- `preprocess_string(..., target_module: str | None = None)` 的可选参数。
- `preprocess_file(..., target_module: str | None = None)` 的可选参数。
- 私有 dataclass 和私有 helper。

### 不允许

- 不修改 `VerilogParser.py`、`VerilogLexer.py`、`VerilogAst.py`。
- 不把 value-like macro reference 展开成具体值。
- 不实现完整 ``include`` 处理。
- 不把 unsupported body item 建模进 AST。
- 不依赖全局工作目录或外部文件状态。
- 不引入隐式 include/package 搜索路径。

## 行为要求

### 必须修复

1. module 前 ``define`` 能影响 module 内 ``ifdef``。

   ```verilog
   `define ENABLE
   module m;
   `ifdef ENABLE
     input en;
   `endif
   endmodule
   ```

   输出必须包含 `input en;`。

2. include guard 不能因先裁剪而产生孤立 ``endif``。

   ```verilog
   `ifndef M_V
   `define M_V
   module m;
     input clk;
   endmodule
   `endif
   ```

   输出必须包含 `module m;`、`input clk;`、`endmodule`。

3. 字符串里的注释符和分号不能破坏声明抽取。

   ```verilog
   module m;
     parameter URL = "http://example";
     parameter TEXT = "a;b";
     input clk;
   endmodule
   ```

   输出必须保留两个 parameter 和 input。

4. object-like macro reference 在表达式中保留。

   ```verilog
   module m;
     input [`WIDTH-1:0] data;
   endmodule
   ```

   输出必须保留 `` `WIDTH``，不能替换成宏值。

5. 非声明型 body item 不进入 parser 输入。

   ```verilog
   module m(input clk);
     assign x = clk;
     child u0 (.clk(clk));
     input late_decl;
   endmodule
   ```

   输出不应包含 assign / instance；如果后续声明边界仍明确，`input late_decl;`
   应保留。

### 可保留但需标注的旧行为

- 未传 `target_module` 时默认第一个 active module。
- attribute 可以继续被忽略，只要不破坏 module 识别和声明抽取。

## 测试要求

更新 `tests/test_VerilogPreprocess.py`，至少新增或修正以下测试：

1. `test_define_before_module_controls_inside_ifdef`
2. `test_include_guard_wrapping_module_is_supported_without_orphan_endif`
3. `test_value_macro_reference_is_preserved_in_width_expression`
4. `test_macro_value_is_not_expanded_in_parameter_default`
5. `test_string_comment_markers_do_not_start_comments`
6. `test_string_semicolon_does_not_end_declaration_scan_early`
7. `test_multi_module_defaults_to_first_active_module_for_backward_compat`
8. `test_target_module_selects_second_module_if_optional_arg_implemented`
9. `test_target_module_missing_raises_parse_error_if_optional_arg_implemented`
10. `test_non_declaration_body_items_are_ignored_not_output`
11. `test_unsupported_directive_inside_extracted_declaration_raises_parse_error`
12. `test_clear_macros_return_type_and_behavior`
13. `test_include_outside_target_declaration_is_dropped`
14. `test_include_inside_target_declaration_raises_parse_error`

如果实现时决定不新增 `target_module` 可选参数，本任务交付文档必须说明原因，并
把目标 module 选择留给后续 Parser/Manager 契约任务；对应 optional tests 不写。

## 验证命令

开发交付前至少运行：

```bash
uv run pytest tests/test_VerilogPreprocess.py -q
```

建议补充运行：

```bash
uv run pytest tests/test_VerilogPreprocess.py tests/test_VerilogParser.py -q
uv run pytest tests/test_vcg_instance_manager.py tests/test_vcg_wires_manager.py -q
```

如果修改了 `preprocess_string` 输出格式导致 Parser 测试变化，必须在交付文档中
说明影响，并区分“修正错误行为”和“兼容性破坏”。

## 交付物

开发 agent 完成后必须提交：

- `src/VerilogPreprocess.py`
- `tests/test_VerilogPreprocess.py`
- `doc/delivery_09_refactor_verilog_preprocess.md`

Tester agent 后续负责：

- 补充或审查测试覆盖。
- 运行 focused 和相关回归。
- 写 `doc/verification_09_refactor_verilog_preprocess.md`。

Verilog checker 仅在 Parser 输出或下游 AST/Verilog 生成行为受影响时介入，写
`doc/check_09_refactor_verilog_preprocess.md`。

## 已知风险

- **Parser 仍不支持 MACRO_ID token**：本任务要求保留 `` `WIDTH``，但当前
  `VerilogLexer.py` 把反引号包含在 ID 正则中，后续 Lexer/Parser 任务仍需收紧。
- **目标 module 参数尚未贯通下游**：`InstanceManager` / `WiresManager` 当前仍只把
  `module_name` 用于渲染和日志。本任务最多预留 Preprocess 接口，不解决 manager
  契约。
- **声明抽取可能遇到复杂 body**：遇到 generate/procedural block 时，若无法可靠
  跳过，应 fail loud，而不是保留旧的宽松行为。
- **旧测试可能依赖错误输出**：例如空文件返回 `endmodule` 的容忍断言，应改成更
  清晰的行为预期，不能继续扩大模糊兼容。
- **include 文件可能真实包含声明**：本任务不展开 include。若 active include 位于
  目标 module 声明范围内，必须失败，避免在缺失声明的情况下生成 AST。
- **旧 review 队列的编号已过期**：`doc/review/00_INDEX.md` 曾建议把 Lexer/Parser
  错误契约作为 TASK-09、Preprocess 作为 TASK-10。当前分支的实际任务单已经按用户
  决策调整为 TASK-09 Preprocess。历史 review 报告保留不改，执行时以本文档为准。
- **旧 helper 测试可能绑定实现细节**：现有测试直接调用
  `remove_pre_module_content()` / `extract_module_ports_section()`。重构时应优先通过
  wrapper 保持可用，避免把测试迁移误判为产品行为修复。

## 架构 Review 结论

- 原计划的核心方向正确：必须先整文件处理条件编译，再定位目标 module，最后抽取声明。
- 需要更新的主要内容是 include/import 的未来扩展接口。搜索目录必须是显式
  `include_roots` / `package_roots`，不能在 TASK-09 中写死 cwd 或项目根。
- TASK-09 不应提前实现完整 include/import，但必须把 include 检测集中化，避免未来
  接入 resolver 时推倒重写。
- 旧的 public-ish helper 需要纳入兼容边界；否则测试改动会混入 API 破坏，影响 review
  判断。
- 空文件、无 module 文件建议继续返回空字符串，不再扩大“返回 endmodule 也可接受”的
  模糊兼容；如果实现选择改为抛错，必须在 delivery 文档中单独说明。

## 非目标

- 不实现完整 Verilog/SystemVerilog 预处理器。
- 不实现 ``include``。
- 不实现 SystemVerilog `import`。
- 不实现 function-like macro expansion。
- 不修改 Parser declaration group。
- 不修改 Lexer token 契约。
- 不修改 AST 数据模型。
- 不修复 InstanceManager/WiresManager 的 module_name 校验。
