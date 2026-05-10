# src/vcg_file_processor.py Linus 风格技术评审

文件路径: `src/vcg_file_processor.py`

## 品味评分

🟡 **凑合。**

旧版最蠢的全局 `os.chdir`、可变 `VCGBlock`、重复插入生成块问题已经被修掉了。现在这份代码的主流程能看，状态机也比以前诚实。但它还没有到"好品味"：文件处理器和执行引擎之间靠 monkey patch 改方法，异常类型在边界处被揉烂，marker 识别仍然靠子串匹配。这不是灾难，但也不是干净的核心编排器。

## 核心判断

✅ **值得继续修。**

这个文件是 VCG 的主编排器：读 Verilog、提取 VCG 块、执行 Python DSL、把生成内容写回原文件。它的错误语义和写回行为直接决定用户会不会丢文件、能不能定位错误。当前实现已经可用，但边界契约不够硬，尤其是执行阶段异常包装和路径解析覆盖，后面会让 CLI、测试和用户诊断看到错误的故障类型。

## Linus 三问

1. **这是个真问题还是臆想？**
   真问题。`VCGExecutionEngine.execute()` 明确把 `VCGFileError`、`VCGParseError`、`VCGSyntaxError` 作为语义异常透传，但 `VCGFileProcessor._execute_blocks()` 又把其中大部分重新包成 `VCGRuntimeError`。这会真实影响上层错误分类。

2. **有更简单的方法吗？**
   有。不要在 file processor 里 monkey patch `execution_engine.expand_path`。路径解析应该是一个明确依赖：构造 engine 时传入 `base_dir`，或者让 engine 的 `expand_path()` 接受可配置 root。异常透传也只需要补齐 VCG 异常类型，不需要新架构。

3. **会破坏什么吗？**
   修异常类型可能改变 CLI/测试看到的错误类，但这是收紧到项目自己的异常层级，不是破坏用户空间。真正要谨慎的是 marker 识别规则：如果历史上允许 `foo //VCG_BEGIN` 这种内联 marker，改成整行匹配会改变行为，需要先明确兼容策略。

## 关键洞察

- **数据结构**: `VCGBlock` / `ExecutedBlock` 分离是对的，生成内容不再回填到块对象。`gen_start_line` / `gen_end_line` 把"扫描结果"放在块上，也比双计数器同步强。
- **复杂度**: `_extract_vcg_blocks()` 拆成 helper 后没有深缩进，但状态仍然是四五个字段协同变化。根因是 marker 事件没有建模，只靠每行顺序 if 分派。
- **风险点**: 最高风险不是状态机，而是跨模块契约被 file processor 偷偷改写。`_bind_file_relative_paths()` 覆盖了 engine 的 `expand_path()`，同时漏掉 engine 自带的空路径和存在性校验。

## 问题列表

### P1: `_execute_blocks()` 把有语义的 VCG 异常错误包装成运行时异常

位置: `src/vcg_file_processor.py:130-135`

`VCGExecutionEngine.execute()` 在 `src/vcg_execution_engine.py:88-92` 已经明确透传 `VCGFileError`、`VCGParseError`、`VCGSyntaxError`、`VCGRuntimeError`。但 file processor 这里只透传 `VCGRuntimeError`，其他 VCG 异常会落入 `except Exception`，再被包装成 `VCGRuntimeError("Exec Error: ...")`。

这很糟糕：缺文件不是运行时 Python 错误，Verilog 语法错也不是运行时 Python 错误。项目异常层级存在的意义就是让调用方知道问题属于文件、解析、语法还是执行。这里直接把类型信息打碎。

改法很简单：导入并透传完整 VCG 异常集合，或者直接捕获基类 `VCGError` 透传。不要在 orchestration 层重写已经有语义的异常。

### P1: `_bind_file_relative_paths()` 的 monkey patch 破坏了 `expand_path()` 原始契约

位置: `src/vcg_file_processor.py:142-149`，对照 `src/vcg_execution_engine.py:63-73`

执行引擎原本的 `expand_path()` 会做两件重要事情：

- 空路径直接抛 `VCGFileError("Empty file path")`
- 解析后的路径不存在直接抛 `VCGFileError`

file processor 用 `MethodType` 覆盖以后，这些校验没了。`Instance("")` 会被解析成被处理文件所在目录，`Instance("missing.v")` 会把错误推迟到更深的 parser/manager 层，然后再被上面的 P1 包成 `VCGRuntimeError`。这是典型的"为了修相对路径，把已有契约顺手弄坏"。

这不是好抽象。相对路径 root 应该是 execution engine 的显式状态，不该靠运行时替换方法。短期至少要让覆盖版 `expand_path()` 保持和原方法相同的空路径、存在性校验。

### P2: marker 识别靠子串匹配，合法 Verilog 内容可能被误判成控制标记

位置: `src/vcg_file_processor.py:176-189`, `src/vcg_file_processor.py:197-203`

当前代码用 `if self.VCG_BEGIN in line`、`if self.VCG_GEN_END in line` 这类子串判断。只要 Verilog 字符串、普通注释或生成内容里出现 `//VCG_BEGIN` / `//VCG_GEN_END`，扫描器就会把它当控制结构。

这类 sentinel 格式本来就脆弱，更不该扩大匹配范围。控制 marker 至少应该是"可选空白 + 精确 marker + 可选空白/行尾"这种行级语义。现在的宽匹配把数据内容和控制语法混在一起。

兼容风险在这里：如果历史文件依赖内联 marker，直接改会破坏行为。所以这项要先定规则，再加测试。

### P2: `_write_file()` 直接覆盖源文件，没有原子写回保护

位置: `src/vcg_file_processor.py:111-116`

这个工具不是写缓存文件，它在改用户的 Verilog 源文件。`Path.write_text()` 直接打开目标写入，进程中断、磁盘错误、同步工具冲突时可能留下半截文件。对代码生成器来说，这是坏味道。

最朴素的做法：写同目录临时文件，flush 后 `replace()`。同目录保证同文件系统 rename，失败时原文件大概率还在。别搞复杂事务，别引入数据库，简单原子替换就够。

### P3: `_BlockScanState` 是一包可变字段，状态转移没有集中约束

位置: `src/vcg_file_processor.py:51-60`, `src/vcg_file_processor.py:165-268`

现在的状态机能工作，但状态字段太散：`in_vcg_block`、`current_block_lines`、`start_line`、`in_gen_block`、`gen_start_line`、`gen_block_id` 彼此有隐含约束。例如 `in_vcg_block=True` 时 `current_block_lines` 应该不是 `None`，`in_gen_block=True` 时 `gen_block_id` 应该不是 `None`。代码靠人工维护这些不变量。

这不是当前最大问题，因为测试覆盖了不少非法 marker。但从品味上说，状态应该更少：一个 `mode` 枚举加当前 open block/gen id，比多个 bool 更难写出矛盾状态。

### P3: `macros` 没有类型标注，边界契约继续含糊

位置: `src/vcg_file_processor.py:71-72`

CLI 现在传的是 `dict[str, str] | None`，execution engine 也把它传给下游 parser/manager。file processor 作为中间层还写 `macros=None`，这不是 bug，但这是接口懒惰。这个项目已经在 `CLAUDE.md` 里要求清晰异常层级和类型契约，这里应该跟上。

## 改进方向

1. **先修异常语义。**
   `_execute_blocks()` 透传完整 VCG 异常，不要把文件/解析/语法错误包装成 runtime error。补一个通过 `VCGFileProcessor.process_file()` 调用 `Instance("missing.v", ...)` 的测试，断言仍是 `VCGFileError`。

2. **把路径 root 变成显式数据，不要 monkey patch 方法。**
   最好让 `VCGExecutionEngine` 接受 `base_dir: Path | None`，`expand_path()` 自己处理相对路径、空路径、存在性检查。短期不改 engine 的话，也要让 `_bind_file_relative_paths()` 的覆盖函数复制原始校验。

3. **收紧 marker 语法。**
   用正则表达式统一识别整行 marker：`^\s*//VCG_BEGIN\s*$`、`^\s*//VCG_GEN_BEGIN_(\d+)\s*$` 这类。先确认是否需要兼容内联 marker；如果不需要，直接删掉子串匹配。

4. **写回用临时文件 + replace。**
   代码生成器不能随便把源文件截断。这个改动很小，收益很实际。

5. **把扫描状态减成一个模式。**
   不急，但应该做。`mode = NORMAL | VCG | GEN` 加上当前 payload，比两个 bool 加一堆 nullable 字段更容易维护。

## 总结

这份文件已经从"危险"变成"能用但边界脏"。真正要打掉的是两个坏习惯：在编排层改写下游对象方法，以及在边界处把有意义的异常类型重新糊成一个大类。先把数据契约和异常契约修硬，再谈状态机优雅。
