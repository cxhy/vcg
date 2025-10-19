# VerilogAST 模块黑盒验证文档（修订版）

## 1. 模块概述

VerilogAST 是一个用于解析 Verilog 抽象语法树的 Python 模块，主要功能是解析和管理 Verilog 模块的端口声明。

**支持的 Verilog 版本：**
- Verilog-95
- Verilog-2001

**测试范围说明：**
- ✅ **单bit端口** (SIMPLE)
- ✅ **向量端口** (VECTOR)
- ❌ **二维数组** (ARRAY_2D) - 不测试
- ❌ **三维数组** (ARRAY_3D) - 不测试
- ❌ **接口端口** (INTERFACE) - 不测试

---

## 2. 核心功能点

### 2.1 端口类型识别（测试范围）

模块支持以下**需要测试**的端口类型：

| 端口类型 | 枚举值 | 描述 | 示例 | 测试状态 |
|---------|--------|------|------|----------|
| SIMPLE | `PortType.SIMPLE` | 单 bit 端口 | `input clk` | ✅ 需测试 |
| VECTOR | `PortType.VECTOR` | 向量端口 | `input [7:0] data` | ✅ 需测试 |
| ARRAY_2D | `PortType.ARRAY_2D` | 二维数组 | `input [7:0] mem [0:15]` | ❌ 不测试 |
| ARRAY_3D | `PortType.ARRAY_3D` | 三维数组及以上 | `input [7:0] mem [0:15][0:7]` | ❌ 不测试 |
| INTERFACE | `PortType.INTERFACE` | 接口端口 | SystemVerilog接口 | ❌ 不测试 |

### 2.2 端口方向支持

| 方向 | 枚举值 | 说明 |
|-----|--------|------|
| INPUT | `PortDirection.INPUT` | 输入端口 |
| OUTPUT | `PortDirection.OUTPUT` | 输出端口 |
| INOUT | `PortDirection.INOUT` | 双向端口 |

### 2.3 表达式计算功能

支持端口宽度表达式的自动计算：

**支持的表达式类型：**
1. **常量表达式**：`[7:0]`, `[15:0]`, `[31:0]`
2. **参数表达式**：`[N-1:0]`, `[WIDTH-1:0]`
3. **算术表达式**：`[2*WIDTH-1:0]`, `[WIDTH+HEIGHT-1:0]`
4. **系统函数**：`[$clog2(DEPTH)-1:0]` 等 Verilog 系统函数
5. **复杂表达式**：嵌套的数学运算

**计算结果类型：**
- `int`：可完全计算的整数结果
- `float`：浮点数结果（边界情况）
- `str`：无法完全计算的表达式字符串

### 2.4 网络类型支持

支持 Verilog 网络类型声明：
- `wire`（默认）
- `reg`
- 其他用户定义类型

---

## 3. 编程接口（API）

### 3.1 VerilogASTBuilder（构建器模式）

**用途**：用于逐步构建 Verilog AST

#### 3.1.1 创建构建器
```python
builder = VerilogASTBuilder()
```

#### 3.1.2 设置模块名
```python
builder.set_module_name(name: str) -> VerilogASTBuilder
```
- **参数**：`name` - 模块名称字符串
- **返回**：返回 self 支持链式调用
- **异常**：如果模块名已设置，抛出 `ValueError`
- **边界条件**：
  - 只能调用一次
  - 模块名不能为空字符串（build 时检查）

#### 3.1.3 添加参数
```python
builder.add_parameter(name: str, **kwargs) -> VerilogASTBuilder
```
- **参数**：
  - `name`：参数名称（必需）
  - `param_type`：参数类型（可选，默认 "parameter"）
  - `default_value`：默认值（可选，默认 ""）
  - `data_type`：数据类型（可选）
- **返回**：返回 self 支持链式调用
- **行为**：重复添加同名参数会覆盖，但保持首次出现的顺序位置

#### 3.1.4 添加/更新端口
```python
builder.add_port(name: str, **kwargs) -> VerilogASTBuilder
builder.update_port(name: str, **kwargs) -> VerilogASTBuilder
```
- **参数**（所有参数均可选）：
  - `direction`：端口方向（"input"/"output"/"inout"）
  - `net_type`：网络类型（"wire"/"reg" 等）
  - `msb_expr`：最高位表达式（字符串）
  - `lsb_expr`：最低位表达式（字符串）
  - ~~`array_dims`~~：数组维度列表（不测试）
  - ~~`interface_type`~~：接口类型（不测试）
- **返回**：返回 self 支持链式调用
- **行为**：
  - `add_port` 和 `update_port` 功能相同
  - 可分多次调用累积设置端口属性
  - 只更新非 None 的属性值

#### 3.1.5 构建 AST
```python
ast = builder.build() -> VerilogAST
```
- **返回**：VerilogAST 对象
- **异常**：
  - 如果模块名未设置：抛出 `VerilogASTError("Module name not set")`
  - 如果已经 build 过：抛出 `VerilogASTError("Builder already built")`
- **边界条件**：
  - 只能调用一次
  - 必须先设置模块名

#### 3.1.6 重置构建器
```python
builder.reset() -> VerilogASTBuilder
```
- **功能**：清空所有数据，可重新使用
- **返回**：返回 self

### 3.2 VerilogAST（AST 对象）

#### 3.2.1 创建 AST
```python
ast = VerilogAST(module_name: str = "")
```
- **参数**：`module_name` - 模块名（可选）

#### 3.2.2 获取端口信息
```python
ports = ast.get_port_info() -> List[PortInfo]
```
- **返回**：PortInfo 对象列表，按添加顺序排列

#### 3.2.3 获取参数信息
```python
params = ast.get_parameter_info() -> List[ParameterInfo]
```
- **返回**：ParameterInfo 对象列表，按添加顺序排列

#### 3.2.4 获取完整模块信息
```python
info = ast.get_module_info() -> Dict[str, Any]
```
- **返回**：字典包含：
  - `"name"`：模块名（字符串）
  - `"parameters"`：参数列表（List[ParameterInfo]）
  - `"ports"`：端口列表（List[PortInfo]）
  - `"port_summary"`：端口统计信息（字典）
    - `"total"`：总端口数
    - `"input"`：输入端口数
    - `"output"`：输出端口数
    - `"inout"`：双向端口数

### 3.3 PortInfo（端口信息对象）

#### 3.3.1 基本属性
- `name`：端口名称
- `direction`：端口方向（"input"/"output"/"inout" 或 None）
- `net_type`：网络类型（"wire"/"reg" 等）
- `msb_expr`：最高位表达式（字符串或 None）
- `lsb_expr`：最低位表达式（字符串或 None）

#### 3.3.2 计算属性

**port_type**（只读属性）
```python
port_type: PortType
```
- **返回**：端口类型枚举
- **判断逻辑（针对测试范围）**：
  1. 如果 `msb_expr` 和 `lsb_expr` 都存在且不为空 → `VECTOR`
  2. 否则 → `SIMPLE`

**is_complete**（只读属性）
```python
is_complete: bool
```
- **返回**：端口是否完整（direction 不为 None）

**width**（只读属性）
```python
width: Union[int, str, float]
```
- **返回**：端口宽度
- **计算规则**：
  - **SIMPLE 类型**：返回整数 `1`
  - **VECTOR 类型**：返回计算后的宽度
    - 如果能完全计算：返回整数（`abs(msb - lsb) + 1`）
    - 特殊优化：如果 `lsb=0` 且 `msb` 以 `"-1"` 结尾，返回参数名（如 "N-1:0" → "N"）
    - 无法完全计算：返回表达式字符串

**range_string**（只读属性）
```python
range_string: str
```
- **返回**：端口范围字符串
- **格式**：
  - **VECTOR**：`"[msb_expr:lsb_expr]"`
  - **SIMPLE**：`""`（空字符串）

### 3.4 ParameterInfo（参数信息对象）

#### 3.4.1 属性
- `name`：参数名称
- `param_type`：参数类型（"parameter" 或 "localparam"）
- `default_value`：默认值（字符串）
- `data_type`：数据类型（可选）

---

## 4. 测试用例分类

### 4.1 功能测试用例

#### 4.1.1 SIMPLE 端口测试

**测试点 1：基本单bit输入端口**
```python
builder.add_port("clk", direction="input")
# 验证：
# - port_type == PortType.SIMPLE
# - width == 1
# - range_string == ""
# - is_complete == True
```

**测试点 2：基本单bit输出端口**
```python
builder.add_port("valid", direction="output")
# 验证：
# - port_type == PortType.SIMPLE
# - direction == "output"
# - width == 1
```

**测试点 3：双向单bit端口**
```python
builder.add_port("sda", direction="inout")
# 验证：
# - port_type == PortType.SIMPLE
# - direction == "inout"
```

**测试点 4：带网络类型的单bit端口**
```python
builder.add_port("flag", direction="output", net_type="reg")
# 验证：
# - net_type == "reg"
# - port_type == PortType.SIMPLE
```

**测试点 5：无方向的端口（不完整）**
```python
builder.add_port("unknown")
# 验证：
# - is_complete == False
# - direction == None
```

#### 4.1.2 VECTOR 端口测试

**测试点 1：标准向量端口（降序）**
```python
builder.add_port("data", direction="input", msb_expr="7", lsb_expr="0")
# 验证：
# - port_type == PortType.VECTOR
# - width == 8
# - range_string == "[7:0]"
```

**测试点 2：标准向量端口（升序）**
```python
builder.add_port("addr", direction="input", msb_expr="0", lsb_expr="7")
# 验证：
# - port_type == PortType.VECTOR
# - width == 8 (abs(0-7)+1)
```

**测试点 3：不同宽度的向量**
```python
# 16位
builder.add_port("data16", direction="input", msb_expr="15", lsb_expr="0")
# 验证：width == 16

# 32位
builder.add_port("data32", direction="output", msb_expr="31", lsb_expr="0")
# 验证：width == 32

# 64位
builder.add_port("data64", direction="inout", msb_expr="63", lsb_expr="0")
# 验证：width == 64
```

**测试点 4：非零起始位的向量**
```python
builder.add_port("slice", direction="input", msb_expr="31", lsb_expr="16")
# 验证：
# - width == 16
# - range_string == "[31:16]"
```

**测试点 5：向量端口带网络类型**
```python
builder.add_port("reg_data", direction="output", msb_expr="7", lsb_expr="0", net_type="reg")
# 验证：
# - net_type == "reg"
# - port_type == PortType.VECTOR
```

#### 4.1.3 参数表达式测试

**测试点 1：简单参数表达式（特殊优化）**
```python
builder.add_port("data", direction="input", msb_expr="N-1", lsb_expr="0")
# 验证：
# - width == "N" (特殊优化)
# - range_string == "[N-1:0]"
```

**测试点 2：其他参数名**
```python
builder.add_port("data", direction="input", msb_expr="WIDTH-1", lsb_expr="0")
# 验证：width == "WIDTH"

builder.add_port("addr", direction="input", msb_expr="ADDR_WIDTH-1", lsb_expr="0")
# 验证：width == "ADDR_WIDTH"
```

**测试点 3：算术表达式**
```python
builder.add_port("data", direction="input", msb_expr="2*WIDTH-1", lsb_expr="0")
# 验证：
# - width == "2*WIDTH" 或计算结果
# - range_string == "[2*WIDTH-1:0]"
```

**测试点 4：复合参数表达式**
```python
builder.add_port("data", direction="input", msb_expr="WIDTH+HEIGHT-1", lsb_expr="0")
# 验证：
# - width 为表达式字符串或计算结果
```

**测试点 5：系统函数表达式**
```python
builder.add_port("addr", direction="input", msb_expr="$clog2(DEPTH)-1", lsb_expr="0")
# 验证：
# - width 包含 "$clog2(DEPTH)"
# - range_string == "[$clog2(DEPTH)-1:0]"
```

**测试点 6：非零起始的参数表达式**
```python
builder.add_port("data", direction="input", msb_expr="WIDTH-1", lsb_expr="4")
# 验证：
# - width 为表达式 "(WIDTH-1)-(4)+1" 的计算结果
```

#### 4.1.4 端口方向完整性测试

**测试点 1：三种方向全覆盖**
```python
builder.add_port("in_port", direction="input")
builder.add_port("out_port", direction="output")
builder.add_port("inout_port", direction="inout")

ast = builder.build()
summary = ast.get_module_info()["port_summary"]
# 验证：
# - summary["input"] == 1
# - summary["output"] == 1
# - summary["inout"] == 1
# - summary["total"] == 3
```

**测试点 2：大小写不敏感**
```python
builder.add_port("port1", direction="INPUT")
builder.add_port("port2", direction="Output")
builder.add_port("port3", direction="InOut")
# 验证：统计时正确识别（内部转小写）
```

#### 4.1.5 网络类型测试

**测试点 1：默认网络类型**
```python
builder.add_port("data", direction="input", msb_expr="7", lsb_expr="0")
ast = builder.build()
port = ast.get_port_info()[0]
# 验证：port.net_type == "wire" (默认值)
```

**测试点 2：显式指定 wire**
```python
builder.add_port("data", direction="input", net_type="wire")
# 验证：net_type == "wire"
```

**测试点 3：指定 reg**
```python
builder.add_port("data", direction="output", net_type="reg")
# 验证：net_type == "reg"
```

**测试点 4：用户自定义类型**
```python
builder.add_port("data", direction="output", net_type="logic")
# 验证：net_type == "logic"
```

#### 4.1.6 参数管理测试

**测试点 1：添加基本参数**
```python
builder.add_parameter("WIDTH", default_value="8")
ast = builder.build()
params = ast.get_parameter_info()
# 验证：
# - len(params) == 1
# - params[0].name == "WIDTH"
# - params[0].default_value == "8"
# - params[0].param_type == "parameter"
```

**测试点 2：添加 localparam**
```python
builder.add_parameter("DEPTH", param_type="localparam", default_value="1024")
ast = builder.build()
param = ast.get_parameter_info()[0]
# 验证：
# - param.param_type == "localparam"
```

**测试点 3：多个参数顺序**
```python
builder.add_parameter("WIDTH", default_value="8")
builder.add_parameter("HEIGHT", default_value="16")
builder.add_parameter("DEPTH", default_value="32")
ast = builder.build()
params = ast.get_parameter_info()
# 验证：参数顺序与添加顺序一致
```

#### 4.1.7 多次更新测试

**测试点 1：分步构建单bit端口**
```python
builder.add_port("clk")
builder.update_port("clk", direction="input")
ast = builder.build()
port = ast.get_port_info()[0]
# 验证：
# - port.name == "clk"
# - port.direction == "input"
# - port.is_complete == True
```

**测试点 2：分步构建向量端口**
```python
builder.add_port("data")
builder.update_port("data", direction="output")
builder.update_port("data", msb_expr="7", lsb_expr="0")
builder.update_port("data", net_type="reg")
ast = builder.build()
port = ast.get_port_info()[0]
# 验证：
# - port_type == PortType.VECTOR
# - direction == "output"
# - width == 8
# - net_type == "reg"
```

**测试点 3：部分更新不覆盖已有属性**
```python
builder.add_port("data", direction="input", msb_expr="7")
builder.update_port("data", lsb_expr="0")  # 不影响 direction 和 msb_expr
ast = builder.build()
port = ast.get_port_info()[0]
# 验证：
# - direction == "input"
# - msb_expr == "7"
# - lsb_expr == "0"
```

### 4.2 边界条件测试

#### 4.2.1 Builder 状态管理

**测试点 1：重复设置模块名**
```python
builder.set_module_name("module1")
try:
    builder.set_module_name("module2")
    # 应抛出 ValueError
except ValueError as e:
    # 验证：异常消息包含 "already set"
    pass
```

**测试点 2：未设置模块名就 build**
```python
builder.add_port("clk", direction="input")
try:
    ast = builder.build()
    # 应抛出 VerilogASTError
except VerilogASTError as e:
    # 验证：异常消息 "Module name not set"
    pass
```

**测试点 3：重复 build**
```python
builder.set_module_name("test")
ast1 = builder.build()
try:
    ast2 = builder.build()
    # 应抛出 VerilogASTError
except VerilogASTError as e:
    # 验证：异常消息 "Builder already built"
    pass
```

**测试点 4：reset 后重用**
```python
builder.set_module_name("module1")
builder.add_port("clk", direction="input")
ast1 = builder.build()

builder.reset()

builder.set_module_name("module2")
builder.add_port("rst", direction="input")
ast2 = builder.build()

# 验证：
# - ast1.module_name == "module1"
# - ast2.module_name == "module2"
# - 两个 AST 独立，互不影响
```

**测试点 5：空模块名**
```python
builder.set_module_name("")
try:
    ast = builder.build()
    # 验证：可能成功或失败（取决于实现）
except VerilogASTError:
    pass
```

#### 4.2.2 端口顺序测试

**测试点 1：端口添加顺序保持**
```python
builder.add_port("port1", direction="input")
builder.add_port("port2", direction="output")
builder.add_port("port3", direction="inout")
builder.add_port("port4", direction="input")
ast = builder.build()
ports = ast.get_port_info()

# 验证：
# - ports[0].name == "port1"
# - ports[1].name == "port2"
# - ports[2].name == "port3"
# - ports[3].name == "port4"
```

**测试点 2：参数添加顺序保持**
```python
builder.add_parameter("PARAM_A", default_value="1")
builder.add_parameter("PARAM_B", default_value="2")
builder.add_parameter("PARAM_C", default_value="3")
ast = builder.build()
params = ast.get_parameter_info()

# 验证：顺序为 PARAM_A, PARAM_B, PARAM_C
```

#### 4.2.3 重复名称测试

**测试点 1：重复添加端口（覆盖行为）**
```python
builder.add_port("data", direction="input")
builder.add_port("data", direction="output", msb_expr="7", lsb_expr="0")
ast = builder.build()
ports = ast.get_port_info()

# 验证：
# - len(ports) == 1 (只有一个 data)
# - ports[0].direction == "output"
# - ports[0].port_type == PortType.VECTOR
```

**测试点 2：重复添加参数（覆盖行为）**
```python
builder.add_parameter("WIDTH", default_value="8")
builder.add_parameter("WIDTH", default_value="16")
ast = builder.build()
params = ast.get_parameter_info()

# 验证：
# - len(params) == 1
# - params[0].default_value == "16"
```

**测试点 3：顺序在覆盖后保持**
```python
builder.add_port("port1", direction="input")
builder.add_port("port2", direction="output")
builder.add_port("port1", direction="inout")  # 覆盖
ast = builder.build()
ports = ast.get_port_info()

# 验证：
# - len(ports) == 2
# - ports[0].name == "port1" (顺序不变)
# - ports[0].direction == "inout" (内容更新)
# - ports[1].name == "port2"
```

#### 4.2.4 空值和 None 测试

**测试点 1：空字符串表达式**
```python
builder.add_port("data", direction="input", msb_expr="", lsb_expr="")
ast = builder.build()
port = ast.get_port_info()[0]

# 验证：
# - port_type == PortType.SIMPLE (空表达式视为无表达式)
# - width == 1
```

**测试点 2：None 值不覆盖**
```python
builder.add_port("data", direction="input", msb_expr="7", lsb_expr="0")
builder.update_port("data", msb_expr=None)  # None 不应覆盖
ast = builder.build()
port = ast.get_port_info()[0]

# 验证：
# - msb_expr == "7" (未被覆盖)
```

**测试点 3：只有 msb 无 lsb**
```python
builder.add_port("data", direction="input", msb_expr="7")
ast = builder.build()
port = ast.get_port_info()[0]

# 验证：
# - port_type == PortType.SIMPLE (缺少 lsb)
# - width == 1
```

**测试点 4：只有 lsb 无 msb**
```python
builder.add_port("data", direction="input", lsb_expr="0")
ast = builder.build()
port = ast.get_port_info()[0]

# 验证：
# - port_type == PortType.SIMPLE
# - width == 1
```

#### 4.2.5 极端宽度测试

**测试点 1：最小宽度（1bit向量）**
```python
builder.add_port("data", direction="input", msb_expr="0", lsb_expr="0")
ast = builder.build()
port = ast.get_port_info()[0]

# 验证：
# - port_type == PortType.VECTOR
# - width == 1
```

**测试点 2：大宽度向量**
```python
# 128位
builder.add_port("data128", direction="input", msb_expr="127", lsb_expr="0")
# 验证：width == 128

# 256位
builder.add_port("data256", direction="input", msb_expr="255", lsb_expr="0")
# 验证：width == 256
```

**测试点 3：零端口模块**
```python
builder.set_module_name("empty_module")
ast = builder.build()
ports = ast.get_port_info()

# 验证：
# - len(ports) == 0
# - summary["total"] == 0
```

**测试点 4：大量端口**
```python
for i in range(100):
    builder.add_port(f"port{i}", direction="input")
ast = builder.build()
ports = ast.get_port_info()

# 验证：
# - len(ports) == 100
# - 顺序正确
```

### 4.3 集成测试用例

#### 4.3.1 Verilog-95 风格模块

**场景**：端口列表只有名称，后续声明方向和类型

```python
builder = VerilogASTBuilder()
builder.set_module_name("counter_v95")

# 第一阶段：端口列表（只有名称）
builder.add_port("clk")
builder.add_port("rst")
builder.add_port("enable")
builder.add_port("count")

# 第二阶段：端口声明（补充方向和类型）
builder.update_port("clk", direction="input")
builder.update_port("rst", direction="input")
builder.update_port("enable", direction="input")
builder.update_port("count", direction="output", msb_expr="7", lsb_expr="0", net_type="reg")

ast = builder.build()

# 验证：
# - 4个端口全部完整
# - 顺序正确
# - count 为 8bit 输出寄存器
```

#### 4.3.2 Verilog-2001 风格模块

**场景**：端口列表直接包含完整声明

```python
builder = VerilogASTBuilder()
builder.set_module_name("adder_v2001")

# 直接添加完整端口
builder.add_port("clk", direction="input")
builder.add_port("rst_n", direction="input")
builder.add_port("a", direction="input", msb_expr="7", lsb_expr="0")
builder.add_port("b", direction="input", msb_expr="7", lsb_expr="0")
builder.add_port("sum", direction="output", msb_expr="8", lsb_expr="0", net_type="wire")
builder.add_port("carry", direction="output")

ast = builder.build()

# 验证：
# - 所有端口一次性完整
# - a, b 为 8bit 输入
# - sum 为 9bit 输出
# - carry 为 1bit 输出
```

#### 4.3.3 带参数的复杂模块

```python
builder = VerilogASTBuilder()
builder.set_module_name("fifo")

# 添加参数
builder.add_parameter("DATA_WIDTH", default_value="8")
builder.add_parameter("ADDR_WIDTH", default_value="4")
builder.add_parameter("DEPTH", param_type="localparam", default_value="16")

# 添加端口
builder.add_port("clk", direction="input")
builder.add_port("rst_n", direction="input")
builder.add_port("wr_en", direction="input")
builder.add_port("rd_en", direction="input")
builder.add_port("wr_data", direction="input", msb_expr="DATA_WIDTH-1", lsb_expr="0")
builder.add_port("rd_data", direction="output", msb_expr="DATA_WIDTH-1", lsb_expr="0", net_type="reg")
builder.add_port("full", direction="output")
builder.add_port("empty", direction="output")

ast = builder.build()
info = ast.get_module_info()

# 验证：
# - 模块名：fifo
# - 参数数量：3
# - 端口数量：8
# - 输入端口：5
# - 输出端口：3
# - wr_data, rd_data 宽度为 "DATA_WIDTH"
```

#### 4.3.4 混合风格模块

```python
builder = VerilogASTBuilder()
builder.set_module_name("mixed_style")

# 部分端口先声明名称
builder.add_port("clk")
builder.add_port("rst")

# 部分端口直接完整声明
builder.add_port("data_in", direction="input", msb_expr="31", lsb_expr="0")
builder.add_port("data_out", direction="output", msb_expr="31", lsb_expr="0")

# 补充前面端口的属性
builder.update_port("clk", direction="input")
builder.update_port("rst", direction="input")

ast = builder.build()

# 验证：
# - 所有端口最终完整
# - 顺序：clk, rst, data_in, data_out
```

### 4.4 表达式计算专项测试

#### 4.4.1 常量计算测试

| msb_expr | lsb_expr | 期望 width | 说明 |
|----------|----------|-----------|------|
| "7" | "0" | 8 | 标准8位 |
| "15" | "0" | 16 | 标准16位 |
| "31" | "0" | 32 | 标准32位 |
| "63" | "0" | 64 | 标准64位 |
| "0" | "7" | 8 | 反向范围 |
| "31" | "16" | 16 | 非零起始 |
| "0" | "0" | 1 | 单bit向量 |
| "10" | "5" | 6 | 任意范围 |

#### 4.4.2 参数表达式测试

| msb_expr | lsb_expr | 期望 width | 说明 |
|----------|----------|-----------|------|
| "N-1" | "0" | "N" | 特殊优化 |
| "WIDTH-1" | "0" | "WIDTH" | 特殊优化 |
| "DATA_WIDTH-1" | "0" | "DATA_WIDTH" | 特殊优化 |
| "2*N-1" | "0" | "2*N" | 算术表达式 |
| "N+M-1" | "0" | "N+M" 或计算值 | 复合表达式 |
| "N" | "M" | "(N)-(M)+1" | 双参数 |
| "$clog2(DEPTH)-1" | "0" | "$clog2(DEPTH)" | 系统函数 |

#### 4.4.3 边界表达式测试

```python
# 空字符串
builder.add_port("p1", direction="input", msb_expr="", lsb_expr="")
# 验证：port_type == SIMPLE, width == 1

# 空白字符
builder.add_port("p2", direction="input", msb_expr="  ", lsb_expr="  ")
# 验证：port_type == SIMPLE, width == 1

# 复杂嵌套
builder.add_port("p3", direction="input", msb_expr="(WIDTH*2+HEIGHT)-1", lsb_expr="0")
# 验证：width 为表达式或计算结果

# 浮点数（边界情况）
builder.add_port("p4", direction="input", msb_expr="7.5", lsb_expr="0")
# 验证：width 处理浮点数
```

---

## 5. 验证检查清单

### 5.1 端口类型判断（覆盖 2 种类型）

- [ ] **SIMPLE 类型识别**
  - [ ] 无 msb/lsb 表达式
  - [ ] msb 或 lsb 为 None
  - [ ] msb 或 lsb 为空字符串
  - [ ] 只有 msb 无 lsb
  - [ ] 只有 lsb 无 msb

- [ ] **VECTOR 类型识别**
  - [ ] msb 和 lsb 都存在且非空
  - [ ] 常量表达式
  - [ ] 参数表达式
  - [ ] 算术表达式
  - [ ] 系统函数表达式

### 5.2 宽度计算分支覆盖

- [ ] **SIMPLE 端口宽度**
  - [ ] 返回整数 1

- [ ] **VECTOR 端口宽度**
  - [ ] 常量计算（返回 int）
  - [ ] 参数表达式特殊优化（"N-1:0" → "N"）
  - [ ] 一般参数表达式（返回 str）
  - [ ] 算术表达式计算
  - [ ] 系统函数保留
  - [ ] 无法计算的表达式（返回原字符串）
  - [ ] 浮点数结果（边界）
  - [ ] 反向范围（msb < lsb）

### 5.3 端口方向覆盖

- [ ] INPUT 方向
- [ ] OUTPUT 方向
- [ ] INOUT 方向
- [ ] 无方向（None）
- [ ] 大小写变体（INPUT/input/Input）

### 5.4 网络类型覆盖

- [ ] 默认类型（wire）
- [ ] 显式 wire
- [ ] reg 类型
- [ ] 用户自定义类型
- [ ] None 值处理

### 5.5 Builder 状态机覆盖

- [ ] **初始状态**
  - [ ] 未设置模块名
  - [ ] 空参数列表
  - [ ] 空端口列表
  - [ ] _built = False

- [ ] **构建中状态**
  - [ ] 已设置模块名
  - [ ] 添加参数后
  - [ ] 添加端口后

- [ ] **已构建状态**
  - [ ] _built = True
  - [ ] 不可重复 build

- [ ] **重置状态**
  - [ ] reset 后回到初始状态
  - [ ] 可重新使用

### 5.6 数据完整性验证

- [ ] **端口顺序**
  - [ ] 添加顺序保持
  - [ ] 更新不改变顺序
  - [ ] 覆盖保持原顺序位置

- [ ] **参数顺序**
  - [ ] 添加顺序保持
  - [ ] 覆盖保持原顺序位置

- [ ] **重复名称处理**
  - [ ] 端口覆盖行为
  - [ ] 参数覆盖行为
  - [ ] 顺序不变

- [ ] **部分更新**
  - [ ] None 值不覆盖
  - [ ] 只更新非 None 属性

### 5.7 统计信息验证

- [ ] 总端口数正确
- [ ] 输入端口数正确
- [ ] 输出端口数正确
- [ ] 双向端口数正确
- [ ] 无方向端口不计入分类统计
- [ ] 方向大小写不敏感

### 5.8 异常处理覆盖

- [ ] 重复设置模块名（ValueError）
- [ ] 未设置模块名 build（VerilogASTError）
- [ ] 重复 build（VerilogASTError）
- [ ] 异常消息正确

---

## 6. 测试数据集

### 6.1 端口名称数据集

```python
# 基本名称
["clk", "rst", "data", "addr", "valid", "ready"]

# 下划线命名
["rst_n", "data_in", "data_out", "wr_en", "rd_en", "addr_bus"]

# 数字后缀
["port0", "port1", "data_32bit", "addr_16"]

# 大小写混合
["CLK", "Rst", "Data", "ADDR_BUS", "Valid_Out"]

# 特殊前缀
["i_clk", "o_data", "io_bus", "s_signal", "m_master"]
```

### 6.2 表达式数据集

**常量表达式**
```python
[
    ("7", "0"),      # 8位
    ("15", "0"),     # 16位
    ("31", "0"),     # 32位
    ("63", "0"),     # 64位
    ("127", "0"),    # 128位
    ("0", "7"),      # 反向
    ("31", "16"),    # 非零起始
    ("0", "0"),      # 单bit
]
```

**参数表达式**
```python
[
    ("N-1", "0"),              # 基本参数
    ("WIDTH-1", "0"),          # WIDTH参数
    ("DATA_WIDTH-1", "0"),     # 长参数名
    ("ADDR_WIDTH-1", "0"),     # 地址宽度
    ("2*WIDTH-1", "0"),        # 算术
    ("WIDTH+HEIGHT-1", "0"),   # 复合
    ("$clog2(DEPTH)-1", "0"),  # 系统函数
]
```

### 6.3 边界值数据集

```python
# 端口数量
[0, 1, 10, 50, 100]

# 参数数量
[0, 1, 5, 20]

# 端口宽度
[1, 8, 16, 32, 64, 128, 256]

# 模块名长度
["a", "mod", "my_module", "very_long_module_name_test_123"]
```

---

## 7. 验证策略建议

### 7.1 单元测试策略

**测试粒度**：每个公共方法独立测试

1. **VerilogASTBuilder 类**
   - `set_module_name()` - 5个测试用例
   - `add_parameter()` - 8个测试用例
   - `add_port()` - 15个测试用例
   - `update_port()` - 10个测试用例
   - `build()` - 10个测试用例
   - `reset()` - 5个测试用例

2. **PortInfo 类**
   - `port_type` 属性 - 6个测试用例
   - `is_complete` 属性 - 4个测试用例
   - `width` 属性 - 15个测试用例
   - `range_string` 属性 - 6个测试用例

3. **VerilogAST 类**
   - `get_port_info()` - 5个测试用例
   - `get_parameter_info()` - 5个测试用例
   - `get_module_info()` - 8个测试用例

### 7.2 集成测试策略

**测试场景**：模拟真实 Verilog 模块解析

1. **简单模块**（3-5个端口）
   - 纯 SIMPLE 端口
   - 纯 VECTOR 端口
   - 混合端口

2. **中等复杂度模块**（10-20个端口）
   - Verilog-95 风格
   - Verilog-2001 风格
   - 混合风格

3. **复杂模块**（20+个端口）
   - 带多个参数
   - 参数化端口宽度
   - 多种网络类型

### 7.3 回归测试策略

**测试库构建**：
- 收集典型的开源 Verilog 模块
- 提取端口声明部分
- 建立标准测试用例库


### 7.4 边界测试策略

**极端场景**：
- 空模块（0端口）
- 单端口模块
- 大量端口（100+）
- 超长参数名
- 超长模块名
- 复杂嵌套表达式

### 7.5 错误处理测试策略

**异常触发测试**：
- 每个可能抛出异常的路径都要测试
- 验证异常类型正确
- 验证异常消息有意义

---

## 8. 测试执行建议

### 8.1 测试优先级

**P0 - 核心功能（必须测试）**
- SIMPLE 端口识别
- VECTOR 端口识别
- 常量宽度计算
- Builder 基本流程
- 端口方向识别

**P1 - 重要功能（应该测试）**
- 参数表达式计算
- 参数管理
- 端口顺序
- 重复名称处理
- 异常处理

**P2 - 次要功能（可选测试）**
- 网络类型多样性
- 复杂表达式
- 极端边界值
- 性能测试

### 8.2 测试覆盖率目标

- **代码覆盖率**：≥ 90%（SIMPLE 和 VECTOR 相关代码）
- **分支覆盖率**：≥ 85%
- **功能点覆盖率**：100%（核心功能）

## 9. 快速验证示例

### 9.1 基本验证流程

```python
# 1. 创建 Builder
builder = VerilogASTBuilder()

# 2. 设置模块名
builder.set_module_name("test_module")

# 3. 添加参数
builder.add_parameter("DATA_WIDTH", default_value="8")

# 4. 添加 SIMPLE 端口
builder.add_port("clk", direction="input")
builder.add_port("rst_n", direction="input")

# 5. 添加 VECTOR 端口
builder.add_port("data_in", direction="input", msb_expr="DATA_WIDTH-1", lsb_expr="0")
builder.add_port("data_out", direction="output", msb_expr="7", lsb_expr="0", net_type="reg")

# 6. 构建 AST
ast = builder.build()

# 7. 验证结果
ports = ast.get_port_info()
assert len(ports) == 4

# 验证第一个端口（SIMPLE）
assert ports[0].name == "clk"
assert ports[0].port_type == PortType.SIMPLE
assert ports[0].width == 1
assert ports[0].range_string == ""

# 验证第三个端口（VECTOR with parameter）
assert ports[2].name == "data_in"
assert ports[2].port_type == PortType.VECTOR
assert ports[2].width == "DATA_WIDTH"
assert ports[2].range_string == "[DATA_WIDTH-1:0]"

# 验证第四个端口（VECTOR with constant）
assert ports[3].name == "data_out"
assert ports[3].port_type == PortType.VECTOR
assert ports[3].width == 8
assert ports[3].range_string == "[7:0]"
assert ports[3].net_type == "reg"

# 验证统计信息
summary = ast.get_module_info()["port_summary"]
assert summary["total"] == 4
assert summary["input"] == 3
assert summary["output"] == 1
```

### 9.2 异常验证示例

```python
# 测试重复设置模块名
builder = VerilogASTBuilder()
builder.set_module_name("module1")
try:
    builder.set_module_name("module2")
    assert False, "Should raise ValueError"
except ValueError:
    pass  # 正确

# 测试未设置模块名
builder = VerilogASTBuilder()
builder.add_port("clk", direction="input")
try:
    ast = builder.build()
    assert False, "Should raise VerilogASTError"
except VerilogASTError:
    pass  # 正确

# 测试重复 build
builder = VerilogASTBuilder()
builder.set_module_name("test")
ast1 = builder.build()
try:
    ast2 = builder.build()
    assert False, "Should raise VerilogASTError"
except VerilogASTError:
    pass  # 正确
```

---

## 11. 注意事项

### 11.1 测试范围限制

**测试重点：**
- ✅ 单bit端口（SIMPLE）
- ✅ 向量端口（VECTOR）
- ✅ 端口方向和网络类型
- ✅ 表达式计算
- ✅ Builder 构建流程

### 11.2 默认行为说明

1. **网络类型默认值**：未指定时默认为 `"wire"`
2. **重复名称处理**：覆盖内容，保持首次出现的顺序位置
3. **None 值更新**：update 时 None 值不会覆盖已有属性
4. **方向大小写**：统计时转为小写处理

### 11.3 已知限制

1. **表达式计算**：
   - 无法验证表达式的 Verilog 语法正确性
   - 系统函数不会真正计算，仅保留
   - 复杂表达式可能返回字符串形式

2. **类型判断**：
   - 仅根据 msb/lsb 存在性判断 SIMPLE 或 VECTOR
   - 不验证表达式的有效性

3. **Builder 使用**：
   - build() 后 Builder 不可重用（需 reset）
   - 不支持删除已添加的端口或参数



