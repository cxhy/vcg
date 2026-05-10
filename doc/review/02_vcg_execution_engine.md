# src/vcg_execution_engine.py Linus 技术评审

## 评审范围

- 主文件：`src/vcg_execution_engine.py`
- 只读上下文：`CLAUDE.md`、`PROJECT.md`、`src/vcg_file_processor.py`、`src/vcg_rule_manager.py`、`src/vcg_instance_manager.py`、`src/vcg_wires_manager.py`、`src/VerilogParser.py`、`tests/test_vcg_execution_engine.py`、`tests/test_vcg_file_processor.py`
- 未修改源码，未提交 git。

## 品味评分

黄：凑合，6/10。

这个文件已经不是旧版那种一把 `except Exception` 把所有 VCG 错误抹平的烂东西。150 行内完成执行上下文、规则生命周期、输出收集和路径展开，结构能看，职责也基本清楚。

但它还有两个硬伤：输出数据结构错了，导致 `print(..., end='')` 生成错误文本；路径基准目录不属于 engine，逼得调用方 monkey patch `expand_path()`。这不是风格问题，是数据所有权没想清楚。

## 核心判断

值得继续收敛，不需要推倒重写。

`VCGExecutionEngine` 的本质只有一句话：执行可信 Python DSL，把 `Connect` 规则喂给 manager，把 `Instance/WiresDef/print` 的文本按顺序吐出来。这个抽象是对的。问题是当前实现把“输出流”伪装成“按行片段列表”，又把“路径解析基准”藏在外部补丁里。把这两个数据模型修正，代码会更短、更稳定。

## Linus 三问

1. 这是个真问题吗？

是。这个文件是 VCG 块的执行边界。它的错误会直接污染生成 Verilog，或者让 CLI/上层工具拿到错误的异常类型。

2. 有更简单的方法吗？

有。输出用真正的 stream buffer，不要靠 `'\n'.join()` 猜 print 语义；路径基准用 `base_dir` 作为构造参数，不要改实例方法；Python 语法错误直接映射到 `VCGSyntaxError`。

3. 会破坏什么吗？

修 `print` 会改变依赖错误换行行为的脚本，但那是 bug 兼容，不该保护。加 `base_dir=None` 可以保持老接口不变。异常细分只会让调用方拿到更准的类型，不会破坏 `except VCGError`。

## 关键洞察

- 数据结构：输出应该是字节/字符串流，不是“已经归一化的一段段行”。`OrderedOutputManager.outputs: list[str]` 加 `'\n'.join()` 无法表达 `end=''`、`end='\n\n'`、尾随空格这些 print 语义。
- 复杂度：当前大部分代码是简单的，真正的复杂度来自两个补丁式特殊情况：`_normalize_print_output()` 猜测空白输出，以及外部替换 `expand_path()`。
- 风险点：执行上下文对用户暴露的是 Python。只要签名里接受 `print(..., end=...)`，就必须按 Python 语义工作，不能生成“看起来差不多”的文本。

## 按严重度排序的问题

### P1：`print` 输出模型会直接生成错误文本

位置：`src/vcg_execution_engine.py:34-42`、`src/vcg_execution_engine.py:133-147`

`OrderedOutputManager.get_final_output()` 永远用 `'\n'.join(self.outputs)` 拼片段。`_print()` 每次调用都把文本归一化成一个独立片段。结果是连续 no-newline print 被硬塞换行：

```python
engine.execute("print('a', end=''); print('b', end='')")
```

Python 语义应该是 `ab`。当前结构会得到 `a\nb`。同类问题还包括：

- `print('a', end=' ')` 的尾随空格被 `text.rstrip()` 吃掉。
- `print('a', end='\n\n')` 的额外空行被吃掉。
- whitespace-only 输出被当成空行处理，而不是保留实际空白。

这不是小毛病。VCG 是代码生成器，输出文本就是产品。输出缓冲的数据结构错了，测试只覆盖了单个 `end=''`，没覆盖连续 print，所以漏了。

### P1：Python DSL 语法错误被错误归类为 runtime

位置：`src/vcg_execution_engine.py:30`、`src/vcg_execution_engine.py:84`、`src/vcg_execution_engine.py:88-92`

文件 import 了 `VCGSyntaxError`，也承诺透传它，但 engine 自己从不产生它。`exec(python_code, context)` 遇到 Python 语法错误时抛 `SyntaxError`/`IndentationError`，当前会被 `except Exception` 包成 `VCGRuntimeError("Exec Error: ...")`。

这破坏了异常层级的语义。VCG block 写成非法 Python 是源码语法错误，不是运行时错误。上层如果要区分“脚本写错”和“脚本运行时 NameError/TypeError”，现在做不到。

正确边界很简单：`except SyntaxError as e: raise VCGSyntaxError(..., lineno=e.lineno, column=e.offset, snippet=e.text) from e`。已经有结构化异常字段，不用继续把信息塞进字符串。

### P2：路径基准目录的数据所有权在 engine 外面

位置：`src/vcg_execution_engine.py:56`、`src/vcg_execution_engine.py:63-73`

`expand_path()` 默认按进程 cwd 解析相对路径，但真实 VCG 文件处理需要按被处理文件所在目录解析。由于 engine 构造函数没有 `base_dir`，调用方只能在 `src/vcg_file_processor.py:142-149` 给实例 monkey patch 一个新的 `expand_path()`。

这说明数据模型错了。路径解析基准是 execution engine 执行 DSL 所需的上下文数据，不应该靠替换方法传进去。更糟的是，engine 自带的 `expand_path()` 会检查空路径和不存在文件；外部替换版本的语义并不完全一致。今天测试能过，是因为下游 parser 还会失败，不是因为边界干净。

把 `base_dir: Path | None = None` 放进 `VCGExecutionEngine.__init__()`，让 `expand_path()` 自己处理 cwd/base_dir/exists/fail-fast。不要用 monkey patch 传业务数据。

### P3：每个 engine 都急切创建两个 manager 和两个 parser

位置：`src/vcg_execution_engine.py:57-60`

构造 engine 时立即创建 `WiresManager` 和 `InstanceManager`。这两个 manager 又各自创建 `VerilogParser`。即使 VCG block 只做 `print()` 或只注册规则，也会先付这笔成本。

这不是当前最要命的问题，但味道不好。VCGFileProcessor 每个 block 创建一个 engine；block 多了以后，这种急切初始化会变成无意义开销。`InstanceManager` 和 `WiresManager` 可以按第一次调用 `_instance()` / `_wires_def()` 时 lazy 创建。

## 改进方向

1. 先修输出模型。

   用 `io.StringIO` 或等价的 raw fragment buffer 表达输出流。`_print()` 直接把 native print 写入 buffer；`_add_generated_output()` 作为块级 emit，明确何时补分隔换行。不要再用 `rstrip()` 猜用户想要什么。

2. 给 Python 语法错误一个真实类型。

   在 `execute()` 里先捕获 `SyntaxError`，包装成 `VCGSyntaxError`，带上 `lineno`、`column`、`snippet`。现有 VCG 异常继续透传，未知运行时异常再包 `VCGRuntimeError`。

3. 把路径基准放回 engine。

   `VCGExecutionEngine(macros=None, base_dir=None)`。相对路径按 `base_dir` 解析；没有 `base_dir` 时保留当前 cwd 行为；空路径和不存在文件都在同一个 `expand_path()` 里 fail-fast。然后删掉调用方对 `expand_path()` 的方法替换。

4. 再考虑 lazy manager。

   这一步不是 P1。等输出和路径边界干净后，再把 `InstanceManager` / `WiresManager` 延迟创建，避免为了简单 VCG block 建 parser。

5. 补测试时别测实现细节，测语义。

   至少补三个用例：连续 `print(..., end='')` 不插入换行；`print(..., end='\n\n')` 保留空行；非法 Python DSL 抛 `VCGSyntaxError` 而不是 `VCGRuntimeError`。
