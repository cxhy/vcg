# src/vcg_exceptions.py Linus 技术评审

## 评审范围

- 主文件：`src/vcg_exceptions.py`
- 只读上下文：`CLAUDE.md`、`PROJECT.md`、`vcg.py`、`src/VerilogParser.py`、`src/VerilogPreprocess.py`、`src/vcg_file_processor.py`、`src/vcg_execution_engine.py`、`src/vcg_instance_manager.py`、`src/vcg_wires_manager.py`、`tests/test_vcg_exceptions.py`
- 未修改源码，未提交 git。

## 品味评分

黄：凑合偏上，6.5/10。

这份文件不是垃圾。它保住了 `VCGError("message")` 的老接口，又给异常加了 `path`、`lineno`、`column`、`snippet` 这些结构化字段，方向是对的。问题是它现在更像一个“好接口的起点”，不是一个已经被系统真正用起来的异常模型。

## 核心判断

值得保留，但还没完成。

`VCGError -> File/Parse/Syntax/Runtime` 这个层级是项目里真实需要的：CLI、parser、processor、execution engine 都依赖异常类型区分失败阶段。`src/vcg_exceptions.py:44-58` 的兼容构造也没有破坏旧调用，这是正确的。

真正的问题不是这个文件写得复杂，而是它提供了结构化上下文，调用处却继续把路径、行号塞进字符串。这样一来，异常对象有字段，系统里大部分错误仍然只能靠人眼读字符串。接口有了，纪律没跟上。

## Linus 三问

1. 这是个真问题吗？

是。VCG 是代码生成工具，失败时必须知道是文件问题、解析问题、语法问题还是运行时问题。否则上层无法给 CLI、日志、测试和后续工具提供稳定语义。

2. 有更简单的方法吗？

有，而且当前已经接近最简单：一个基类加四个语义子类。不要继续加更多异常类。下一步应该是让现有字段被调用处稳定使用，而不是再扩展层级。

3. 会破坏什么吗？

当前实现没有破坏老的 `Error("message")` 用法：`super().__init__(message)` 保留了 `args == ("message",)`，`str()` 在没有上下文字段时仍只返回 message。风险在后续迁移：如果调用处继续写 `VCGParseError("... at line 4", lineno=4)`，输出会重复位置。这不是现在的破坏，但很容易被后续半吊子迁移引入。

## 关键洞察

- 数据结构：异常的核心数据应该是“类型 + message + 可选位置上下文”。当前文件把这个模型表达出来了，但仓库多数 raise 点仍然只生产字符串。
- 复杂度：`location` 和 `__str__` 的复杂度可接受；这个模块没有深嵌套，也没有离谱抽象。
- 风险点：`VCGSyntaxError` 是公开 API，但生产代码零处 raise。这个类型现在靠测试和 manager 的透传分支维持存在感，不靠真实语义存在。
- 兼容性：关键兼容点做对了。`message` 是 keyword 前的唯一位置参数，新增上下文全是 keyword-only，这就是不破坏用户的写法。

## 按严重度排序的问题

### P1：结构化字段基本没被生产代码使用，接口价值被浪费

证据：

- `src/vcg_exceptions.py:48-51` 定义了 `path`、`lineno`、`column`、`snippet`。
- 生产代码里真正用 `path=` 的只有 `vcg.py:95`。
- 大部分调用仍把位置拼进 message：`src/vcg_file_processor.py:199`、`src/vcg_file_processor.py:220`、`src/vcg_file_processor.py:228`、`src/VerilogPreprocess.py:193`、`src/VerilogPreprocess.py:212`、`src/VerilogParser.py:82-86`。

这就是半套结构化异常。对象有字段，但调用方拿不到可靠字段，只能解析字符串。更糟的是，将来如果有人逐步迁移，最容易出现“message 里一份路径，字段里又一份路径”的重复输出。

正确方向不是改 `vcg_exceptions.py`，而是规定 raise 点：message 描述错误，path/lineno/column/snippet 放字段。比如文件读失败应该是 `VCGFileError("Verilog file not found", path=filepath)`，不是 `VCGFileError(f"Verilog file not found: {filepath}")`。

### P1：`VCGSyntaxError` 是公开类型，但生产代码没有语义来源

证据：

- `src/vcg_exceptions.py:92-93` 定义 `VCGSyntaxError`。
- `rg` 结果显示生产代码零处 `raise VCGSyntaxError`；只有测试构造和 `src/vcg_wires_manager.py:72`、`src/vcg_instance_manager.py:87` 这类透传分支提到它。
- Parser 当前统一抛 `VCGParseError`：`src/VerilogParser.py:122-126`。

这不是立即 bug，但它是 API 噪音。一个公开异常类型如果没有明确抛出边界，调用方无法知道该 catch 哪个。语法错误到底是 `VCGParseError` 还是 `VCGSyntaxError`？现在答案是“文档说一套，代码做另一套”。

要么把 `VCGSyntaxError` 明确绑定到 lexer/parser 的 token/grammar 错误，要么承认它是保留类型并在文档里说清楚暂不由生产代码主动抛出。不要让调用方猜。

### P2：`__str__` 是展示逻辑，不是结构化输出协议

证据：

- `src/vcg_exceptions.py:75-81` 把 message、location、snippet 拼成字符串。
- `vcg.py:108-109` 直接把 `str(e)` 打到日志和 stderr。

这对 CLI 足够，但不要把它当机器接口。只要 `__str__` 格式被测试锁死，后续想调整 CLI 展示就会牵动异常类测试。现在 `tests/test_vcg_exceptions.py:59`、`tests/test_vcg_exceptions.py:66`、`tests/test_vcg_exceptions.py:73`、`tests/test_vcg_exceptions.py:80` 都在精确断言字符串。

这不致命，但测试重点有点歪。应该重点锁字段和兼容性，字符串只锁最小必要形状。CLI 格式应该由 CLI 层负责，不该让异常基类背展示格式的长期债。

### P2：`PathLike[str]` 类型注解偏窄，但实际运行没问题

证据：

- `src/vcg_exceptions.py:24` 从 `os` 导入 `PathLike`。
- `src/vcg_exceptions.py:48` 标注 `path: str | PathLike[str] | None`。

这能工作，但 `os.PathLike` 的泛型主要表示 `__fspath__` 返回类型。实际项目里 `pathlib.Path` 可以进来，`str(path)` 也能处理。问题只是类型表达有点装，价值不大。若要更正，直接用 `str | PathLike[str]` 也可以继续保留；别为这个小问题搞大动作。

## 改进方向

1. 保持当前异常层级，不要再加类。

   这套五类足够：`VCGError`、`VCGFileError`、`VCGParseError`、`VCGSyntaxError`、`VCGRuntimeError`。更多类型只会让 catch 分支变脏。

2. 制定 raise 点纪律。

   message 只写错误事实；`path`、`lineno`、`column`、`snippet` 放字段。先迁移最有价值的模块：`vcg_file_processor` 的 VCG 标记错误、`VerilogPreprocess` 的条件编译错误、`VerilogParser.parse_file` 的文件错误。

3. 给 `VCGSyntaxError` 一个真实边界。

   如果 lexer/parser 能区分 token/grammar 级错误，就在那里抛 `VCGSyntaxError`。如果暂时不做，就在该类 docstring 里明确“reserved for future lexer/parser syntax diagnostics”，并避免下游代码假装它已经会出现。

4. 不要让异常基类承担所有展示需求。

   `__str__` 保留简单、稳定、向后兼容即可。更丰富的 CLI 展示应该放在 CLI 或 logger formatter 层，直接读 `e.path`、`e.lineno`、`e.snippet`。

5. 测试应从字符串精确匹配转向字段契约。

   保留 `str(VCGFileError("missing")) == "missing"` 这个兼容性测试。对带上下文的异常，优先断言字段和 `location`，少锁完整 `__str__` 文案，避免未来展示格式被测试绑死。

## 结论

`src/vcg_exceptions.py` 当前实现是一个合格的基础设施模块：短、兼容、类型层级清楚。最大缺陷不在文件内部，而在系统还没按这个接口生产结构化错误。下一步别重写它，别扩异常树；把调用处的字符串错误改成字段错误，让这个接口真正开始干活。
