# VCGRuleManager 模块黑盒验证文档

## 1. 模块概述

**模块名称**: `VCGRuleManager`

**功能描述**: VCGRuleManager是一个用于Verilog代码生成的规则管理器，负责管理和应用信号连接、参数连接和线网生成的转换规则。该模块支持模式匹配、通配符替换、函数调用、注释保留等高级功能。

**核心职责**:
- 管理三类规则：信号规则(signal_rules)、参数规则(param_rules)、线网规则(wire_rules)
- 根据规则进行模式匹配和名称转换
- 处理端口方向约束
- 生成宽度相关的字面值
- 保留和恢复内联注释

---

## 2. 编程接口（公开API）

### 2.1 构造函数

```python
__init__(self)
```

**功能**: 初始化规则管理器

**输入**: 无

**输出**: VCGRuleManager实例

**副作用**: 初始化空的规则集合和日志记录器

---

### 2.2 规则添加接口

#### 2.2.1 add_signal_rule

```python
add_signal_rule(self, source_pattern: str, target_pattern: str, port_direction: Optional[str] = None)
```

**功能**: 添加信号连接规则

**参数**:
- `source_pattern` (str): 源信号名称模式（支持通配符 `*`）
- `target_pattern` (str): 目标信号名称模式（支持通配符替换、函数调用、内联注释）
- `port_direction` (Optional[str]): 端口方向约束，可选值：`'input'`, `'output'`, `'inout'`, `None`（不限制）

**返回值**: 无

**规则优先级**: 后添加的规则优先级更高（应用时从后向前匹配）

---

#### 2.2.2 add_param_rule

```python
add_param_rule(self, param_name: str, param_value: str)
```

**功能**: 添加参数连接规则

**参数**:
- `param_name` (str): 参数名称模式（支持通配符 `*`）
- `param_value` (str): 参数值（字符串形式）

**返回值**: 无

**规则优先级**: 后添加的规则优先级更高

---

#### 2.2.3 add_wire_rule

```python
add_wire_rule(self, port_pattern: str, wire_pattern: str, 
              width: Optional[str] = None, expression: Optional[str] = None)
```

**功能**: 添加线网生成规则

**参数**:
- `port_pattern` (str): 端口名称模式（支持通配符 `*`）
- `wire_pattern` (str): 线网名称模式（支持通配符替换、函数调用、内联注释）
- `width` (Optional[str]): 线网宽度（可选）
- `expression` (Optional[str]): 线网赋值表达式（可选，支持通配符替换）

**返回值**: 无

**规则优先级**: 后添加的规则优先级更高

---

### 2.3 规则应用接口

#### 2.3.1 resolve_signal_connection

```python
resolve_signal_connection(self, port: PortInfo) -> str
```

**功能**: 解析端口的信号连接名称

**参数**:
- `port` (PortInfo): 端口信息对象，需包含 `name`, `direction`, `port_type`, `width` 等属性

**返回值**: 
- (str) 解析后的信号连接名称
- 如果没有匹配的规则，返回原始端口名称

**匹配逻辑**:
1. 从后向前遍历信号规则（优先级高的先匹配）
2. 检查端口方向是否匹配（如果规则指定了方向约束）
3. 检查信号名称是否匹配源模式
4. 应用模式替换和函数调用
5. 处理字面值（'0'或'1'）
6. 恢复内联注释

---

#### 2.3.2 resolve_param_connection

```python
resolve_param_connection(self, param_name: str) -> Optional[str]
```

**功能**: 解析参数连接值

**参数**:
- `param_name` (str): 参数名称

**返回值**:
- (Optional[str]) 匹配的参数值，如果没有匹配规则则返回 `None`

**匹配逻辑**:
1. 从后向前遍历参数规则
2. 检查参数名称是否匹配模式
3. 返回第一个匹配的参数值

---

#### 2.3.3 resolve_wire_generation

```python
resolve_wire_generation(self, port: PortInfo, pattern: str = 'greedy') -> Tuple[str, Optional[str], Optional[str], bool]
```

**功能**: 解析线网生成信息

**参数**:
- `port` (PortInfo): 端口信息对象
- `pattern` (str): 生成模式，可选值：
  - `'greedy'`（默认）: 未匹配规则时使用端口名称作为线网名称
  - `'lazy'`: 未匹配规则时不生成线网

**返回值**: 元组 `(wire_name, width, expression, has_rule)`
- `wire_name` (str): 线网名称
- `width` (Optional[str]): 线网宽度
- `expression` (Optional[str]): 线网赋值表达式
- `has_rule` (bool): 是否匹配到规则

**特殊处理**:
- 对于 `PortType.INTERFACE` 类型的端口，不生成线网，返回 `("", None, None, False)`

---

### 2.4 工具接口

#### 2.4.1 reset

```python
reset(self)
```

**功能**: 清空所有规则

**参数**: 无

**返回值**: 无

---

#### 2.4.2 get_rules_summary

```python
get_rules_summary(self) -> Dict[str, int]
```

**功能**: 获取规则统计信息

**参数**: 无

**返回值**: 
```python
{
    'signal_rules': int,  # 信号规则数量
    'param_rules': int,   # 参数规则数量
    'wire_rules': int     # 线网规则数量
}
```

---

## 3. 功能点详细拆解

### 3.1 模式匹配功能

#### 3.1.1 精确匹配
- **功能**: 当模式中不包含通配符 `*` 时，进行精确字符串匹配
- **测试用例**:
  - 规则: `source="clk"`, `target="sys_clk"`
  - 输入: `"clk"` → 输出: `"sys_clk"`
  - 输入: `"clk_1"` → 输出: `"clk_1"` (不匹配)

#### 3.1.2 单通配符匹配
- **功能**: 模式中包含一个 `*`，捕获任意字符序列
- **测试用例**:
  - 规则: `source="i_*"`, `target="o_*"`
  - 输入: `"i_data"` → 输出: `"o_data"`
  - 输入: `"i_"` → 输出: `"o_"` (空字符串捕获)
  - 输入: `"i_test_signal"` → 输出: `"o_test_signal"`

#### 3.1.3 多通配符匹配
- **功能**: 模式中包含多个 `*`，按顺序捕获
- **测试用例**:
  - 规则: `source="*_*_in"`, `target="*_*_out"`
  - 输入: `"uart_data_in"` → 输出: `"uart_data_out"`
  - 输入: `"a_b_in"` → 输出: `"a_b_out"`

---

### 3.2 函数调用功能

#### 3.2.1 支持的函数列表
- `upper`: 转换为大写
- `lower`: 转换为小写
- `title`: 首字母大写
- `capitalize`: 首字符大写
- `replace(old, new)`: 字符串替换
- `strip()`, `lstrip()`, `rstrip()`: 去除空白

#### 3.2.2 函数调用语法
- **格式**: `${函数表达式}`
- **通配符引用**:
  - `*` 或 `*0`: 第一个捕获组
  - `*1`: 第二个捕获组
  - `*2`: 第三个捕获组，依此类推

#### 3.2.3 测试用例
- 规则: `source="*"`, `target="${upper(*)}"`
  - 输入: `"clk"` → 输出: `"CLK"`
  
- 规则: `source="*_*"`, `target="${upper(*0)}_${lower(*1)}"`
  - 输入: `"Clk_Data"` → 输出: `"CLK_data"`

- 规则: `source="*"`, `target="${replace(*, '_', '__')}"`
  - 输入: `"a_b"` → 输出: `"a__b"`

- 函数调用异常处理:
  - 规则: `source="*"`, `target="${invalid_func(*)}"`
  - 输入: `"test"` → 输出: `"test"` (异常回退到第一个捕获组)

---

### 3.3 端口方向约束功能

#### 3.3.1 不限制方向
- **条件**: `port_direction=None`
- **行为**: 匹配所有方向的端口
- **测试用例**:
  - 规则: `source="*"`, `target="sig_*"`, `port_direction=None`
  - 输入端口方向为 `input`: 匹配
  - 输入端口方向为 `output`: 匹配
  - 输入端口方向为 `None`: 匹配

#### 3.3.2 指定方向约束
- **条件**: `port_direction="input"` 或 `"output"` 或 `"inout"`
- **行为**: 仅匹配指定方向的端口（不区分大小写）
- **测试用例**:
  - 规则: `source="*"`, `target="i_*"`, `port_direction="input"`
  - 输入端口: `name="data"`, `direction="input"` → 输出: `"i_data"`
  - 输入端口: `name="data"`, `direction="output"` → 输出: `"data"` (不匹配)
  
  - 规则: `source="*"`, `target="o_*"`, `port_direction="OUTPUT"` (大小写)
  - 输入端口: `name="data"`, `direction="output"` → 输出: `"o_data"`

#### 3.3.3 端口无方向信息
- **条件**: 端口的 `direction=None`
- **行为**: 即使规则指定了方向约束，仍然允许匹配
- **测试用例**:
  - 规则: `source="*"`, `target="i_*"`, `port_direction="input"`
  - 输入端口: `name="data"`, `direction=None` → 输出: `"i_data"` (允许匹配)

---

### 3.4 字面值处理功能

#### 3.4.1 字面值识别
- **条件**: 转换结果为 `"0"` 或 `"1"`
- **行为**: 根据端口宽度生成对应的Verilog字面值

#### 3.4.2 宽度为1或空
- **测试用例**:
  - 端口: `width=1` 或 `width=None`, 目标值: `"0"` → 输出: `"1'b0"`
  - 端口: `width=1`, 目标值: `"1"` → 输出: `"1'b1"`

#### 3.4.3 宽度 ≤ 8
- **测试用例**:
  - 端口: `width=4`, 目标值: `"0"` → 输出: `"4'b0000"`
  - 端口: `width=8`, 目标值: `"1"` → 输出: `"8'b11111111"`

#### 3.4.4 宽度 > 8
- **测试用例**:
  - 端口: `width=16`, 目标值: `"0"` → 输出: `"{16{1'b0}}"`
  - 端口: `width=32`, 目标值: `"1"` → 输出: `"{32{1'b1}}"`

#### 3.4.5 表达式宽度
- **测试用例**:
  - 端口: `width="WIDTH"`, 目标值: `"0"` → 输出: `"{WIDTH{1'b0}}"`
  - 端口: `width="WIDTH+4"`, 目标值: `"1"` → 输出: `"{(WIDTH+4){1'b1}}"` (包含运算符需要括号)
  - 端口: `width="WIDTH*2-1"`, 目标值: `"0"` → 输出: `"{(WIDTH*2-1){1'b0}}"`

#### 3.4.6 非字面值
- **测试用例**:
  - 目标值: `"signal_name"` → 输出: `"signal_name"` (不转换)
  - 目标值: `"10"` → 输出: `"10"` (不转换)

---

### 3.5 内联注释处理功能

#### 3.5.1 注释提取
- **语法**: `/* 注释内容 */`
- **行为**: 在模式处理前提取注释，用占位符替换

#### 3.5.2 注释恢复
- **行为**: 在最终结果中恢复注释

#### 3.5.3 测试用例
- 规则: `source="*"`, `target="sig_* /* comment */"`
  - 输入: `"data"` → 输出: `"sig_data /* comment */"`

- 规则: `source="*_*"`, `target="*_*_out /* first */ /* second */"`
  - 输入: `"uart_tx"` → 输出: `"uart_tx_out /* first */ /* second */"`

- 多行注释:
  - 规则: `target="sig /* line1\nline2 */"`
  - 输出: `"sig /* line1\nline2 */"`

- 嵌套处理:
  - 规则: `source="*"`, `target="${upper(*)} /* UPPER */"`
  - 输入: `"clk"` → 输出: `"CLK /* UPPER */"`

---

### 3.6 规则优先级功能

#### 3.6.1 后添加优先
- **行为**: 规则按添加顺序存储，应用时从后向前匹配（最后添加的最先匹配）
- **测试用例**:
  ```python
  manager.add_signal_rule("*", "prefix1_*")
  manager.add_signal_rule("data", "special_data")
  ```
  - 输入: `"data"` → 输出: `"special_data"` (第二条规则优先)
  - 输入: `"clk"` → 输出: `"prefix1_clk"` (第一条规则匹配)

#### 3.6.2 方向约束与优先级
- **测试用例**:
  ```python
  manager.add_signal_rule("*", "sig_*", port_direction=None)
  manager.add_signal_rule("*", "input_*", port_direction="input")
  ```
  - 输入: `name="data"`, `direction="input"` → 输出: `"input_data"`
  - 输入: `name="data"`, `direction="output"` → 输出: `"sig_data"`

---

### 3.7 线网生成功能

#### 3.7.1 Greedy模式（默认）
- **行为**: 即使没有匹配的规则，也返回端口名称作为线网名称
- **测试用例**:
  - 无匹配规则，输入: `port.name="data"` → 输出: `("data", None, None, False)`

#### 3.7.2 Lazy模式
- **行为**: 没有匹配的规则时，不生成线网
- **测试用例**:
  - 无匹配规则，输入: `port.name="data"`, `pattern="lazy"` → 输出: `("", None, None, False)`

#### 3.7.3 Interface端口
- **行为**: 对于 `PortType.INTERFACE` 类型的端口，始终不生成线网
- **测试用例**:
  - 输入: `port.port_type=PortType.INTERFACE` → 输出: `("", None, None, False)`
  - 即使有匹配的规则，也不生成

#### 3.7.4 宽度指定
- **测试用例**:
  - 规则: `port_pattern="*"`, `wire_pattern="wire_*"`, `width="8"`
  - 输入: `"data"` → 输出: `("wire_data", "8", None, True)`

#### 3.7.5 表达式指定
- **测试用例**:
  - 规则: `port_pattern="*"`, `wire_pattern="wire_*"`, `expression="1'b0"`
  - 输入: `"rst"` → 输出: `("wire_rst", None, "1'b0", True)`

#### 3.7.6 表达式中的通配符替换
- **测试用例**:
  - 规则: `port_pattern="*_out"`, `wire_pattern="*_wire"`, `expression="*_in"`
  - 输入: `"data_out"` → 输出: `("data_wire", None, "data_in", True)`

---

### 3.8 参数解析功能

#### 3.8.1 基本匹配
- **测试用例**:
  - 规则: `param_name="WIDTH"`, `param_value="32"`
  - 输入: `"WIDTH"` → 输出: `"32"`

#### 3.8.2 通配符匹配
- **测试用例**:
  - 规则: `param_name="*_WIDTH"`, `param_value="16"`
  - 输入: `"DATA_WIDTH"` → 输出: `"16"`
  - 输入: `"ADDR_WIDTH"` → 输出: `"16"`

#### 3.8.3 无匹配规则
- **测试用例**:
  - 无规则，输入: `"UNKNOWN_PARAM"` → 输出: `None`

---

### 3.9 规则重置功能

#### 3.9.1 完全清空
- **测试用例**:
  ```python
  manager.add_signal_rule("*", "*_sig")
  manager.add_param_rule("WIDTH", "32")
  manager.add_wire_rule("*", "*_wire")
  manager.reset()
  summary = manager.get_rules_summary()
  ```
  - 预期: `summary == {'signal_rules': 0, 'param_rules': 0, 'wire_rules': 0}`

---

## 4. 边界条件测试

### 4.1 空字符串处理
- 规则: `source=""`, `target="default"`
  - 输入: `""` → 输出: `"default"`
- 规则: `source="*"`, `target=""`
  - 输入: `"any"` → 输出: `""`

### 4.2 特殊字符处理
- 正则特殊字符（不含`*`）:
  - 规则: `source="data[0]"`, `target="sig"`
  - 输入: `"data[0]"` → 输出: `"sig"`
  - 输入: `"data[1]"` → 输出: `"data[1]"` (不匹配)

### 4.3 Unicode字符
- 规则: `source="信号_*"`, `target="signal_*"`
  - 输入: `"信号_数据"` → 输出: `"signal_数据"`

### 4.4 极长字符串
- 规则: `source="*"`, `target="prefix_*"`
  - 输入: 10000字符的字符串 → 应正常处理

### 4.5 大量规则
- 添加1000+条规则，验证性能和正确性

### 4.6 嵌套函数调用
- 规则: `target="${upper(${lower(*)})}"`
  - 预期: 不支持嵌套，外层作为普通字符串

### 4.7 通配符替换数量限制

**规则**: 目标模式中可替换的通配符数量 = 源模式中的通配符数量

**测试用例**:

1. **单捕获组，多星号目标**
   - 规则: `source="*"`, `target="***"`
   - 输入: `"test"` → 输出: `"test**"`
   - 说明: 只有1个捕获组，只替换第一个 `*`

2. **双捕获组，多星号目标**
   - 规则: `source="*_*"`, `target="*-*-*-*"`
   - 输入: `"hello_world"` → 输出: `"hello-world-*-*"`
   - 说明: 有2个捕获组，只替换前两个 `*`

3. **捕获组多于目标星号**
   - 规则: `source="*_*_*"`, `target="*"`
   - 输入: `"a_b_c"` → 输出: `"a"`
   - 说明: 只使用第一个捕获组

4. **捕获组与星号匹配**
   - 规则: `source="*_*"`, `target="*-*"`
   - 输入: `"hello_world"` → 输出: `"hello-world"`
   - 说明: 2个捕获组替换2个星号，完美匹配

### 4.8 端口对象属性缺失
- `port.direction = None` → 应正常处理
- `port.width = None` → 字面值应生成 `"1'b0"`
- `port.name = ""` → 应正常匹配

### 4.9 宽度表达式边界
- `width = "0"` → 字面值: `"0'b0"` (Verilog非法，但应生成)
- `width = "-1"` → 字面值: `"{-1{1'b0}}"` (Verilog非法，但应生成)
- `width = "2**8"` → 字面值: `"{(2**8){1'b0}}"`

### 4.10 注释边界
- 单个 `/*` 无闭合 → 应不被识别为注释
- 空注释: `/**/` → 应正常提取和恢复
- 注释包含 `*/`: `/* comment */ extra */` → 匹配到第一个 `*/`

---

## 5. 测试用例设计建议

### 5.1 单元测试结构

```python
# 测试类结构建议
class TestVCGRuleManager:
    def setup_method(self):
        self.manager = VCGRuleManager()
        self.manager.reset()
    
    # 5.1.1 信号规则测试
    def test_signal_exact_match(self): ...
    def test_signal_wildcard_single(self): ...
    def test_signal_wildcard_multiple(self): ...
    def test_signal_direction_constraint(self): ...
    def test_signal_function_upper(self): ...
    def test_signal_function_replace(self): ...
    def test_signal_literal_zero(self): ...
    def test_signal_literal_one(self): ...
    def test_signal_comment_preservation(self): ...
    def test_signal_priority(self): ...
    
    # 5.1.2 参数规则测试
    def test_param_exact_match(self): ...
    def test_param_wildcard_match(self): ...
    def test_param_no_match(self): ...
    def test_param_priority(self): ...
    
    # 5.1.3 线网规则测试
    def test_wire_greedy_mode(self): ...
    def test_wire_lazy_mode(self): ...
    def test_wire_interface_port(self): ...
    def test_wire_with_width(self): ...
    def test_wire_with_expression(self): ...
    def test_wire_expression_substitution(self): ...
    
    # 5.1.4 边界测试
    def test_empty_string(self): ...
    def test_special_characters(self): ...
    def test_unicode(self): ...
    def test_many_rules(self): ...
    
    # 5.1.5 工具函数测试
    def test_reset(self): ...
    def test_get_summary(self): ...
```

### 5.2 集成测试场景

#### 场景1: 完整的信号连接工作流
```python
# 添加多条规则
manager.add_signal_rule("clk*", "sys_${upper(*)}", port_direction="input")
manager.add_signal_rule("*_in", "*_out")
manager.add_signal_rule("*", "default_*")

# 测试多个端口
ports = [
    PortInfo(name="clk", direction="input"),
    PortInfo(name="clk_ref", direction="input"),
    PortInfo(name="data_in", direction="output"),
    PortInfo(name="reset", direction="input"),
]

# 验证结果
```

#### 场景2: 混合规则类型
```python
# 同时使用信号、参数、线网规则
manager.add_signal_rule("*", "*_sig")
manager.add_param_rule("WIDTH", "32")
manager.add_wire_rule("*_out", "*_wire", width="WIDTH", expression="0")

# 测试完整流程
```

---

## 6. 验证检查清单

### 6.1 功能覆盖率
- [ ] 所有规则添加接口测试
- [ ] 所有规则应用接口测试
- [ ] 精确匹配测试
- [ ] 单通配符匹配测试
- [ ] 多通配符匹配测试
- [ ] 所有支持的函数测试
- [ ] 端口方向约束（input/output/inout/None）测试
- [ ] 字面值生成（所有宽度情况）测试
- [ ] 内联注释提取和恢复测试
- [ ] 规则优先级测试
- [ ] Greedy/Lazy模式测试
- [ ] Interface端口处理测试
- [ ] 规则重置测试

### 6.2 边界条件覆盖率
- [ ] 空字符串测试
- [ ] 特殊字符测试
- [ ] Unicode字符测试
- [ ] 极长字符串测试
- [ ] 大量规则测试
- [ ] 属性缺失测试
- [ ] 非法宽度表达式测试
- [ ] 注释边界测试

### 6.3 异常处理覆盖率
- [ ] 函数调用异常回退测试
- [ ] 无效函数名测试
- [ ] 无效函数参数测试

---

## 7. 预期行为总结表

| 功能 | 输入示例 | 规则示例 | 预期输出 |
|------|---------|---------|---------|
| 精确匹配 | `"clk"` | `source="clk"`, `target="sys_clk"` | `"sys_clk"` |
| 通配符 | `"i_data"` | `source="i_*"`, `target="o_*"` | `"o_data"` |
| 函数upper | `"data"` | `source="*"`, `target="${upper(*)}"` | `"DATA"` |
| 方向约束 | `name="a"`, `dir="input"` | `source="*"`, `target="i_*"`, `dir="input"` | `"i_a"` |
| 字面值宽度8 | `"0"`, `width=4` | `source="*"`, `target="0"` | `"4'b0000"` |
| 字面值宽度大 | `"1"`, `width=16` | `source="*"`, `target="1"` | `"{16{1'b1}}"` |
| 注释保留 | `"data"` | `source="*"`, `target="* /* cmt */"` | `"data /* cmt */"` |
| 无匹配(greedy) | `"unknown"` | 无规则 | `"unknown"` |
| 无匹配(lazy) | `"unknown"`, `pattern="lazy"` | 无规则 | `""` |
| Interface端口 | `port_type=INTERFACE` | 任意规则 | `("", None, None, False)` |

---

## 8. 依赖接口说明

### 8.1 PortInfo 对象要求

验证时需要模拟的 `PortInfo` 对象应包含以下属性:

```python
class PortInfo:
    name: str                    # 端口名称（必需）
    direction: Optional[str]     # 方向: "input"/"output"/"inout"/None
    port_type: PortType          # 端口类型枚举
    width: Optional[Union[int, str]]  # 宽度: 整数/表达式字符串/None
    interface_type: Optional[str]     # 接口类型（当port_type=INTERFACE时）
```

### 8.2 PortType 枚举

```python
class PortType(Enum):
    NORMAL = "normal"           # 普通端口
    INTERFACE = "interface"     # 接口端口
```

---

## 9. 日志验证

模块包含详细的日志记录，验证时可通过日志验证内部行为:
- DEBUG级别: 详细的匹配过程、替换步骤
- INFO级别: 规则添加、匹配成功
- WARNING级别: 函数调用失败回退

建议在验证时启用日志输出，辅助定位问题。

---

以上文档涵盖了 `VCGRuleManager` 的所有公开接口、功能点、边界条件和测试建议，可以作为黑盒验证的完整指导。