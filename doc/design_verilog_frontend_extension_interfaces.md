# Verilog Frontend Extension Interfaces

> 日期: 2026-05-10
> 状态: design
> 范围: `VerilogPreprocess` / `VerilogParser` / future SystemVerilog extension
> 关联: `PROJECT.md` 决策 13-18, `doc/decisions/2026-05-10_verilog_frontend_scope_and_grammar.md`, `src/verilog.bnf`

## 背景

当前 VCG Verilog 前端只实现目标 module 的 module-level declaration 子集解析。
近期不会实现完整 ``include`` 展开，也不会实现 SystemVerilog package import 解析。

但 API 设计必须给未来扩展留下位置，避免后续支持 ``include``、`import`、
source mapping、package resolver 时破坏现有调用方。

## 总原则

1. **现有简单 API 保持可用**

   当前调用方仍可继续使用：

   ```python
   VerilogPreprocess(macros).preprocess_string(code)
   VerilogParser(macros).parse_file(path)
   ```

2. **复杂能力通过 options / resolver 注入**

   不在函数内部隐式搜索 include path，不隐式读取 package 文件。未来能力通过显式
   resolver 注入。resolver 必须接收搜索根目录或搜索上下文。

3. **``include`` 属于预处理层**

   ``include`` 是文本包含和 source mapping 问题，由 preprocess 层处理。

4. **SystemVerilog `import` 属于语法/语义层**

   `import pkg::*;` 是 package 可见性声明，不是文本展开。它应由 parser 记录为
   metadata，后续 semantic resolver 再解释。

5. **所有扩展都必须保留 source location**

   一旦支持 include/import，错误诊断不能只报“预处理后第 N 行”，必须能映射回原始
   文件和 include 文件。

## 建议接口草案

以下接口是未来扩展的设计目标，不要求 TASK-09 全部实现。

### Source Model

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass(frozen=True)
class SourceLocation:
    path: Optional[Path]
    line: int
    column: int = 1

@dataclass(frozen=True)
class SourceSpan:
    start: SourceLocation
    end: SourceLocation

@dataclass(frozen=True)
class SourceFile:
    path: Optional[Path]
    text: str
```

用途：

- `path=None` 表示来自 `parse_string()` 的内存输入。
- include 展开后，每一行仍能追踪回原始 `SourceFile`。
- parser/preprocess diagnostics 使用 `SourceLocation`，不要只传字符串。

### Diagnostics

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class FrontendDiagnostic:
    code: str
    message: str
    location: SourceLocation | None = None
    severity: str = "error"
```

规则：

- 当前可继续抛 `VCGParseError`。
- 未来内部应积累 `FrontendDiagnostic`，最终由 parser 决定是否 fail loud。
- warning 不应阻止 AST 返回；error 必须阻止 AST 返回。

## Preprocess 扩展接口

### Search Roots

`include` 和未来 `import` 都需要从一组目录中查找文件，但二者语义不同：

- ``include`` 按 include 文件名查找文本文件。
- `import` 按 package 名查找 package 定义文件或 package 索引。

因此可以共用搜索根目录数据结构，但不能共用 resolver 行为。

```python
@dataclass(frozen=True)
class SearchRoot:
    path: Path
    recursive: bool = False
    file_patterns: tuple[str, ...] = ()

@dataclass(frozen=True)
class FileSearchResult:
    source: SourceFile
    resolved_path: Path
    root: SearchRoot
```

约束：

- `SearchRoot.path` 必须由调用方显式传入。
- 默认不递归搜索，除非 `recursive=True`。
- 多个搜索结果匹配同一 include/package 时，必须报 ambiguity error。
- resolver 可以做缓存，但缓存 key 必须包含搜索根目录和文件修改信息，避免跨工程污染。

### Options

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

IncludePolicy = Literal[
    "disabled",
    "error_in_declarations",
    "expand",
]

@dataclass(frozen=True)
class PreprocessOptions:
    target_module: str | None = None
    include_policy: IncludePolicy = "error_in_declarations"
    include_roots: Sequence[SearchRoot] = ()
    max_include_depth: int = 16
    preserve_value_macros: bool = True
```

语义：

- `disabled`: 任何 active ``include`` 都作为 unsupported directive 处理。
- `error_in_declarations`: 当前推荐默认值。目标声明范围外的 include 可丢弃；声明
  范围内 include 报错。
- `expand`: 未来支持。通过 `IncludeResolver` 展开 include。
- `include_roots`: 未来 `expand` 模式的 include 文件搜索根目录。
- `preserve_value_macros=True`: 位宽/参数表达式中的 `` `WIDTH`` 保留原文。

### Include Resolver

```python
from typing import Protocol

class IncludeResolver(Protocol):
    def resolve_include(
        self,
        include_name: str,
        current_file: Path | None,
        include_roots: Sequence[SearchRoot],
    ) -> FileSearchResult:
        ...
```

约束：

- resolver 是唯一允许读取 include 文件的组件。
- resolver 必须由调用方显式传入；默认不读文件。
- resolver 负责路径搜索和读取，preprocess 负责循环检测和深度限制。
- 搜索顺序建议为：当前文件目录优先，然后按 `include_roots` 顺序查找。
- `include_name` 是 ``include`` 指令中的 spelling，例如 `"defs.vh"` 或
  `"sub/defs.vh"`，resolver 负责规范化路径。
- 循环 include、超过深度、找不到文件都应转成 `VCGFileError` 或 `VCGParseError`。

### Preprocess Result

```python
@dataclass(frozen=True)
class PreprocessedLine:
    text: str
    source: SourceLocation

@dataclass(frozen=True)
class PreprocessResult:
    text: str
    target_module: str | None
    lines: tuple[PreprocessedLine, ...]
    macros: dict[str, str]
    diagnostics: tuple[FrontendDiagnostic, ...] = ()
```

未来推荐新增高阶接口：

```python
class VerilogPreprocess:
    def preprocess(
        self,
        source: SourceFile,
        options: PreprocessOptions | None = None,
        include_resolver: IncludeResolver | None = None,
    ) -> PreprocessResult:
        ...
```

兼容接口保留：

```python
def preprocess_string(
    self,
    verilog_code: str,
    target_module: str | None = None,
) -> str:
    ...

def preprocess_file(
    self,
    file_path: str,
    target_module: str | None = None,
) -> str:
    ...
```

`preprocess_string()` / `preprocess_file()` 可以内部调用 `preprocess()`，再返回
`PreprocessResult.text`。

## Parser 扩展接口

### Parse Options

```python
@dataclass(frozen=True)
class ImportOptions:
    package_roots: Sequence[SearchRoot] = ()
    auto_index_packages: bool = False
    package_file_patterns: tuple[str, ...] = ("*.sv", "*.svh", "*.v")

@dataclass(frozen=True)
class ParseOptions:
    target_module: str | None = None
    preprocess: PreprocessOptions = PreprocessOptions()
    imports: ImportOptions = ImportOptions()
```

`ImportOptions` 语义：

- `package_roots` 是未来 package/import 搜索根目录。
- `auto_index_packages=False` 表示默认不扫描目录；调用方可以预先提供 resolver 或索引。
- `auto_index_packages=True` 允许 resolver 在 package roots 下扫描文件并建立 package
  name -> source file 索引。
- `package_file_patterns` 限制 package 扫描候选文件类型。
- 该能力属于 future task，不属于 TASK-09。

未来兼容接口：

```python
class VerilogParser:
    def parse_file(
        self,
        filepath: str,
        target_module: str | None = None,
        options: ParseOptions | None = None,
    ) -> VerilogAST:
        ...

    def parse_string(
        self,
        verilog_code: str,
        target_module: str | None = None,
        options: ParseOptions | None = None,
    ) -> VerilogAST:
        ...
```

要求：

- `target_module` 可选参数不破坏旧调用。
- `options.target_module` 与显式 `target_module` 同时出现时，显式参数优先，或直接
  抛配置冲突错误；二选一必须文档化。
- parser 返回 AST 时，`ast.module_name` 必须等于选中的目标 module。

## SystemVerilog Import 扩展接口

### Import Data

```python
@dataclass(frozen=True)
class PackageImport:
    package: str
    symbol: str | None
    wildcard: bool
    location: SourceLocation | None = None
```

例子：

```systemverilog
import axi_pkg::*;
import cfg_pkg::cfg_t;
```

对应：

```python
PackageImport(package="axi_pkg", symbol=None, wildcard=True)
PackageImport(package="cfg_pkg", symbol="cfg_t", wildcard=False)
```

### Parser Context

```python
@dataclass(frozen=True)
class ParseContext:
    package_imports: tuple[PackageImport, ...] = ()
```

未来 `VerilogAST` 可增加：

```python
class VerilogAST:
    def get_imports(self) -> list[PackageImport]:
        ...
```

兼容要求：

- 当前不需要实现 `get_imports()`。
- 如果未来新增，必须是“只加不改”的 API 扩展。
- 不应让 `import` 改变现有 `get_port_info()` / `get_parameter_info()` 返回结构。

### Import Resolver

```python
class ImportResolver(Protocol):
    def resolve_package(
        self,
        package_name: str,
        package_roots: Sequence[SearchRoot],
    ) -> FileSearchResult:
        ...

    def resolve_import(
        self,
        package_import: PackageImport,
        context: ParseContext,
    ) -> object:
        ...
```

约束：

- `ImportResolver` 不属于 preprocess。
- 默认 parser 不读取 package 文件；只有显式传入 resolver 和 package roots 时才允许
  解析 package 文件。
- package 搜索是按 package 名查找定义，不是按 import spelling 直接拼文件名。
  resolver 可以采用工程约定，例如 `axi_pkg -> axi_pkg.sv`，也可以扫描 package
  declarations 建索引。
- package 搜索根目录必须显式传入，不能隐式从 cwd 或工程根目录猜。
- 多个 package 定义冲突时必须报错，不能静默选第一个。
- 初期支持 SystemVerilog type name 时，可以只保留 type text，例如
  `cfg_t cfg_port`，不做完整符号解析。
- 真正的 package symbol resolution 是后续 semantic analysis，不是 TASK-09。

## Manager 侧未来接入点

`InstanceManager` / `WiresManager` 当前签名已经有 `module_name`：

```python
generate_instance(file_path, module_name, instance_name)
generate_wires_def(file_path, module_name, ...)
```

未来应把该参数贯通到 parser：

```python
ast = self.parser.parse_file(file_path, target_module=module_name)
```

并检查：

```python
if ast.module_name != module_name:
    raise VCGParseError(...)
```

这个改动不属于 TASK-09，但 Preprocess 的 `target_module` 可选参数要为它预留。

## TASK-09 的最小落地要求

TASK-09 不需要实现上述完整接口，但建议不要写死未来路径：

- `preprocess_string()` 可以新增 `target_module: str | None = None`。
- 内部 helper 应使用带 `line_no` 的行对象，方便以后扩展到 `SourceLocation`。
- include 处理应集中在一个 helper 中，未来能替换为 `IncludeResolver`。
- 不要把 `import` 当作 preprocessor directive 处理。
- 不要在 preprocess 层读取 package 文件。

## 后续任务建议

1. TASK-09: Preprocess 数据流重构，预留 `target_module` 和 source line 结构。
2. TASK-10: Lexer token 契约，显式支持/拒绝 `MACRO_ID`、`SYSTEM_ID`。
3. TASK-11: Parser declaration group 与 target module 契约。
4. TASK-12: Manager 贯通 `module_name -> parser target_module`。
5. Future TASK: include expansion resolver。
6. Future TASK: SystemVerilog import metadata and package resolver。
