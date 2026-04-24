# TASK-01: 重构 src/VerilogAst.py（依据 review 11_VerilogAst.md）

| 字段 | 值 |
|------|----|
| 负责 | vcg-python-dev → vcg-python-tester → vcg-verilog-checker |
| 依赖 | doc/review/11_VerilogAst.md（Linus 评审） |
| 状态 | pending（等待用户确认后派发 dev） |
| 创建 | 2026-04-25 |
| Baseline | tmp/baseline_dma_system.v （md5 `bdbf98cf1f3165bfe8dbda8231f1062e`, 187 行） |

---

## 1. 背景与目标

严格依据 `doc/review/11_VerilogAst.md` 执行重构。不做 review 范围外的方案调整，不"顺手优化"。

### 1.1 硬约束（不得突破）

- **目标文件**：仅 `src/VerilogAst.py`
- **API 兼容性**：以下类名 + 公共方法签名保持不变
  - `VerilogAST`、`PortInfo`、`ParameterInfo`、`PortManager`、`ParameterManager`
  - `VerilogASTBuilder`、`PortFactory`、`PortDirection`、`PortType`、`ExpressionCalculator`
  - 含已有公共方法：`PortFactory.to_info(decl)`、`PortManager.add_port_info(port_info)`、
    `ParameterManager.add_parameter(name, **kwargs)`、`VerilogASTBuilder.add_port / update_port / add_parameter / build / reset / set_module_name`、
    `VerilogAST.get_port_info / get_parameter_info / get_module_info`、
    `ExpressionCalculator.parse_width_expression(expr)`
- **下游零改动**：`VerilogParser.py`、`vcg_instance_manager.py`、`vcg_wires_manager.py`、`vcg_rule_manager.py` 不得修改
- **方案不调整**：不重写 PLY / 不换 sympy / 不重设计 AST 层级 / 不新增依赖

### 1.2 用户已决策项（会话记录 2026-04-25）

| 决策点 | 结论 |
|--------|------|
| PortDeclaration / PortFactory 合并（review #4） | **搁置**。保留 PortDeclaration 与 PortFactory 原样（因硬约束） |
| PortNotFoundError / ParameterNotFoundError（review #12） | **允许删除**（全仓 0 引用，grep 确认） |
| ParameterManager / PortManager 扩展（review #2 / #6） | **两项都允许**：①给 ParameterManager 新增 `add_parameter_info(ParameterInfo)`；②抽 `OrderedRegistry[T]` 泛型基类，两个 Manager 继承之（类名与公共签名不变） |
| PortDirection 启用（review #10） | **搁置**（会改下游字符串协议） |
| PortType.ARRAY_2D/3D 重设计（review #11） | **搁置**（属"重设计 AST 层级"硬约束） |
| 三个 dataclass frozen（review #5） | **全部 frozen=True**。Builder.add_port 内部改用 `dataclasses.replace` 重建对象，外部行为不变 |
| `_calculate_vector_width` 的 endswith hack（review #1 P0） | **删整个 if 分支**，让 sympy 自己化简 |
| examples/dma_system.v 验收 | **byte-for-byte 等价**。任何 diff checker 报 feedback，architect 转交用户裁决 |

---

## 2. Review 条目 ↔ 任务追溯表

| # | Review 条目 | 严重度 | 本次任务编号 | 处置 |
|---|------------|--------|------------|------|
| 1 | `_calculate_vector_width` endswith hack bug | P0 | T-A | 删除 lines 170-171 的 if 分支 |
| 2 | `Builder.build()` 直戳 `_parameters` / `_parameter_order` | P0 | T-B | ParameterManager 新增 `add_parameter_info(info)`；Builder 改用之 |
| 3 | `ExpressionCalculator._sympy_parse` silent fallback | P1 | T-C | 在 except 里加 `get_vcg_logger('VerilogAST.Calculator').debug(...)` 记录表达式 + 异常类型，然后原逻辑保持（返回 expr） |
| 4 | PortDeclaration 与 PortInfo 重复 | P1 | — | **搁置**（因硬约束保留 PortFactory / PortDeclaration） |
| 5 | 三个 dataclass 未 frozen、Builder setattr mutate | P1 | T-D | 三个 dataclass 加 `frozen=True`；Builder.add_port 用 `dataclasses.replace` 重建 PortDeclaration 对象 |
| 6 | ParameterManager / PortManager 模板重复 | P2 | T-E | 抽 `OrderedRegistry[T]` 泛型基类（文件内私有，不对外导出）；两 Manager 继承之；公共签名不变 |
| 7 | 模块级 `_calculator` 单例 + `patterns` 死代码 | P2 | T-F | 删 `ExpressionCalculator.__init__.patterns`（未使用）；`_calculator` 单例**保留**（外部已通过模块属性访问的可能，保守） |
| 8 | `Builder.update_port = self.add_port` 别名 | P2 | T-G | **保留并文档化**（VerilogParser.py:362 在用）。加 docstring 注明"完全等价于 add_port"；不删 |
| 9 | `PortInfo.range_string` array_dims 分支未检查 lsb_expr | P2 | T-H | 改 `if self.msb_expr and self.lsb_expr:` 双判定，与 port_type 一致 |
| 10 | PortDirection 枚举未用 | P2 | — | **搁置**（会改下游协议） |
| 11 | ARRAY_2D/3D 分类泄漏 | P2 | — | **搁置**（重设计 AST 层级） |
| 12 | PortNotFoundError / ParameterNotFoundError 死代码 | P2 | T-I | **删除**两个异常类（不在硬约束保留清单，grep 全仓 0 引用） |

---

## 3. 函数级修改清单

### T-A：删除 `_calculate_vector_width` 的字符串 hack （`VerilogAst.py:170-171`）

**位置**：`PortInfo._calculate_vector_width`

**删除**：
```python
if str(lsb_val) == "0" and str(self.msb_expr).endswith("-1"):
    return self.msb_expr[:-2]
```

**保留**：其余逻辑，`(msb)-(lsb)+1` 让 sympy 自己化简。

**期望行为**：
- 输入 `msb="WIDTH-1", lsb="0"` → sympy 化简 `(WIDTH-1)-(0)+1` → `"WIDTH"`（结果同旧 hack，路径经 sympy）
- 输入 `msb="WIDTH - 1", lsb="0"` → sympy 化简 → `"WIDTH"`（旧 hack 会产出 `"WIDTH - "`，**本次修复**）
- 输入 `msb="FOO-1+1", lsb="0"` → sympy 化简 `(FOO)-(0)+1` → `"FOO+1"`（旧 hack 会错误截断为 `"FOO-1+"`，**本次修复**）

---

### T-B：ParameterManager 扩展 `add_parameter_info`，Builder.build 停戳私有

**位置**：`ParameterManager` + `VerilogASTBuilder.build`

**新增方法**（对称 PortManager.add_port_info）：
```python
def add_parameter_info(self, param_info: ParameterInfo) -> None:
    if param_info.name not in self._parameters:
        self._parameter_order.append(param_info.name)
    self._parameters[param_info.name] = param_info
```

**修改** `VerilogASTBuilder.build` lines 308-311：
```python
# 旧：
for name in self._parameter_order:
    param = self._parameters[name]
    ast.parameter_manager._parameters[name] = param
    ast.parameter_manager._parameter_order.append(name)

# 新：
for name in self._parameter_order:
    ast.parameter_manager.add_parameter_info(self._parameters[name])
```

---

### T-C：ExpressionCalculator._sympy_parse 加日志

**位置**：`ExpressionCalculator._sympy_parse` lines 80-86

**新增模块级 logger**：
```python
from .vcg_logger import get_vcg_logger
_logger = get_vcg_logger('VerilogAST.Calculator')
```

**修改**：
```python
def _sympy_parse(self, expr: str) -> Union[int, str, float]:
    try:
        processed, mapping = self._handle_dollar_funcs(expr)
        result = simplify(sympify(processed))
        return self._format_result(result, mapping)
    except Exception as e:
        _logger.debug(
            "sympy parse failed for expr=%r (type=%s): %s",
            expr, type(e).__name__, e
        )
        return expr
```

**行为变更**：返回值不变（仍是原 expr），仅 DEBUG 级日志新增。默认日志级别 INFO 不会可见。

---

### T-D：三个 dataclass 加 `frozen=True`

**位置**：`PortDeclaration` (line 114)、`PortInfo` (line 125)、`ParameterInfo` (line 188)

**修改**：
```python
@dataclass(frozen=True)
class PortDeclaration: ...

@dataclass(frozen=True)
class PortInfo: ...

@dataclass(frozen=True)
class ParameterInfo: ...
```

**连锁修改** `VerilogASTBuilder.add_port` lines 284-294：
```python
def add_port(self, name: str, **kwargs) -> 'VerilogASTBuilder':
    if name not in self._port_decls:
        self._port_order.append(name)
        self._port_decls[name] = PortDeclaration(name=name)

    decl = self._port_decls[name]
    # 旧：setattr(decl, key, value)
    # 新：dataclasses.replace 过滤掉 None 与不存在字段
    update = {
        k: v for k, v in kwargs.items()
        if v is not None and k in {f.name for f in fields(decl)}
    }
    if update:
        self._port_decls[name] = dataclasses.replace(decl, **update)
    return self
```

**注意**：
- `field(default_factory=list)` 在 frozen dataclass 下需改成 `field(default_factory=tuple)` 或保持 `list` 但不可变语义靠约定。**本任务保持 list** 以维持对外签名；dev 实施时需在 docstring 说明"虽 frozen 但 array_dims 字段仍是 list，请不要 in-place mutate"。
- `import dataclasses` 与 `from dataclasses import fields` 需补齐。

---

### T-E：抽 `OrderedRegistry[T]` 私有基类

**位置**：`ParameterManager` 与 `PortManager` 之前新增

**新增**（使用 PEP 695 / typing.Generic 皆可，优先 `typing.Generic[T]` 兼容性稳）：
```python
from typing import Generic, TypeVar

_T = TypeVar("_T")

class _OrderedRegistry(Generic[_T]):
    """文件内私有：dict + insertion-order 列表的统一实现。"""
    def __init__(self) -> None:
        self._items: Dict[str, _T] = {}
        self._order: List[str] = []

    def _put(self, key: str, value: _T) -> None:
        if key not in self._items:
            self._order.append(key)
        self._items[key] = value

    def _all(self) -> List[_T]:
        return [self._items[k] for k in self._order]
```

**ParameterManager 重构**（公共签名完全不变）：
```python
class ParameterManager(_OrderedRegistry[ParameterInfo]):
    def __init__(self) -> None:
        super().__init__()
        # 维持对外 _parameters / _parameter_order 属性别名
        self._parameters = self._items
        self._parameter_order = self._order

    def add_parameter(self, param_name: str, **kwargs) -> None:
        self._put(param_name, ParameterInfo(
            name=param_name,
            param_type=kwargs.get('param_type', 'parameter'),
            default_value=kwargs.get('default_value', ''),
            data_type=kwargs.get('data_type'),
        ))

    def add_parameter_info(self, param_info: ParameterInfo) -> None:
        self._put(param_info.name, param_info)

    def get_all_parameters(self) -> List[ParameterInfo]:
        return self._all()
```

**PortManager 同理**。

**字段别名** (`self._parameters = self._items`)：是为了防万一有外部/测试代码偷偷读下划线字段。grep 未见外部引用，但保险起见保留别名（零成本）。

---

### T-F：删 `ExpressionCalculator.__init__.patterns`

**位置**：lines 70-73

**删除**整个 `self.patterns = {...}` 字典（file grep 已确认无引用）。`__init__` 若变空，保留空方法或显式删除 `__init__` 皆可（**保留空 `__init__`** 以维持 `ExpressionCalculator()` 可无参实例化的外部行为——虽 Python 本默认如此，显式保留避免 linter 报"pointless init"时 dev 误删）。

**保留**：模块级单例 `_calculator` （review 建议的"注入 calculator"属于测试友好性改造，但会改变 PortInfo 的接口）。

**同时删除**：`import re` 与 `self.patterns` 相关死代码（若 `re` 仅此处使用）。**需 dev 确认**：`_handle_dollar_funcs` 里用了 `re.sub`，**re 必须保留**。

---

### T-G：`update_port` 加 docstring

**位置**：line 296-297

```python
def update_port(self, name: str, **kwargs) -> 'VerilogASTBuilder':
    """等价于 add_port()。保留别名以支持 VerilogParser.py 等下游调用方。

    Note:
        该方法与 add_port 完全同义。PLY grammar rule 倾向用 update_*
        命名强调"已存在端口的字段补全"语义，底层共用 add_port 实现。
    """
    return self.add_port(name, **kwargs)
```

---

### T-H：`PortInfo.range_string` array_dims 分支双判定

**位置**：line 181

```python
# 旧：
base_range = f"[{self.msb_expr}:{self.lsb_expr}]" if self.msb_expr else ""

# 新：
base_range = (
    f"[{self.msb_expr}:{self.lsb_expr}]"
    if self.msb_expr and self.lsb_expr
    else ""
)
```

与 `port_type` property 的 `self.msb_expr and self.lsb_expr` 判定对齐。

---

### T-I：删 `PortNotFoundError` / `ParameterNotFoundError`

**位置**：lines 387-393

**删除**：
```python
class PortNotFoundError(VerilogASTError):
    """端口未找到异常"""
    pass

class ParameterNotFoundError(VerilogASTError):
    """参数未找到异常"""
    pass
```

**保留**：`VerilogASTError`（`VerilogParser.py:205` 在 catch）。

---

## 4. 风险清单

| 风险 | 影响 | 缓解 |
|------|------|------|
| T-A 删 hack 后 sympy 化简结果与旧 hack 字节差异 | examples/dma_system.v baseline diff | checker 阶段 `cmp tmp/baseline_dma_system.v examples/dma_system.v`，任何 diff 报 feedback 找用户裁决 |
| T-D frozen 导致 `array_dims: list` 字段外部可被 in-place mutate（frozen 只冻顶层字段重绑定） | 不可变性仍有缝隙 | 任务单文档标注，实施保持现状；后续如需根治可改 tuple（属下次迭代） |
| T-E `self._parameters = self._items` 别名若外部偷改会同步影响 | 封装轻度泄漏 | 别名仅用于保险；公共 API 无人需要访问下划线字段 |
| T-C 新增 import `get_vcg_logger` 造成循环依赖 | import 失败 | `vcg_logger.py` 已在 src/ 下独立模块，grep 确认不 import VerilogAst；无风险 |
| frozen + dataclasses.replace 语义重排导致 PLY grammar 回调时临时对象被旧引用持有 | parser 行为变化 | grep VerilogParser 确认未长期持有 decl 引用；每次 rule 都经 add_port/update_port 走 builder |

---

## 5. 回滚策略

- 每个子任务 T-A..T-I 可独立 git commit，便于二分回滚
- 若 tester/checker 阶段全量失败：`git restore src/VerilogAst.py`，回到当前 HEAD 状态
- baseline `tmp/baseline_dma_system.v` 作为不可变参考，整个重构周期内不得覆盖

---

## 6. 验收标准（硬性）

- [ ] `uv run pytest tests/ -v` 全绿
- [ ] `cmp -s tmp/baseline_dma_system.v examples/dma_system.v`（先 restore examples/ 再跑 vcg.py 再比对）返回 0（byte-for-byte 等价）
- [ ] `git diff --stat src/VerilogParser.py src/vcg_instance_manager.py src/vcg_wires_manager.py src/vcg_rule_manager.py` 输出为空（下游零改动）
- [ ] 对外 API 签名 diff 为空：
  - tester 阶段用 `python -c "import inspect; from src.VerilogAst import ...; print(inspect.signature(...))"` 枚举硬约束清单所有符号，与当前 HEAD 对比
- [ ] Review #1 / #2 / #3 / #5 / #6 / #7 / #9 / #12 八条已落地；#4 / #8 / #10 / #11 明确标注"因硬约束搁置"并有理由
- [ ] 文件行数变化可接受（原 394 行 → 最终 452 行，+58 行，因强制 docstring + `_OrderedRegistry` 基类 + T-A-fix narrow fallback；2026-04-25 用户批准该偏差）

---

## 7. 交付物清单（dev 阶段）

- `src/VerilogAst.py`（重构后）
- `doc/delivery_01_refactor_verilogast.md` 包含：
  - 每项 T-A..T-I 的实际改动位置（文件行号）
  - frozen 改造的 edge case 说明
  - 新增的 import 与为何需要
  - 本地 `uv run pytest tests/ -v` 快速自检结果

---

## 8. 后续阶段预告

- **tester**：`doc/verification_01_refactor_verilogast.md`
  - 全量 pytest 回归
  - 补充单测：`_calculate_vector_width` 带空格表达式、嵌套 `-1` 表达式、frozen dataclass 不可变性断言、`add_parameter_info` 对称 API、DEBUG 日志是否发出
- **checker**：`doc/check_01_refactor_verilogast.md`
  - `git restore examples/dma_system.v && uv run python vcg.py examples/dma_system.v && cmp tmp/baseline_dma_system.v examples/dma_system.v`
  - 对外 API 签名枚举对比

---

> Architect 签字：依据 2026-04-25 用户决策编制。
> 交付用户确认后，派发至 vcg-python-dev。
