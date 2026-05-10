# src/vcg_logger.py Linus 风格技术评审

> 范围: 只评审 `src/vcg_logger.py`。上下文参考 `CLAUDE.md`、`PROJECT.md`、`vcg.py`、`src/vcg_file_processor.py`、`tests/test_vcg_logger.py` 和相关 logger 调用处。

## 品味评分

🟡 **凑合，偏上。**

之前那种 Java 式 `VCGLoggerManager` 单例壳子已经砍掉了，这是对的。当前文件的主体已经变成了 Python logging 应有的样子：模块级 root logger、ContextVar 文件上下文、handler 工厂函数。它能用，也不算丑。

但还没干净。最大的臭味是 logging level 的数据模型没理顺：文件 handler 声称 DEBUG，父 logger 却用用户选择的 level 先过滤。另一个问题是兼容 API `set_file_context/clear_file_context` 自己维护 token 栈，和 `file_context()` 形成两套状态入口。能工作，但这是残留复杂度，不是好品味。

## 核心判断

✅ **值得继续小修，不值得大重写。**

这是日志基础设施，用户侧 API 已经很小：`setup_vcg_logging()`、`get_vcg_logger()`、`file_context()`，外加旧兼容的 `set_file_context()` / `clear_file_context()`。不要再搞类、manager、配置对象之类的玩具。真正要修的是 level 语义和状态入口，把行为变成一眼能推导出来。

## Linus 三问

1. **这是个真问题还是臆想出来的？**
   真问题。`src/vcg_logger.py:107` 把文件 handler 设成 DEBUG，但 `src/vcg_logger.py:123` 把父 logger 设成用户指定 level。Python logging 先过 logger level，再到 handler level，所以 log 文件不会按代码暗示记录 DEBUG 全量日志。这会直接影响排错。

2. **有更简单的方法吗？**
   有。root logger level 固定放宽到 `DEBUG`，用 handler level 控制 console 和 file；或者明确改成"文件也遵守全局 level"，删掉 `_create_file_handler()` 里的 DEBUG 假象。二选一，别写两套互相打架的规则。

3. **会破坏什么吗？**
   不能破坏现有调用方的 5 个公开函数。尤其 `VCGFileProcessor` 已经用 `file_context()`，旧的 `set_file_context/clear_file_context` 可能还有外部脚本在用。修法必须保留签名，内部收敛状态模型。

## 关键洞察

- **数据结构**: 核心状态只有两个：`logging.Logger('VCG')` 和 `ContextVar[Optional[str]]`。handler 引用只是缓存，不该成为第二套真相。
- **复杂度**: 当前 150 行可以接受，但 `_console_handler/_file_handler`、`_file_context_tokens`、三个 formatter 里有残余复杂度。不是灾难，但有减法空间。
- **风险点**: 最大风险不是崩溃，而是日志语义撒谎。用户以为开了 `--log-file` 就有 DEBUG 现场，实际父 logger 早把 DEBUG 扔掉了。

## 问题清单

### P1 - 文件日志 DEBUG 语义是假的

`src/vcg_logger.py:107`:

```python
handler.setLevel(logging.DEBUG)
```

`src/vcg_logger.py:123`:

```python
_VCG_LOGGER.setLevel(resolved_level)
```

这是 logging 模型的基本错误。logger level 是第一道门，handler level 是第二道门。默认 `level=logging.WARNING` 时，`VCG.*` 子 logger 的 DEBUG/INFO 记录根本到不了 file handler。于是文件 handler 的 DEBUG level 只是摆设。

这会破坏 debug 可用性。`VerilogParser`、`RuleManager`、`InstanceManager` 里大量 DEBUG 日志，本来最适合进文件；结果用户不开全局 DEBUG，文件里也看不到。代码看起来像"文件全量，控制台按级别"，实际不是。

**修法**: 选一个明确语义：

1. 如果 log file 应该保存完整现场：`_VCG_LOGGER.setLevel(logging.DEBUG)`，console handler 用 `resolved_level`，file handler 用 DEBUG。
2. 如果 log file 应该跟随用户 level：把 `handler.setLevel(logging.DEBUG)` 改成传入 `resolved_level`，别假装全量记录。

我倾向第一种。日志文件的价值就是事后诊断，控制台才需要安静。

### P2 - 兼容的 set/clear API 重新发明了一套 context manager

`src/vcg_logger.py:133-144` 维护 `_file_context_tokens` 栈：

```python
token = current_file_context.set(_context_value(file_path))
_file_context_tokens.set((*_file_context_tokens.get(), token))
```

这比 `file_context()` 难读，也更容易误用。`file_context()` 是正确模型：set 拿 token，finally reset。`set_file_context/clear_file_context` 是为了兼容留下的手动 push/pop，但它让同一个状态有两套生命周期管理方式。

更糟的是 `clear_file_context()` 在 token 栈为空时直接 `current_file_context.set(None)`，没有 reset token。这虽然能把当前值清空，但它绕过了 ContextVar 的回滚语义。对命令行单线程场景大概率没事，对嵌套或异步上下文就是不干净。

**修法**: 保留函数签名，但文档上标为 legacy。内部可以继续 push/pop token，但 `clear_file_context()` 空栈时不要制造新 token；要么无操作，要么明确 reset 到默认值并接受这是 legacy 行为。更好的方向是全仓只使用 `with file_context(...)`，旧 API 只给外部兼容。

### P2 - `_coerce_level()` 静默吞掉非法 level

`src/vcg_logger.py:66-69`:

```python
return getattr(logging, level.upper(), logging.INFO)
```

非法字符串变 INFO。这种"宽容"不是好事。用户拼错 `--log-level DEBG`，程序不会报错，而是悄悄变成 INFO。CLI 现在 argparse 限制了 choices，但 `setup_vcg_logging()` 是公开函数，测试或外部脚本可以直接传错。

**修法**: 对未知字符串抛 `ValueError`。如果要兼容旧行为，至少别回退到 INFO，回退到 WARNING 还稍微接近默认值。但最干净的是失败要响。

### P3 - handler 全局缓存没有实际价值

`src/vcg_logger.py:38-39` 和 `src/vcg_logger.py:118-130`:

```python
_console_handler: Optional[logging.Handler] = None
_file_handler: Optional[logging.Handler] = None
```

这些变量只在 `setup_logger()` 里赋值，没有被其他逻辑读取。真正的 handler 所有权在 `_VCG_LOGGER.handlers`。缓存引用只是第二份状态，增加了"到底谁拥有 handler"的问题。

**修法**: 删掉 `_console_handler/_file_handler`，让 `_VCG_LOGGER.handlers` 成为唯一真相。`_close_handlers(_VCG_LOGGER)` 已经按这个模型写了。

### P3 - formatter 的空格会产生双空格

`src/vcg_logger.py:55`:

```python
'[VCG-%(levelname)s] %(file_context)s %(name)s: %(message)s'
```

没有 file context 时 `%(file_context)s` 是空字符串，输出会变成 `]  VCG.Main:`，中间两个空格。不是功能 bug，但这是日志门面，粗糙会降低排错时的信噪比。

**修法**: 让 `file_context` 包含尾随空格，格式串里只放一个占位符；或者用 filter 在 record 上生成完整 prefix。

### P3 - 公开函数缺类型返回

`src/vcg_logger.py:149`:

```python
def setup_vcg_logging(**kwargs):
```

这个函数只是兼容别名，但没有返回类型，也没有参数约束。小问题，但这个项目已经开始使用类型注解，基础设施 API 不该拖后腿。

**修法**: `def setup_vcg_logging(**kwargs) -> None:`。如果以后要更严格，再把 kwargs 展开成和 `setup_logger()` 一样的签名。

## 改进方向

1. **先修 level 数据模型**。这是唯一接近 bug 的点。明确文件日志到底是 DEBUG 全量还是跟随全局 level，然后用 logger level + handler level 正确表达。
2. **把 handler 所有权收敛到 `_VCG_LOGGER.handlers`**。删掉 `_console_handler/_file_handler` 这两个没用缓存。
3. **把 `set_file_context/clear_file_context` 降级成 legacy API**。内部尽量别再扩散，主路径统一使用 `file_context()`。
4. **非法配置要失败，不要猜**。`_coerce_level()` 不该把未知 level 变成 INFO。
5. **清理日志格式细节**。去掉无 context 时的双空格，给公开别名补类型。

一句话：这文件已经从"过度设计"回到了"能用的基础设施"，但还没到好品味。剩下的问题不是行数多，而是状态模型还在撒谎：handler 说 DEBUG，logger 不让 DEBUG 通过；context manager 是正路，旁边又留一套手动 token 栈。把这两件事收敛掉，代码就基本干净了。
