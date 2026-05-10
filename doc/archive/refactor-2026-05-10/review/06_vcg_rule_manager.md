# vcg_rule_manager.py Review

> 评审日期: 2026-04-21
> 评审人: Linus (代理)
> 文件路径: src/vcg_rule_manager.py
> 文件规模: 405 行

## 品味评分

🔴 垃圾

## 核心判断

❌ **当前实现是"凑合能跑"的初级品**。它有正确的功能意图，但数据结构选错了、特殊情况遍地、日志噪音淹没了真正逻辑、安全模型靠 `eval` 撑着。整个文件读起来像是先写出来再没人重构过 —— 三个 `resolve_*` 几乎是 copy-paste 的孪生兄弟，一处改动得改三处。

Linus 三问回答：
1. **真问题？** 是。规则匹配 + 通配符替换是正常需求。
2. **更简单办法？** 有。把规则做成 `frozen dataclass`，把三个 resolve 抽出公共的 `_resolve_with_rules(...)`，把 `eval` 换成显式 dispatch，文件能砍到 200 行以内。
3. **会破坏什么？** 重构会破坏 dict 形状的隐式契约。但项目内部使用，没有外部 API 锁定 —— 该破就破。

## 关键洞察

- **数据结构**: 规则用 `dict` 存储 (`vcg_rule_manager.py:32-36`, `:56-63`, `:71-76`, `:87-95`)，三种规则字段不同但通过同一个字典池共存。每次访问都是 `rule['source']` / `rule.get('comments')` 这种字符串键查找 —— 没有类型保护，没有 IDE 补全，没有一处地方告诉你 wire rule 到底有哪些字段。CLAUDE.md 明文要求 `frozen dataclass`，这里 0 配合。
- **复杂度**: 文件 405 行，单文件接近 CLAUDE 规范的临界。三个 `resolve_*` 方法 (`:112`, `:170`, `:187`) 共享相同骨架 —— 倒序遍历 → 匹配 → 应用替换 → 处理 literal/comment —— 但代码是手抄三遍。`_generate_width_literal` (`:369`) 把"无 width / int width / 表达式 width"三种情况切成 4 个分支，可以折叠。
- **风险点**: (1) `_execute_function_call` 使用 `eval` (`:358`)，虽然清空了 `__builtins__` 但 `local_vars` 里塞了 `str`，攻击者可以构造 `str.__class__.__mro__[1].__subclasses__()` 这套绕过路径。规则来源若来自不可信文件就是远程代码执行。(2) 通用 `except Exception` (`:364`) 把所有异常吞成 fallback，违反 CLAUDE.md 异常处理规范。(3) `_generate_width_literal` 的 magic number `8` (`:377`) 没有任何注释说明为什么 8，是阈值还是巧合？

## 致命问题（按严重度）

### P0：`eval()` 安全洞 + 异常吞噬

`vcg_rule_manager.py:358`

```python
result = eval(processed_call, {"__builtins__": {}}, local_vars)
```

`local_vars` 里有 `str` 和 `self.safe_functions` 中的 bound method。Python 沙箱靠清 `__builtins__` 是**不够的**，经典逃逸：

```
${str.__class__.__mro__[1].__subclasses__()[XXX]("rm -rf /")}
```

只要规则文件可以被任何渠道注入（命令行 `--macros`、未来支持的配置文件、include 进来的 .v），就是 RCE。

紧接着 `vcg_rule_manager.py:364`：

```python
except Exception as e:
    fallback = groups[0] if groups else function_call
    self.logger.warning(...)
    return fallback
```

裸 `except Exception` 把语法错误、类型错误、安全异常全吞了 —— 用户写错 `${upper(}` 永远不会知道哪里错了，只会看到一个莫名其妙的回退值。CLAUDE.md 明确禁止"通用 `except Exception` 吞掉有语义的异常"。

**修复方向**: 弃用 `eval`，改成显式 parser：把 `upper(*)` / `replace(*,a,b)` 解析成 `(name, args)` 元组，然后 `self.safe_functions[name](*args)`。20 行代码搞定，零安全风险。

### P1：三个 resolve 方法的 copy-paste

`vcg_rule_manager.py:112-153` (signal)、`:170-185` (param)、`:187-235` (wire) —— 三个方法的骨架相同：

```
for rule_index, rule in enumerate(reversed(rules)):
    rule_num = len(rules) - 1 - rule_index
    self.logger.debug(f"Checking ... rule #{rule_num}: ...")
    if self._match_pattern(name, rule['<key>']):
        ...apply substitution...
        ...handle literal...
        ...restore comments...
        return result
```

但因为规则用的是 dict，每个方法都得手写自己的 key 查找路径 (`rule['source']` vs `rule['param_name']` vs `rule['port_pattern']`)，导致无法抽公共函数。

**修复方向**: 三步走 —— ① 把规则做成 dataclass：

```python
@dataclass(frozen=True)
class SignalRule:
    source: str
    target: str
    comments: tuple[str, ...]
    port_direction: str | None
    priority: int

    def matches(self, port: PortInfo) -> bool: ...
    def apply(self, port: PortInfo) -> str: ...
```

② 让规则自己负责 match 和 apply，`VCGRuleManager` 只剩遍历逻辑：

```python
def _resolve(self, rules, target, default):
    for rule in reversed(rules):
        if rule.matches(target):
            return rule.apply(target)
    return default
```

三个 resolve 方法塌缩成 3 行调用。

### P1：日志噪音淹没逻辑

`resolve_signal_connection` 41 行里 11 个 `logger.debug` 调用 (`:116-150`)。`_apply_pattern_substitution` 38 行 9 个 (`:255-289`)。`_execute_function_call` 33 行 7 个 (`:336-367`)。

后果：
- **真实代码逻辑只占文件不到 40%**，剩下都是日志参数构造的字符串拼接。
- 阅读时眼睛要在"日志 → 代码 → 日志 → 代码"间反复切换，认知负载爆炸。
- f-string 在 DEBUG 级别下也会 eager evaluate，每次调用都付出字符串构造代价 —— 应该用 `logger.debug("...", arg1, arg2)` 的 lazy 形式。
- `logger.debug` 之后立刻 `logger.info`（如 `:149-150`、`:181`）输出几乎相同信息，重复 log 同一事件。

**修复方向**: 砍掉 80% 的 debug。每个方法保留 1-2 个关键节点（"start resolving X"、"matched rule #N"），其余删除。需要详细 trace 时上 `logger.isEnabledFor(DEBUG)` 守卫。

### P2：`_generate_width_literal` 的 magic 8

`vcg_rule_manager.py:377`

```python
if w_int and w_int <= 8:
    result = f"{w_int}'b{value * w_int}"
```

为什么是 8？没有常量名，没有注释，没有 PROJECT.md 说明。是因为 8-bit 字面量更易读？阈值定在 16 行不行？硬编码数字是禁忌。

而且这个方法有真正的逻辑问题：分支结构是"无 width → 单 bit / int width ≤8 → 二进制串 / int width >8 → replication / str width → replication（带括号）"，但其实可以**消除特殊情况**：

```python
DEFAULT_BIT_WIDTH = 1
INLINE_BINARY_THRESHOLD = 8  # 命名常量

if not width:
    return f"1'b{value}"
w = self._normalize_width(port.width)  # 返回 (int_or_None, str_form)
return self._format_replication(w, value)
```

`_format_replication` 内部用一致的 `{N{1'b?}}` 形式，width≤8 的"二进制串"分支属于"为了好看的特殊情况"，可以问自己：真的有必要吗？如果产物总是 `{8{1'b1}}` 也完全合法可综合。

### P2：`_apply_pattern_substitution` 的诡异回退

`vcg_rule_manager.py:266-268`

```python
if not match:
    self.logger.debug(...)
    return target_pattern
```

调用者 `resolve_signal_connection` 在调用本方法**之前**已经用 `_match_pattern` 检查过 (`:133`)。换言之，这里的 `if not match: return target_pattern` 永远不应该触发 —— 但代码默默吞掉异常情况返回了一个不带替换的 target。如果哪天调用顺序变了，bug 会以"占位符没替换"的形式静默扩散。

**修复方向**: 这种"不可能发生"的分支应该 `raise AssertionError`，或者干脆把 match 和 substitute 合并成一个调用，传 `re.Match` 对象进来。

### P2：`reset` 方法的代码重复

`vcg_rule_manager.py:101-109`

`reset` 把 `__init__` 里的 dict 字面量复制了一遍。一旦增加第四类规则，要改两处。提取成 `_empty_rules_dict()` 工厂方法或 class-level 常量。

### P2：日志冗余 — debug 之后 info 重复同一事件

例如 `:149-150`：

```python
self.logger.debug(f"Applied signal rule #{...} to '{signal_name}' -> '{final_result}'")
self.logger.info(f"Signal connection resolved: '{signal_name}' -> '{final_result}'")
```

两条 log 表达同一件事，info 是 debug 的子集。选一个。

### P2：`port.direction` 检查不一致

`add_signal_rule` (`:61`) 把 `port_direction` 存为小写：`port_direction.lower() if port_direction else None`。但 `_check_port_direction_match` (`:163`) 又做一次 `required_direction.lower()`。规则添加时已经小写化，方法里再次 lower 是无谓开销 —— 或者反过来，如果 `required_direction` 可能不是 lower 的（接口契约不清晰），那就该在一处统一 normalize。当前是"两边都做一遍"，典型的防御式编程冗余。

## Linus 式改进方向

按优先级一条条来，每条都是"先简化数据结构，再消除特殊情况"：

1. **干掉 `eval`**：自己写一个 30 行的 `_parse_function_call(text) -> (name, args)`。这是 P0 安全洞，必须先修。完成后能立即砍掉 `safe_functions` dict、`_execute_function_call` 里的字符串变换逻辑（`*0` → `group_0` 那段）。

2. **规则 dict → frozen dataclass**：`SignalRule` / `ParamRule` / `WireRule`，加一个 `Rule` Protocol 暴露 `matches` 和 `apply`。不可变性是 CLAUDE.md 硬要求，目前 0 分。

3. **三个 resolve 方法塌缩成一个泛型 `_resolve(rules, target, default)`**：依赖第 2 步完成。预计三个方法从 ~80 行降到 ~15 行。

4. **日志大屠杀**：每个方法保留 1 条 INFO 表示"做完了"，删除 80% 的 DEBUG。剩下的 DEBUG 用 lazy 格式 `logger.debug("matched %s -> %s", a, b)`。文件预计能瘦 100 行。

5. **`_generate_width_literal` 简化**：把 magic 8 提成命名常量 `INLINE_BINARY_THRESHOLD = 8`，并认真考虑是否真有必要保留 ≤8 的特殊形式。Bonus：用 `_normalize_width(width) -> int | str` 把"是否能转 int"的特殊情况消灭在一个地方。

6. **`reset` 提取工厂**：`@staticmethod def _empty_rules() -> dict`。

7. **异常吞噬**：所有 `except Exception` 拆成具体异常类型，按 CLAUDE.md 用 `VCGRuntimeError` 体系。

完成 1+2+3+4 后预计文件能从 405 行降到 220 行左右，三个 resolve 方法可读性提升一个数量级，安全洞修好，日志不再淹没逻辑。这才是这个文件应有的样子。

> "Bad programmers worry about the code. Good programmers worry about data structures."
> 这个文件的根本问题就是数据结构错了 —— 规则不该是 dict。修好这一条，剩下的问题一半自然消失。
