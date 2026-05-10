# TASK-08: Refactor WiresManager

| 字段 | 值 |
|------|----|
| 负责 | vcg-python-dev / vcg-python-tester / vcg-verilog-checker |
| 依赖 | TASK-07 |
| 状态 | completed |
| 创建 | 2026-05-10 |

## 需求描述

完成 `src/vcg_wires_manager.py` 的低风险结构性重构，使其与已重构的
`src/vcg_instance_manager.py` 保持一致的“解析 -> 解析规则 -> 渲染”结构，同时修复
`doc/review/08_vcg_wires_manager.md` 和 `doc/refactor_backlog_2026-05-10.md` 中记录的
宽度格式化、多维数组识别和异常处理问题。

本任务目标是清理当前模块内部复杂度，不引入 `WireWidth` ADT，不修改 Parser / AST /
RuleManager 的公开数据结构。

## 范围

### 必须修改

- `src/vcg_wires_manager.py`
- `tests/test_vcg_wires_manager.py`
- `doc/delivery_08_refactor_vcg_wires_manager.md`
- `doc/verification_08_refactor_vcg_wires_manager.md`
- `doc/check_08_refactor_vcg_wires_manager.md`

### 可选修改

- `doc/refactor_backlog_2026-05-10.md`：任务完成后同步状态。

### 禁止修改

- `src/VerilogAst.py`
- `src/VerilogParser.py`
- `src/vcg_rule_manager.py`
- `src/vcg_execution_engine.py`
- 其他与 WiresManager 无关的模块。

## 接口约束

公开接口必须保持兼容：

```python
class WiresManager:
    def __init__(self, rule_manager: VCGRuleManager, macros=None): ...

    def generate_wires_def(
        self,
        file_path: str,
        module_name: str,
        port_direction: str | None = None,
        pattern: str = "greedy",
    ) -> str: ...

    def set_base_spacing(self, spacing: int): ...
    def get_base_spacing(self) -> int: ...
```

`generate_wires_def()` 的行为约束：

- `pattern` 仅允许 `"lazy"` / `"greedy"`，非法值继续抛 `ValueError`。
- `port_direction` 仅允许 `None` / `"input"` / `"output"` / `"inout"`，大小写不敏感，非法值继续抛 `ValueError`。
- `VCGFileError` / `VCGParseError` / `VCGSyntaxError` / `VCGRuntimeError` 必须透传。
- 未知异常可包装为 `VCGRuntimeError`，必须使用 `raise ... from e`，不得伪装成 parse/file error。
- 输出仍为多行 wire 声明字符串，行间使用 `\n`。

Wire 生成规则必须保持兼容：

- greedy + 规则匹配有效名称：使用规则名称。
- greedy + 规则匹配空名称：不生成该端口 wire。
- greedy + 规则未匹配：使用端口名作为 wire 名称。
- lazy + 规则匹配有效名称：使用规则名称。
- lazy + 规则匹配空名称：不生成该端口 wire。
- lazy + 规则未匹配：不生成该端口 wire。

宽度格式化必须保持兼容：

- `None` / `""` / `0` / `1` -> 无宽度声明。
- 整数 `N > 1` -> `[N-1:0]`。
- 数字字符串 `"N"` 且 `N > 1` -> `[N-1:0]`。
- 已格式化单维 range 如 `"[15:0]"` -> 原样保留。
- 多维 range 如 `"[7:0][3:0]"` 和 `"[7:0] [3:0]"` -> 原样保留。
- 标识符宽度如 `"WIDTH"` -> `[WIDTH-1:0]`。
- 表达式宽度如 `"N+1"` / `"(A+B)*C-1"` -> `[(expr)-1:0]`。

## 设计要求

`vcg-python-dev` 实现时应至少拆出以下私有职责：

```python
def _resolve_effective_width(self, rule_width, port: PortInfo):
    """Rule width has priority; otherwise use port.width."""

def _format_wire_width(self, width_input) -> str:
    """Convert supported width input forms to Verilog range text."""

def _is_range_text(self, width_text: str) -> bool:
    """Return True for a single bracketed range."""

def _is_multi_dimensional(self, width_text: str) -> bool:
    """Return True for two or more adjacent bracketed dimensions, allowing whitespace."""

def _render_wire_declaration(
    self,
    wire_name: str,
    width_text: str,
    expression: str | None,
) -> str:
    """Render final wire declaration with existing alignment behavior."""

def _pad_prefix(self, prefix: str) -> str:
    """Return spacing between prefix and wire name."""
```

可以调整具体函数名，但必须做到：

- 宽度选择、宽度格式化、对齐、声明渲染分离。
- `_format_wire_declaration()` 不再同时承载所有细节；如保留该函数，只作为薄组合层。
- `_is_multi_dimensional()` 不再依赖紧贴的 `"]["`，必须允许 `"] ["` 和 `"]\t["`。
- `_generate_single_wire()` 中 lazy/greedy 分支应表达为清晰的规则表，删除不可达的防御性分支。
- 类型注解改为现代写法：`list[T]`、`T | None`。
- 删除未使用 import，例如 `Tuple`、`Dict`、`ParameterInfo`、`PortType`、`VCGSyntaxError` 如未使用。

## 测试要求

必须先补失败测试，再改实现。测试重点放在真实行为而不是 patch 已经创建过的 `VerilogParser`
类对象。

至少新增或收紧以下测试：

- `_format_wire_width("[7:0] [3:0]")` 保留空格形式多维 range。
- `_format_wire_width("[7:0]\t[3:0]")` 保留 tab 形式多维 range。
- rule width 优先于 `port.width`。
- rule width 为空时 fallback 到 `port.width`。
- `VCGSyntaxError` 从 parser 透传，不被包装。
- 未知异常包装为 `VCGRuntimeError` 且 `__cause__` 是原异常。
- greedy/lazy 的六种 rule_matched × wire_name_empty 行为输出明确断言。
- spacing 输出使用精确字符串断言，不只断言包含 `"wire"`。

现有测试中 patch `src.vcg_wires_manager.VerilogParser` 但在 fixture 已创建 `WiresManager`
之后才生效的用例，应改为直接替换 `wires_manager.parser` 或直接测试私有纯函数。

## 验收标准

- `src/vcg_wires_manager.py` 文件少于 800 行，单个函数少于 50 行。
- 公开 API 与调用方兼容，`src/vcg_execution_engine.py` 不需要适配。
- `tests/test_vcg_wires_manager.py` 针对上述新增行为有失败后转绿记录。
- focused validation 通过：

```bash
uv run pytest tests/test_vcg_wires_manager.py -q
```

- broader validation 通过：

```bash
uv run pytest tests/test_vcg_wires_manager.py tests/test_vcg_instance_manager.py tests/test_vcg_rule_manager.py -q
```

- Verilog checker 至少检查一个真实 `WiresDef(...)` 输出片段，确认宽度和声明语法仍合理。

## 交付物

`vcg-python-dev` 交付：

- 重构后的 `src/vcg_wires_manager.py`
- `doc/delivery_08_refactor_vcg_wires_manager.md`

`vcg-python-tester` 交付：

- 更新后的 `tests/test_vcg_wires_manager.py`
- `doc/verification_08_refactor_vcg_wires_manager.md`

`vcg-verilog-checker` 交付：

- `doc/check_08_refactor_vcg_wires_manager.md`

## 已知风险

- 当前测试文件存在较多弱断言，必须优先收紧关键行为，否则重构可能只保持“包含 wire”的假阳性。
- `PortInfo.width` 和 `VCGRuleManager.resolve_wire_generation()` 的 `width` 字段仍然是弱类型；
  本任务只在 WiresManager 层整理兼容逻辑，不解决上游类型债。
- 多维数组输出是否完全合法依赖 Parser/AST 对 SystemVerilog packed/unpacked dimension 的表达；
  本任务只保证现有字符串形式不被误改写。
- `set_base_spacing(0)` / 负数 spacing 当前允许，本任务保持兼容，不新增校验。
