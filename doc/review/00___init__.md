# Linus 技术评审: `src/__init__.py`

> 评审范围: 仅 `src/__init__.py`
> 上下文读取: `CLAUDE.md`, `PROJECT.md`, `pyproject.toml`, 根入口 `vcg.py`, 关键 `src.*` 调用处
> 文件状态: 0 字节空文件

## 品味评分

🟡 凑合。

空 `__init__.py` 本身没犯罪。它没有副作用、没有隐式 import、没有启动日志、没有版本探测，这一点是对的。Python 包初始化文件最容易被人塞垃圾进去，这个文件至少没有犯那个错。

但它也不是好品味。它把 `src` 这个目录名变成了运行时包名，而项目名是 `vcg`。这不是 `__init__.py` 一行代码的问题，是包边界设计的问题。空文件只是把这个设计固定下来了。

## 核心判断

✅ 值得保留空文件，不值得往里面加导出。

理由很简单：当前代码已经依赖 `src` 是一个包。根入口 `vcg.py` 使用 `from src.vcg_file_processor import VCGFileProcessor`，`src/` 内部模块使用相对 import，例如 `from .vcg_execution_engine import VCGExecutionEngine`。删掉这个文件或随手改包初始化，会直接破坏 import 路径。现在最好的局部选择就是保持它无副作用。

真正该讨论的是长期包名：`src` 不应该是公开运行时 API 名。项目叫 `vcg`，用户和测试却在 import `src.VerilogParser`。这会污染接口认知，也会让后续 packaging 变得别扭。但这个问题不能靠在 `__init__.py` 里塞一堆 re-export 解决。

## Linus 三问

1. 这是个真问题还是臆想出来的？

   文件为空不是问题。`src` 被当成包名才是真问题，而且已经真实存在：入口和测试都在依赖 `src.*`。

2. 有更简单的方法吗？

   有。局部保持空文件；长期如果要整理包结构，就把真正包名改成 `vcg`，入口放到 `vcg.__main__` 或 `vcg.cli`，不要让 `src` 暴露为用户可见 import 名。

3. 会破坏什么吗？

   会。删除这个文件、改成动态 import、或者在里面批量 re-export 模块，都可能破坏相对 import、增加循环 import 风险，或者把内部模块错误地承诺成公共 API。

## 关键洞察

- 数据结构: 这里没有业务数据结构，只有包命名边界。当前事实是 `src` 目录既是源码目录，又是 Python package。
- 复杂度: 空文件复杂度为零，这是优点。任何自动导入子模块、`__all__` 聚合、版本读取，都会把零复杂度变成启动时副作用。
- 风险点: 最大风险不是空文件，而是把 `src.*` 变成外部可见接口后难以迁移到正常包名。

## 问题列表

### P2: 运行时包名是 `src`，不是项目名 `vcg`

位置: `src/__init__.py:1`

这个空文件让 `src` 成为包。结合根入口 `vcg.py` 的 `from src...` 和测试里的 `from src.VerilogParser...`，项目的实际 import surface 变成了 `src.*`。这很难看。

用户安装一个叫 `vcg` 的项目，却要 import `src.VerilogParser`，这是接口层面的坏味道。它还会让后续发布包时出现两套命名认知：distribution name 是 `vcg`，package name 是 `src`。

严重度不是 P0，因为当前代码靠它工作；也不是 P1，因为没有直接运行时 bug。它是架构债，别在这个文件里打补丁。

### P3: 空文件没有说明它是刻意的包标记

位置: `src/__init__.py:1`

0 字节文件本身可以接受，但读代码的人不知道它是遗留空文件，还是刻意要求 `src` 作为 package。考虑到 `PROJECT.md` 已经记录了包/CLI import 路径曾经被修过，这里缺一个极短注释会增加误删风险。

但这只是维护性问题。不要为了这个问题写半页 docstring，更不要导入任何模块。

## 改进方向

1. 现在不要动源码。保持 `src/__init__.py` 空或近似空，避免包初始化副作用。
2. 如果要加说明，只允许加一两行模块 docstring，说明它是 package marker，不导出公共 API。
3. 不要在这里写 `from .VerilogParser import VerilogParser` 这类聚合导出。那会把内部模块加载顺序、PLY 初始化、异常类、logger 全绑到 package import 上，制造循环 import 和启动成本。
4. 长期正确方向是改包结构：把运行时包从 `src` 迁到 `vcg`，保留 CLI 入口兼容层。那是单独任务，不是 `__init__.py` 的局部修补。

## 结论

这个文件本身没 bug。它的最佳实现接近于“什么都不做”。坏味道来自项目把 `src` 当包名，而不是来自空文件内容。

当前建议：保留，不加导出；长期做一次明确的 package rename 设计。
