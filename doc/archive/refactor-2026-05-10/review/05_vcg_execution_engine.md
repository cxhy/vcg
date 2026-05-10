# vcg_execution_engine.py Review

> 评审日期: 2026-04-21
> 评审人: Linus (代理)
> 文件路径: src/vcg_execution_engine.py
> 文件规模: 156 行

## 品味评分
🟡 凑合

文件本身不长，结构清晰，没有什么"看一眼就想吐"的代码。但从 Linus 的标准看，里面充满了"为了抽象而抽象"和"懒得想数据结构"的味道。可工作，但不优雅。

## 核心判断

值得改：是。这是 VCG 项目的核心入口，安全语义和异常处理一旦埋雷，影响全链路。

不要重写：架构方向没问题（DSL 函数 + exec 执行 + Output 收集器），改动应该集中在三件事：
1. 把 `OrderedOutputManager` 三个 `add_*` 合并成一个；
2. 把 6 个 `_create_*_func` 闭包工厂的脚手架去掉；
3. 把 `execute()` 里的 `except Exception` 吞类型问题修掉。

## 关键洞察

- **数据结构**: `OrderedOutputManager.outputs: List[str]` 这个数据结构本身没问题，但暴露的接口是错的。三个 `add_*_output` 在做同一件事——把字符串加到列表里。它们之所以看起来不同，是因为 `add_text_output` 混入了一段 print 输出格式化逻辑。这是层次错位：格式化应该在 print wrapper 里完成，Manager 只负责"加进去"。
- **复杂度**: 6 个 `_create_*_func` 全部是同一个套路——"def 一个内部函数，立刻 return"。除了 `Instance` 和 `WiresDef` 各自带两行副作用（`add_*_output` + `rule_manager.reset()`），其余 4 个都是 1 行透传。这是 5 倍于必要的样板代码。直接用 `self.fn` 作为 method，或者在 `_create_execution_context` 里写 lambda 即可。
- **风险点**:
  1. `execute()` 的 `except Exception` 把 `VCGRuntimeError`/`VCGSyntaxError`/`VCGFileError`/`VCGParseError` 全部包成 `VCGRuntimeError`——明明 import 了这 4 个类型，却一个都不用。这不是异常处理，这是异常"擦除"。
  2. `__builtins__` 直接灌给用户脚本，意味着用户在 `//VCG_BEGIN` 块里能 `open()`、`__import__('os').system()`、`exec()`。如果项目定位不只是本地工具，这是设计级安全洞。即使是本地工具，也应在 docstring 里写明"用户脚本拥有完整 Python 权限"。
  3. `expand_path` 用 `Path.resolve()`——在 Windows 上对不存在的路径行为依赖 Python 版本。

## 致命问题（按严重度）

### P0

**1. 异常吞类型** — `vcg_execution_engine.py:88-90`

```python
except Exception as e:
    self.logger.error(f"Execution error: {str(e)}")
    raise VCGRuntimeError(f"Exec Error: {str(e)}")
```

Import 了 4 种异常 (`vcg_execution_engine.py:30`)，一种都没分别处理。用户脚本里抛 `VCGFileError`（找不到 Verilog 文件），上层只看到 `VCGRuntimeError("Exec Error: ...")`。错误类型信息被字符串化丢光，调用方无法做精确捕获。

正确做法：让 VCG 自己的异常透传，只包装真正的 Python 异常（`SyntaxError`/`NameError`/`TypeError` 等）。

```python
except (VCGFileError, VCGParseError, VCGSyntaxError, VCGRuntimeError):
    raise
except Exception as e:
    raise VCGRuntimeError(f"Exec Error: {e}") from e
```

注意 `from e` —— 现有代码连 traceback chain 都丢了。

### P1

**2. 三个 `add_*_output` 的特殊情况是假的** — `vcg_execution_engine.py:37-52`

```python
def add_text_output(self, text: str):
    if text == '\n':
        self.outputs.append('')
    elif text.strip():
        self.outputs.append(text.rstrip())
    elif text and not text.strip():
        if '\n' in text:
            self.outputs.append('')

def add_instance_output(self, instance_code: str):
    if instance_code.strip():
        self.outputs.append(instance_code)

def add_wires_output(self, wires_code: str):
    if wires_code.strip():
        self.outputs.append(wires_code)
```

`add_instance_output` 和 `add_wires_output` 一字不差。这是教科书级"复制粘贴写完忘了 refactor"。

`add_text_output` 那一坨 if/elif 是因为 print 的 `end='\n'` 行为被透传到这里——分类 4 种情况：纯换行、有内容、空白含换行、其他。这个分类应该在 `custom_print` 里处理掉，Manager 只接收"已规范化的一行字符串"。

好品味写法：

```python
class OrderedOutputManager:
    def __init__(self):
        self.outputs: list[str] = []

    def add(self, text: str) -> None:
        if text:
            self.outputs.append(text.rstrip())

    def get_final_output(self) -> str:
        return '\n'.join(self.outputs)
```

`custom_print` 里把 `\n`-only 输入转成 `''` 即可。三个方法变一个，无 if/elif 链。

**3. 6 个 `_create_*_func` 是过度抽象** — `vcg_execution_engine.py:104-156`

```python
def _create_connect_func(self):
    def Connect(source_pattern, target_pattern, port_type=None):
        self.rule_manager.add_signal_rule(source_pattern, target_pattern, port_type)
    return Connect
```

为了把 4 个透传函数装进 `context` dict，写了 4 个工厂方法 + 4 个内部函数。这是 Java 病。Python 里直接：

```python
def _create_execution_context(self) -> dict:
    return {
        '__builtins__': __builtins__,
        'print': self._custom_print,
        'Instance': self._instance,
        'Connect': self.rule_manager.add_signal_rule,
        'ConnectParam': self.rule_manager.add_param_rule,
        'WiresRule': self.rule_manager.add_wire_rule,
        'WiresDef': self._wires_def,
        # ...
    }
```

`Connect`/`ConnectParam`/`WiresRule` 直接绑 method ref，参数签名一致，零开销。
`Instance`/`WiresDef`/`print` 因为有副作用（更新 output、reset rule），保留方法即可。
6 个工厂 → 0 个工厂。文件能少 30 行。

### P2

**4. `__builtins__` 全开** — `vcg_execution_engine.py:94`

```python
context = {
    '__builtins__': __builtins__,
    ...
}
```

注意 `__builtins__` 在模块顶层是 module 对象，作为 dict 传入 exec 时 Python 会自动处理，但语义上等于"用户脚本拥有解释器全权限"。如果定位是"本地开发者工具"，这是合理选择，但**必须在 docstring 标注**。如果未来要支持 CI 执行不可信 Verilog 模板，这是 RCE。

**5. `expand_path` 默默 resolve 不存在的路径** — `vcg_execution_engine.py:69-73`

```python
def expand_path(self, path_str: str) -> str:
    expanded_path = os.path.expandvars(path_str.strip())
    expanded_path = os.path.expanduser(expanded_path)
    abs_path = str(Path(expanded_path).resolve())
    return abs_path
```

`Path.resolve()` 在 Python 3.6+ 默认 `strict=False`，路径不存在时不报错。然后下游 `instance_manager.generate_instance(file_path, ...)` 接到一个解析过但不存在的路径，错误信息会变得难懂（"找不到模块"而非"找不到文件"）。

加一行 fail-fast：

```python
if not os.path.exists(abs_path):
    raise VCGFileError(f"File not found: {path_str} -> {abs_path}")
```

**6. `custom_print` 的 `file is not None` 分支** — `vcg_execution_engine.py:149-155`

```python
def custom_print(*args, sep=' ', end='\n', file=None, flush=False):
    if file is not None:
        print(*args, sep=sep, end=end, file=file, flush=flush)
        return
    ...
```

允许用户 `print(..., file=sys.stderr)` 绕过收集器——这是合理的逃生口，但也意味着用户能 `print(..., file=open('/etc/passwd', 'w'))`。和 P2-4 同源，标注即可。

**7. `OrderedOutputManager` 与 `VCGExecutionEngine` 应同文件还是分文件** — `vcg_execution_engine.py:33`

按"多个小文件优于一个大文件"的项目规范，OrderedOutputManager 完全可以独立。但目前 56 行的 Manager + 100 行的 Engine 共 156 行，没有突破 800 行红线，**不必拆**。这一条不是问题，是反向确认：留在原文件是对的。

**8. 类型注解不统一** — 文件全篇

`List[str]` (vcg_execution_engine.py:34) 用 `typing.List`，但 PEP 585 推荐 `list[str]`。Python 3.14 项目应该一律用内建泛型。`Dict, Tuple` 也 import 了但没用 (`vcg_execution_engine.py:26`)。

## Linus 式改进方向

按优先级，不分批：

1. **修异常吞类型**（P0，5 行改动）
   `except Exception` 前面加一个 `except (VCG*Error,): raise`，并加 `from e`。

2. **合并 3 个 `add_*_output` 为 1 个 `add`**（P1，删 15 行）
   把 print 格式化挪进 `custom_print`，Manager 退化为"加一行"。三个调用点同步改名。

3. **干掉 6 个 `_create_*_func` 工厂**（P1，删 30 行）
   `Connect`/`ConnectParam`/`WiresRule` 在 context dict 里直接绑 `self.rule_manager.add_*` method。`Instance`/`WiresDef`/`print` 改成普通 method（带 `self`）后绑定，Python 的 bound method 自动 capture self，无需闭包。

4. **`expand_path` 加 fail-fast**（P2，3 行）
   不存在的路径立刻 `VCGFileError`。

5. **docstring 标注 `__builtins__` 全开**（P2，2 行注释）
   "User scripts run with full Python privileges. Do not feed untrusted templates."

6. **类型注解 PEP 585 化 + 删未用 import**（P2，5 行）
   `List` → `list`，删掉 `Dict, Tuple`。

完成上述六项后，文件应在 110 行左右，零特殊情况，零样板工厂，异常类型保留语义。这才叫"好品味"。

---

**总结一句**：这文件不烂，但每一段都能再短一半。当前的"工厂方法包闭包再返回"是 OOP 思维的肌肉记忆，Python 不需要这么端着。把数据结构和异常类型当一等公民，代码会自己变短。
