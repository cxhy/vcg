# DELIVERY: vcg_rule_manager.py refactor

| 字段 | 值 |
|------|----|
| 来源 | 用户直接要求完成 `src/vcg_rule_manager.py` 重构 |
| 负责 | vcg-python-dev |
| 状态 | delivered |
| 日期 | 2026-05-10 |

## 修改文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `src/vcg_rule_manager.py` | 修改 | 规则从 dict 改为 `SignalRule` / `ParamRule` / `WireRule` frozen dataclass；移除 `eval()`；用显式函数表达式解析器处理 `${upper(*)}` / `${replace(*, ...)}` 等安全函数；压缩重复日志和规则遍历逻辑 |
| `tests/test_vcg_rule_manager.py` | 修改 | 新增安全回归测试，验证 `${str.__class__...}` 不会被执行；新增兼容性测试，锁定“无 wildcard source 不执行函数表达式”的旧行为 |
| `doc/refactor_backlog_2026-05-10.md` | 修改 | 将 `vcg_rule_manager.py` 从 P0 backlog 移入已完成清单 |

## 需要验证的测试点

1. 正常路径：`upper` / `lower` / `title` / `capitalize` / `replace` / `strip` / `lstrip` / `rstrip` 函数表达式行为保持不变。
2. 安全路径：属性访问、对象模型访问、非白名单函数不执行，按旧策略 fallback 到第一个 wildcard 捕获组。
3. 兼容路径：source pattern 不含 `*` 时，target 中的 `${...}` 不求值，保持旧实现行为。
4. 规则语义：信号/参数/线网规则仍保持后添加优先、方向过滤、literal 宽度展开、inline comment restore。
5. 下游影响：`InstanceManager` / `WiresManager` 通过原有 `resolve_*` 接口调用，不需要适配。

## 验证结果

| 命令 | 结果 |
|------|------|
| `uv run pytest tests/test_vcg_rule_manager.py -q` | `87 passed` |
| `uv run pytest tests/test_vcg_instance_manager.py tests/test_vcg_wires_manager.py -q` | `84 passed` |
| `uv run pytest tests/ -q` | `605 passed` |
| `.venv\Scripts\python.exe -m py_compile src\vcg_rule_manager.py` | 通过 |
| `rg -n "\beval\(|except Exception|rule\['|safe_functions" src\vcg_rule_manager.py` | 无匹配 |

## 对下游模块的影响

- 公开 API 未变：`add_signal_rule()`、`add_param_rule()`、`add_wire_rule()`、`resolve_signal_connection()`、`resolve_param_connection()`、`resolve_wire_generation()`、`reset()`、`get_rules_summary()` 均保留。
- `self.rules` 仍保留 `signal_rules` / `param_rules` / `wire_rules` 三个 key，但元素类型从 dict 变为 frozen dataclass；项目内未发现外部直接索引 dict 字段。
- 函数表达式不再通过 Python `eval()` 执行，只支持明确白名单函数和 wildcard/string-literal 参数。

## 已知环境问题

- `uv run python -m py_compile src\vcg_rule_manager.py` 在本机失败，原因是 uv cache 路径 `C:\Users\cxhy1\AppData\Local\uv\cache\sdists-v9\.git` 访问被拒绝。
- 同一环境下 `uv run pytest ...` 可正常执行；语法检查已用项目 `.venv\Scripts\python.exe` 完成。
