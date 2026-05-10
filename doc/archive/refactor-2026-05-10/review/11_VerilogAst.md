# VerilogAst.py Review

> 评审日期: 2026-04-21
> 评审人: Linus (代理)
> 文件路径: src/VerilogAst.py
> 文件规模: 394 行

## 品味评分
🟡 凑合 —— 比 1150 行的旧版强一大截，但骨子里仍是"OOP 厨房水槽"，藏着一处真 bug、若干无脑模板、以及对 CLAUDE.md 不可变性原则的当面违反。

## 核心判断

值得做一次"再瘦身"。当前文件 5 个核心类（PortDeclaration / PortInfo / PortFactory / PortManager / Builder）干了一件事的 4 个名字。把 Declaration/Info 合一、把 Factory 干掉、把 build() 内部的私有戳穿换成正经 API，能再砍掉 80~120 行，并消灭一类潜在 bug。

但**不要紧急动**：这个文件已经被 4 个下游模块（vcg_instance_manager / vcg_rule_manager / vcg_wires_manager / VerilogParser）和测试文档绑定了 `PortInfo` / `ParameterInfo` / `VerilogASTError` 这套对外名字。重构必须保留这些导出名，否则就是"Never break userspace"被自己打脸。

## 关键洞察

- **数据结构**: `PortDeclaration` (`VerilogAst.py:115-123`) 与 `PortInfo` (`VerilogAst.py:126-134`) 字段一字不差，只是 PortInfo 多挂了几个 `@property`。这是典型的"为了一个动词把名词复制了一遍"。Builder 持有的临时对象和最终对象应该是**同一种东西**，区别仅在于"还没填完" vs "填完了"。`is_complete` 属性已经足以表达后者。
- **复杂度**: `ExpressionCalculator._sympy_parse` (`VerilogAst.py:80-86`) 是经典 silent fallback —— 任何 sympy 异常一律返回原字符串。这意味着 **拼写错误的表达式和合法的符号表达式行为完全相同**，调用方无从分辨。`_calculate_vector_width` (`VerilogAst.py:160-174`) 里那段 `lsb=="0" and msb.endswith("-1")` (`:170-171`) 是对 silent fallback 后果的二次补丁——因为 sympy 算 `(N-1)-(0)+1` 时会还原为 `N`，但作者不信任这条路径，所以加了字符串切片 hack。坏品味叠加坏品味。
- **风险点**: `Builder.build()` 里 `ast.parameter_manager._parameters[name] = param` (`VerilogAst.py:310-311`) 直接戳 `ParameterManager` 的下划线私有字段。这是 ParameterManager 唯一的被破坏点（grep 全仓只有这一处），意味着 `add_parameter()` 这个公开 API 形同虚设，封装边界被自己人捅穿。哪天 ParameterManager 改内部实现（比如换成 OrderedDict），Builder 立刻爆炸。
- **不可变性**: CLAUDE.md 第三节明确写了"创建新对象而非修改现有对象 (frozen dataclass)"。`PortDeclaration` / `PortInfo` / `ParameterInfo` 三个 `@dataclass` (`VerilogAst.py:114, 125, 188`) 都不是 `frozen=True`，而 `Builder.add_port` (`VerilogAst.py:284-294`) 用 `setattr(decl, key, value)` 主动 mutate 已存在对象。规范和实现两张皮。

## 致命问题（按严重度）

### P0 — 真 bug / 真破坏

1. **`_calculate_vector_width` 的字符串 hack 与 lsb 表达式不兼容** (`VerilogAst.py:170-171`)
   ```python
   if str(lsb_val) == "0" and str(self.msb_expr).endswith("-1"):
       return self.msb_expr[:-2]
   ```
   - 检查 `lsb_val == "0"` 但只检查 `msb_expr`（**未求值前**的字符串）以 `-1` 结尾。如果用户写 `[WIDTH - 1 : 0]`（带空格），`endswith("-1")` 仍然成立，但 `self.msb_expr[:-2]` 切出来是 `"WIDTH - "`（尾部带空格），返回给下游变成 `wire [WIDTH - :0] xxx`，直接生成出非法 Verilog。
   - 更糟的：`msb_expr` 形如 `"FOO-1+1"` 也会命中 `endswith("-1")`，被错误截断成 `"FOO-1+"`。
   - 整个 if 分支应该被删掉，让 `(msb)-(lsb)+1` 走 sympy 化简就够了；sympy 完全能把 `(N-1)-(0)+1` 化简成 `N`。

2. **`Builder.build()` 直戳 ParameterManager 私有成员** (`VerilogAst.py:308-311`)
   - 绕过了 `ParameterManager.add_parameter` 的唯一公开 API。这是封装违反，也是潜在的 use-after-build 隐患（如果以后 ParameterManager 加了校验或事件钩子，Builder 路径会静默跳过）。
   - 修复极其简单：把那几行换成 `ast.parameter_manager.add_parameter(name, param_type=param.param_type, default_value=param.default_value, data_type=param.data_type)`。或者干脆让 `ParameterManager` 暴露一个 `add_parameter_info(info: ParameterInfo)`，与 `PortManager.add_port_info` (`VerilogAst.py:247`) 对称。后者更好。

### P1 — 设计债 / 沉默失败

3. **`ExpressionCalculator._sympy_parse` silent fallback** (`VerilogAst.py:80-86`)
   - `except Exception: return expr` 把 sympy 内部所有错误（包括拼写错误、非法符号、解析失败）一律降级成"原样字符串"。下游拿到 `"WDITH-1"`（拼错）时和拿到 `"WIDTH-1"`（合法）时无法区分。
   - 应该至少 `logger.debug` 记录失败表达式与异常类型。VCG 项目已经有 `get_vcg_logger`（CLAUDE.md 第三节"日志"段明文要求），这里却完全没用。

4. **`PortDeclaration` 与 `PortInfo` 字段重复** (`VerilogAst.py:114-134`)
   - 7 个字段一字不差。"Declaration → Factory.to_info → Info"这条管线本质是把字段拷一份再加几个 property。Linus 式做法：删掉 PortDeclaration，Builder 直接持有 `Dict[str, PortInfo]`，"完成度"用 `PortInfo.is_complete` 判定。`PortFactory.to_info` (`VerilogAst.py:196-220`) 整个类随之消失。
   - 唯一需要保留的副作用：`net_type or "wire"` 的默认值兜底——把它移进 PortInfo 的 `__post_init__` 即可（如果走 frozen 路线则用 default 表达式）。

5. **`@dataclass` 全部未 frozen，违反 CLAUDE.md 不可变性铁律** (`VerilogAst.py:114, 125, 188`)
   - 项目规范白纸黑字"创建新对象而非修改现有对象 (frozen dataclass)"，三个 dataclass 全部裸 `@dataclass`，`Builder.add_port` (`VerilogAst.py:290-292`) 还显式 `setattr` 改字段。要么改规范，要么改代码——目前是规范在裸奔。
   - 如果 frozen，Builder 的 `add_port` 必须改成 `dataclasses.replace(decl, **kwargs)` 创建新对象。这反而更符合 Builder 模式的语义。

### P2 — 模板代码 / 风格

6. **`ParameterManager` (`VerilogAst.py:222-240`) 与 `PortManager` (`VerilogAst.py:242-253`) 是同一个模板**
   - 都是 "dict + order list + add + get_all"。差别只在元素类型和字段名 (`_parameters`/`_ports`, `_parameter_order`/`_port_order`)。
   - 一个 `OrderedDict[str, T]` 就够了。Python 3.7+ 的普通 dict 都保序，根本不需要单独的 order list。这俩管理器各 12 行可以一起干掉，换成两个 `dict[str, ParameterInfo]` 和 `dict[str, PortInfo]` 直接挂在 VerilogAST 上。
   - 如果坚持要管理器类，至少抽个 `class OrderedRegistry[T]: ...` 泛型基类。

7. **模块级单例 `_calculator = ExpressionCalculator()` (`VerilogAst.py:112`)**
   - PortInfo 在 `_calculate_vector_width` 里直接用模块级全局，绑定成本是测试无法替换 calculator（除非 monkeypatch 模块属性）。这违反 CLAUDE.md "Mock: 直接替换实例属性" 的可测试性原则。
   - 而且 `ExpressionCalculator.__init__` 里那个 `self.patterns` (`VerilogAst.py:71-73`) 在整个文件里**根本没被用过**。死代码。

8. **`Builder.update_port = self.add_port` (`VerilogAst.py:296-297`)**
   - 别名方法。要么删掉，要么明确文档化"两者完全等价"。当前状态是隐性 API 表面积扩大。

9. **`PortInfo.range_string` 的 `array_dims` 分支** (`VerilogAst.py:180-183`)
   - `base_range = f"[{self.msb_expr}:{self.lsb_expr}]" if self.msb_expr else ""`：只检查 `msb_expr` 不检查 `lsb_expr`，与 `port_type` (`VerilogAst.py:142`) 的 `msb and lsb` 双判定不一致。如果只设了 msb 没设 lsb，会产出 `[FOO:None]`。

10. **`PortDirection` 枚举定义了却没被使用** (`VerilogAst.py:56-59`)
    - 全文件 `direction: Optional[str]`，没有任何地方接受或返回 `PortDirection`。`_get_port_summary` (`VerilogAst.py:360-375`) 用 `port.direction.lower()` 字符串比较 `"input"/"output"/"inout"`。要么用枚举一以贯之，要么删掉枚举。

11. **`PortType.ARRAY_3D if len(self.array_dims) >= 3 else PortType.ARRAY_2D` (`VerilogAst.py:141`)**
    - 4 维数组也归类为 ARRAY_3D。这个分类法本身就是泄漏的抽象——为什么要把"任意维度"塞进固定的两个枚举值？要么 ARRAY，要么 `dim_count: int`，二选一。

12. **异常类继承但从不使用** (`VerilogAst.py:387-393`)
    - `PortNotFoundError`、`ParameterNotFoundError` 全文件 0 处 raise，全仓 0 处 catch（grep 已确认）。要么补上抛出点，要么删掉。

## Linus 式改进方向

> "把那个字符串 hack 删掉。让 sympy 干它的活。"

1. **第一刀：杀掉 `_calculate_vector_width` 的 endswith hack** (`VerilogAst.py:170-171`)
   完全删除三行，让 `(msb)-(lsb)+1` 走 sympy。化简结果就是想要的答案。这同时修掉 P0 的真 bug。

2. **第二刀：合并 PortDeclaration 与 PortInfo**
   只留一个 `PortInfo`（保留对外名字），加 `frozen=True`。Builder 的 `_port_decls` 改成 `Dict[str, PortInfo]`，`add_port` 用 `dataclasses.replace` 重建。`PortFactory` 整个删掉。算上 import，省 ~40 行。

3. **第三刀：Builder.build() 改用公开 API**
   要么 `for ... ast.parameter_manager.add_parameter(...)`，要么给 ParameterManager 加 `add_parameter_info(ParameterInfo)`，与 `PortManager.add_port_info` 对称。删掉对 `_parameters` / `_parameter_order` 的私有戳穿。

4. **第四刀：ParameterManager / PortManager 二选一抽象**
   如果不愿意删管理器类，至少二选一改成 `class OrderedRegistry[T]: add(name, item); all() -> List[T]`，让两个管理器变成两个实例。Python dict 已经保序，不需要并行的 order list。

5. **第五刀：silent fallback 至少加日志**
   `_sympy_parse` 的 `except Exception` 用 `get_vcg_logger('VerilogAst.Calculator').debug(...)` 记录原始表达式与异常类型。规范要求，零成本。

6. **清理死代码**：
   - `ExpressionCalculator.patterns` (`:71-73`) 删
   - `PortDirection` 枚举要么用要么删
   - `PortNotFoundError` / `ParameterNotFoundError` 要么用要么删
   - `Builder.update_port` 别名要么文档化要么删

预计净效果：394 行 → 约 250-280 行；消灭 1 个真 bug、1 个封装违反、3 处死代码；同时让 frozen dataclass 真正实施 CLAUDE.md 写的规矩。

---

> "数据结构错了——同一个东西不该有两个名字。"
> "Silent fallback 是给懒人写的。Verilog 里宽度算错就是综合错，不能装聋作哑。"
