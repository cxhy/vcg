# vcg_exceptions.py Review

> 评审日期: 2026-04-21
> 评审人: Linus (代理)
> 文件路径: src/vcg_exceptions.py
> 文件规模: 38 行（含 23 行 license/header，实际有效 14 行）

## 品味评分
🟡 凑合

## 核心判断

这文件本身没什么"错"——5 个空 `pass` 类，挑不出 bug。问题在于"它装作建立了异常体系，实际什么都没建立"。`VCGError → File/Parse/Syntax/Runtime` 这套层级在 CLAUDE.md、PROJECT.md、agent skill 里被反复引用，被当成项目的纪律，但代码里：(1) `VCGSyntaxError` 在 src/ 中**从未被 raise，仅被 import**（`vcg_exceptions.py:33` 定义 → `vcg_execution_engine.py:30`、`vcg_instance_manager.py:29`、`vcg_wires_manager.py:30` 三个文件 import 它，零处使用）；(2) 全项目只有 **2 处** `except VCG*`（`vcg.py:96` 和 `vcg_wires_manager.py:79`），子类化的意义在 catch 端根本没兑现；(3) 异常本身不携带任何结构化上下文（file_path / lineno / snippet），下游被迫用 f-string 把信息塞进 `args[0]`，跟 CLAUDE.md 要求的"按类型分别处理后 re-raise"对接不上。

简言之：这不是异常体系，是 5 个名字。换不换无所谓，但被吹成"层级"就有问题。值不值得重写？**值，但不紧急**——10 分钟的事。

## 关键洞察

- **数据结构**: 异常即"标签 + 字符串"，没有携带 path/line/col/cause 字段。所有定位信息都丢进 f-string，调用方想拿 file_path 只能 `str(e)` 然后正则。这是 Python 1990 年代的写法。
- **复杂度**: 5 个类，零方法，零字段，零 docstring。复杂度本身是 0；问题是它假装提供了语义区分。
- **风险点**:
  1. `VCGSyntaxError` 是死代码——文档承诺它存在，源码从不抛它。任何依赖"捕获 VCGSyntaxError"的下游写法都是空操作。
  2. `vcg.py:76` 直接 `raise VCGError(f"File Missing: {file_path}")`——按层级设计应该是 `VCGFileError`。顶层入口都不遵守自己定的层级，这层级就是装饰品。
  3. 异常无字段意味着 i18n、结构化日志、CI 错误归类全部没法做。

## 致命问题（按严重度排序）

### P0
（无真 bug。空 pass 类不会自己崩。）

### P1
- **`VCGSyntaxError` 是死代码**（`vcg_exceptions.py:33`）。在 `vcg_execution_engine.py:30`、`vcg_instance_manager.py:29`、`vcg_wires_manager.py:30` 被 import 后从未 `raise`，从未 `except`。要么删掉，要么真用起来。文档把它列为正式异常类型是误导。
- **顶层入口违反自己的层级**（`vcg.py:76`）：文件不存在抛 `VCGError` 而非 `VCGFileError`。`vcg_file_processor.py:99`、`vcg_instance_manager.py:73`、`vcg_wires_manager.py:76` 都正确抛了 `VCGFileError`，唯独主入口走偏。要么是该层级根本没必要，要么是 `vcg.py` 没遵守。两边必须挑一个。
- **异常不携带结构化字段**。下游全部靠 `f"Cannot find Verilog File: {file_path}"`（`vcg_instance_manager.py:73`）、`f"Parse errors in {file_path}: {error_msg}"`（`vcg_wires_manager.py:93`）拼字符串。错误处理代码想拿 file_path 只能 `str(e).split(":")`——这是反模式。最低限度 `VCGFileError(message, *, path)`、`VCGParseError(message, *, path, lineno=None)`。

### P2
- **import 风格不一致**：`vcg.py:32` 用 `from vcg_exceptions import VCGError`（顶层 flat import），其他三个用 `from .vcg_exceptions import ...`（相对包 import）。同一个项目两种风格，PYTHONPATH 配置稍有不同就能制造 `ImportError` 或重复加载（`isinstance` 失败的经典坑）。
- **缺 `__all__`**。包暴露面隐式，IDE 自动补全和 `from vcg_exceptions import *` 行为不可控。对于一个被定位为"项目异常约定"的模块，这是失职。
- **零 docstring**。每个类一行 `pass`，连"什么时候抛我"都没说。CLAUDE.md 在外面写规范，源文件里却没有，最近的真相离调用方最远。
- **header 占文件 60%**。23 行 license + header 包 14 行代码。GPL header 没问题，但每个文件 23 行属于复制粘贴税。考虑统一收到 LICENSE 文件，源文件留 SPDX 一行（`# SPDX-License-Identifier: GPL-3.0-or-later`）。
- **没有 `cause` 链路语义约定**。项目里反复出现"`except Exception` 包装成 VCGParseError"踩坑（`bugfix_progress.md:17`、`decisions/2026-04-11_bugfix_and_agent_setup.md:19`）。如果异常基类强制要求 `raise VCGParseError(...) from e`，并在 `__init__` 里检查 `__cause__`，就能从源头堵这个坑。

## Linus 式改进方向

不要为了改而改，但既然你定位它是"项目异常约定"，就让它配得上这个名字。**40 分钟内可以全部做完**：

1. **删掉 `VCGSyntaxError`**（如果半年内不打算让 Lexer/Parser 真抛它的话）。死代码就是谎言。或者，立刻在 Parser 里把它用起来——`VerilogParser` 现在抛的 `VCGParseError` 实际上很多是**语法错误**（unexpected token），那才是 `VCGSyntaxError` 的归属。二选一。

2. **给基类加结构化字段，消灭 f-string 拼接**：
   ```python
   class VCGError(Exception):
       def __init__(self, message: str, *, path: str | None = None,
                    lineno: int | None = None) -> None:
           super().__init__(message)
           self.message = message
           self.path = path
           self.lineno = lineno

       def __str__(self) -> str:
           loc = f" [{self.path}:{self.lineno}]" if self.path else ""
           return f"{self.message}{loc}"
   ```
   下游 `raise VCGFileError("Cannot find Verilog file", path=file_path)`——比 f-string 干净，且 `e.path` 可被程序消费。

3. **统一 import 风格**：要么全 `from .vcg_exceptions`，要么全 `from vcg_exceptions`。修 `vcg.py:32`，并把 `vcg.py:76` 的 `VCGError(...)` 换成 `VCGFileError(...)`。

4. **加 `__all__` 和 docstring**：
   ```python
   __all__ = ["VCGError", "VCGFileError", "VCGParseError",
              "VCGSyntaxError", "VCGRuntimeError"]
   ```
   每个类一行 docstring 说明"何时抛我、谁负责处理"。

5. **License header 瘦身**：保留 LICENSE 文件，源码顶端只留 SPDX + Copyright 两行。少 20 行 × N 个文件 = 项目立刻好读一截。

6. **加一条不变量测试**：扫 `src/` 里所有 `raise VCG*`，断言没有人 `raise VCGError(...)`（应该用具体子类）。这种纪律靠人记是记不住的，靠测试强制才能维持。

不做这些也活得下去，但每次踩到 `bugfix_progress.md` 里那种"异常被错误包装"的坑，根因都在这文件——它没给下游任何结构化工具，只给了五个名字。
