# WiresManager 模块黑盒验证文档

## 1. 模块概述

`WiresManager` 是一个用于根据 Verilog 文件自动生成 wire 声明的管理模块。它能够解析 Verilog 文件中的模块端口信息，并根据规则管理器(`VCGRuleManager`)中定义的规则，自动生成符合规范的 wire 声明代码。

---

## 2. 编程接口 (API)

### 2.1 构造函数

```python
WiresManager(rule_manager: VCGRuleManager, macros=None)
```

**参数说明：**
- `rule_manager` (必需): `VCGRuleManager` 实例，用于提供 wire 生成规则
- `macros` (可选):宏定义字典，用于 Verilog 解析器

**返回值：** `WiresManager` 实例

---

### 2.2 主要功能接口

#### 2.2.1 generate_wires_def()

```python
generate_wires_def(
    file_path: str, 
    module_name: str,
    port_direction: Optional[str] = None, 
    pattern: str = 'greedy'
) -> str
```

**功能描述：** 根据 Verilog 文件生成 wire 声明代码

**参数说明：**
- `file_path` (必需): Verilog 文件的路径（字符串）
- `module_name` (必需): 目标模块名称
- `port_direction` (可选): 端口方向过滤器，可选值：
  - `None` (默认): 处理所有端口
  - `"input"`: 仅处理输入端口
  - `"output"`: 仅处理输出端口
  - `"inout"`: 仅处理双向端口
- `pattern` (可选): 生成模式，可选值：
  - `"greedy"` (默认): 贪婪模式，未匹配规则时使用默认行为
  - `"lazy"`: 懒惰模式，仅生成匹配规则的 wire

**返回值：** 生成的 wire 声明代码字符串（多行，以 `\n` 分隔）

**异常：**
- `VCGFileError`: 文件不存在或无法访问
- `VCGParseError`: Verilog 文件解析失败或生成过程出错
- `ValueError`: 参数值无效

---

### 2.3 配置接口

#### 2.3.1 set_base_spacing()

```python
set_base_spacing(spacing: int) -> None
```

**功能描述：** 设置 wire 声明的基础对齐间距

**参数说明：**
- `spacing` (必需): 对齐间距值（整数）

**返回值：** 无

---

#### 2.3.2 get_base_spacing()

```python
get_base_spacing() -> int
```

**功能描述：** 获取当前的基础对齐间距

**参数说明：** 无

**返回值：** 当前间距值（整数，默认为 15）

---

## 3. 功能点详细说明

### 3.1 功能点列表（完整覆盖）

#### **F1:文件解析功能**
- **F1.1**: 成功解析有效的 Verilog 文件
- **F1.2**: 处理文件不存在的情况（抛出 `VCGFileError`）
- **F1.3**: 处理解析错误的 Verilog 文件（抛出 `VCGParseError`）
- **F1.4**: 支持带宏定义的 Verilog 文件解析

#### **F2: 端口方向过滤功能**
- **F2.1**: `port_direction=None` - 处理所有端口
- **F2.2**: `port_direction="input"` - 仅处理输入端口
- **F2.3**: `port_direction="output"` - 仅处理输出端口
- **F2.4**: `port_direction="inout"` - 仅处理双向端口
- **F2.5**: 无效的`port_direction` 值（抛出 `ValueError`）

#### **F3: 生成模式功能**
- **F3.1**: `pattern="greedy"` - 贪婪模式- **F3.1.1**: 规则匹配成功，生成规则定义的 wire
  - **F3.1.2**: 规则匹配但返回空名称，不生成 wire
  - **F3.1.3**: 规则未匹配，使用端口名作为 wire 名称
- **F3.2**: `pattern="lazy"` - 懒惰模式
  - **F3.2.1**: 规则匹配成功，生成规则定义的 wire
  - **F3.2.2**: 规则匹配但返回空名称，不生成 wire
  - **F3.2.3**: 规则未匹配，跳过该端口（不生成 wire）
- **F3.3**: 无效的 `pattern` 值（抛出 `ValueError`）

#### **F4: 宽度格式化功能**
- **F4.1**: 无宽度信息（生成 `wire<name>;`）
- **F4.2**: 整数宽度- **F4.2.1**: 宽度 <= 1，不生成宽度声明
  - **F4.2.2**: 宽度 > 1，生成 `[width-1:0]` 格式
- **F4.3**: 字符串宽度（纯数字）
  - **F4.3.1**: 数值<= 1，不生成宽度声明
  - **F4.3.2**: 数值 > 1，生成 `[width-1:0]` 格式
- **F4.4**: 已格式化的宽度（`[x:y]` 格式），直接使用
- **F4.5**: 包含运算符的宽度表达式（`+`, `-`, `*`, `/`, `(`, `)`），生成 `[(expr)-1:0]` 格式
- **F4.6**: 参数化宽度（不含运算符），生成 `[param-1:0]` 格式
- **F4.7**: 多维数组宽度（包含 `][`），直接使用原格式

#### **F5: 表达式处理功能**
- **F5.1**: 无表达式，生成 `wire [width]<name>;`
- **F5.2**: 有表达式，生成 `wire [width] <name> = <expression>;`

#### **F6: 对齐格式化功能**
- **F6.1**: 前缀长度 < 基础间距，使用计算的空格数对齐
- **F6.2**: 前缀长度 >= 基础间距，使用单个空格
- **F6.3**: 自定义基础间距配置

---

## 4. 测试用例设计

### 4.1 基本功能测试

| 用例ID | 测试场景 | 输入参数 | 预期输出 | 对应功能点 |
|--------|---------|---------|---------|-----------|
| TC001 | 正常解析有效文件 | 有效的 Verilog 文件路径 | 返回 wire 声明字符串 | F1.1 |
| TC002 | 文件不存在 | 不存在的文件路径 | 抛出 `VCGFileError` | F1.2 |
| TC003 | 文件格式错误 | 无效的 Verilog 文件 | 抛出 `VCGParseError` | F1.3 |

### 4.2 端口方向过滤测试

| 用例ID | 测试场景 | port_direction | 预期行为 | 对应功能点 |
|--------|---------|----------------|---------|-----------|
| TC101 | 处理所有端口 | `None` | 处理输入、输出、双向所有端口 | F2.1 |
| TC102 | 仅输入端口 | `"input"` | 仅处理输入端口 | F2.2 |
| TC103 | 仅输出端口 | `"output"` | 仅处理输出端口 | F2.3 |
| TC104 | 仅双向端口 | `"inout"` | 仅处理双向端口 | F2.4 |
| TC105 | 无效方向 | `"invalid"` | 抛出 `ValueError` | F2.5 |
| TC106 | 大小写混合 | `"INPUT"` / `"Output"` | 正确识别并处理 | F2.2/F2.3 |

### 4.3 生成模式测试

| 用例ID | 测试场景 | pattern | 规则匹配情况 | 预期输出 | 对应功能点 |
|--------|---------|---------|------------|---------|-----------|
| TC201 | 贪婪模式-规则匹配 | `"greedy"` | 匹配且返回有效名称 | 生成规则定义的 wire | F3.1.1 |
| TC202 | 贪婪模式-规则匹配但空名称 | `"greedy"` | 匹配但返回空字符串 | 不生成该wire | F3.1.2 |
| TC203 |贪婪模式-规则未匹配 | `"greedy"` | 未匹配任何规则 | 生成以端口名为名的 wire | F3.1.3 |
| TC204 | 懒惰模式-规则匹配 | `"lazy"` | 匹配且返回有效名称 | 生成规则定义的 wire | F3.2.1 |
| TC205 | 懒惰模式-规则匹配但空名称 | `"lazy"` | 匹配但返回空字符串 | 不生成该 wire | F3.2.2 |
| TC206 | 懒惰模式-规则未匹配 | `"lazy"` | 未匹配任何规则 | 跳过该端口，不生成 | F3.2.3 |
| TC207 | 无效模式 | `"invalid"` | - | 抛出 `ValueError` | F3.3|

### 4.4 宽度格式化测试

| 用例ID | 测试场景 | 输入宽度 | 预期宽度声明 | 对应功能点 |
|--------|---------|---------|------------|-----------|
| TC301 | 无宽度信息 | `None` 或空字符串 | 无宽度声明 | F4.1 |
| TC302 | 单比特(整数1) | `1` | 无宽度声明 | F4.2.1 |
| TC303 | 单比特(整数0) | `0` | 无宽度声明 | F4.2.1 |
| TC304 | 多比特整数 | `8` | `[7:0]` | F4.2.2 |
| TC305 | 纯数字字符串(单比特) | `"1"` | 无宽度声明 | F4.3.1 |
| TC306 | 纯数字字符串(多比特) | `"32"` | `[31:0]` | F4.3.2 |
| TC307 | 已格式化宽度 | `"[15:0]"` | `[15:0]` | F4.4 |
| TC308 | 加法表达式 | `"N+1"` | `[(N+1)-1:0]` | F4.5 |
| TC309 | 减法表达式 | `"N-1"` | `[(N-1)-1:0]` | F4.5 |
| TC310 | 乘法表达式 | `"N*2"` | `[(N*2)-1:0]` | F4.5 |
| TC311 | 括号表达式 | `"(N+M)/2"` | `[((N+M)/2)-1:0]` | F4.5 |
| TC312 | 参数化宽度 | `"WIDTH"` | `[WIDTH-1:0]` | F4.6 |
| TC313 | 多维数组 | `"[7:0][3:0]"` | `[7:0][3:0]` | F4.7 |

### 4.5 表达式处理测试

| 用例ID | 测试场景 | wire名称 | 宽度 | 表达式 | 预期输出 | 对应功能点 |
|--------|---------|---------|------|--------|---------|-----------|
| TC401 | 无表达式 | `data` | `8` | `None` | `wire [7:0]data;` | F5.1 |
| TC402 | 有表达式 | `valid` | `None` | `1'b0` | `wire            valid = 1'b0;` | F5.2 |
| TC403 | 有表达式+宽度 | `counter` | `16` | `16'd0` | `wire [15:0]    counter = 16'd0;` | F5.2 |

### 4.6 对齐格式化测试

| 用例ID | 测试场景 | 间距设置 | 预期行为 | 对应功能点 |
|--------|---------|---------|---------|-----------|
| TC501 | 默认间距(15) | 默认 | `wire [7:0]     name;` (补齐到15) | F6.1 |
| TC502 | 前缀过长 | 宽度声明很长 | 使用单个空格 | F6.2 |
| TC503 | 自定义间距(20) | `set_base_spacing(20)` | 补齐到20个字符 | F6.3 |
| TC504 | 获取间距 | `get_base_spacing()` | 返回当前间距值 | F6.3 |

---

## 5. 边界条件与特殊场景

### 5.1 边界条件

| 边界条件ID | 场景描述 | 预期行为 |
|-----------|---------|---------|
| BC001 | 文件路径为空字符串 | 抛出异常 |
| BC002 | module_name 为空字符串 | 正常处理（可能找不到模块） |
| BC003 | 端口列表为空 | 返回空字符串 |
| BC004 | 宽度为负数 | 按照表达式处理 |
| BC005 | wire 名称包含特殊字符 | 保留原样输出 |
| BC006 | 间距设置为0或负数 | 按照实际值使用 |

### 5.2 特殊场景

| 场景ID | 场景描述 | 输入示例 | 预期输出 |
|--------|---------|---------|---------|
| SS001 | 端口名包含下划线 | `data_valid` | `wiredata_valid;` |
| SS002 | 端口名包含数字 | `port0` | `wire            port0;` |
| SS003 | 多维数组端口 | 宽度 `[7:0][3:0]` | `wire [7:0][3:0] name;` |
| SS004 | 参数化宽度 | 宽度 `DATA_WIDTH` | `wire [DATA_WIDTH-1:0] name;` |
| SS005 | 复杂表达式宽度 | 宽度 `(A+B)*C-1` | `wire [((A+B)*C-1)-1:0] name;` |
| SS006 | 所有端口被规则跳过(lazy模式) | 无匹配规则，lazy模式 | 返回空字符串 |

---

## 6. 验证策略建议

### 6.1 黑盒测试方法

1. **等价类划分**
   - 按参数类型划分：有效/无效文件路径、有效/无效端口方向、有效/无效模式
   - 按规则匹配结果划分：匹配/不匹配、返回有效名称/空名称

2. **边界值分析**
   - 宽度：0, 1, 2, 最大整数
   - 间距：0, 1, 默认值, 极大值
   - 端口数量：0, 1, 大量端口

3. **决策表测试**
   - 组合 pattern 和规则匹配结果的所有情况

4. **状态转换测试**
   - 多次调用 `set_base_spacing()` 后验证状态保持

### 6.2 测试数据准备

**需要准备的 Verilog 测试文件：**
1. 标准模块文件（包含 input/output/inout 端口）
2. 仅输入端口的模块
3. 仅输出端口的模块
4. 包含参数化宽度的模块
5. 包含多维数组端口的模块
6. 语法错误的 Verilog 文件
7. 空文件

**需要准备的规则配置：**
1. 匹配所有端口的规则
2. 匹配特定前缀的规则
3. 返回空名称的规则
4. 带表达式的规则
5. 无匹配规则的配置

### 6.3 验证检查点

✅ **每个测试用例应验证：**
1. 返回值格式是否正确（字符串，换行符分隔）
2. Wire 声明语法是否符合 Verilog 规范
3. 宽度格式是否正确
4. 对齐格式是否一致
5. 异常处理是否符合预期
6. 日志输出是否正常（如需验证）

---

## 7. 测试执行示例

### 7.1 基本使用示例

```python
# 初始化
rule_manager = VCGRuleManager()  # 假设已配置规则
wires_manager = WiresManager(rule_manager)

# 测试用例1: 生成所有端口的wire声明（greedy模式）
result = wires_manager.generate_wires_def(
    file_path="test_module.v",
    module_name="test_module",
    port_direction=None,
    pattern="greedy"
)
print(result)

# 测试用例2: 仅生成输入端口（lazy模式）
result = wires_manager.generate_wires_def(
    file_path="test_module.v",
    module_name="test_module",
    port_direction="input",
    pattern="lazy"
)
print(result)

# 测试用例3: 自定义间距
wires_manager.set_base_spacing(20)
result = wires_manager.generate_wires_def(
    file_path="test_module.v",
    module_name="test_module"
)
print(result)
```

### 7.2 异常测试示例

```python
# 测试文件不存在
try:
    result = wires_manager.generate_wires_def(
        file_path="non_existent.v",
        module_name="test"
    )
except VCGFileError as e:
    print(f"捕获到预期异常: {e}")

# 测试无效参数
try:
    result = wires_manager.generate_wires_def(
        file_path="test.v",
        module_name="test",
        pattern="invalid"
    )
except ValueError as e:
    print(f"捕获到预期异常: {e}")
```

---

## 8. 输出格式说明

### 8.1 标准输出格式

```verilog
wire [7:0]     data_in;
wire           valid;
wire [15:0]    counter = 16'd0;
wire [DATA_WIDTH-1:0] param_signal;
```

### 8.2 格式规则

1. **关键字**:统一使用 `wire`
2. **宽度声明**: 紧跟在 `wire` 后面，格式为 `[msb:lsb]`
3. **对齐**: wire 名称按基础间距对齐（默认15个字符）
4. **表达式**: 如有赋值，格式为 `= expression`
5. **结束符**: 每行以分号 `;` 结束
6. **换行**: 多个 wire 声明之间用 `\n` 分隔

---

## 9. 依赖项说明

该模块依赖以下外部组件，测试时需要确保这些依赖可用：

- `VCGRuleManager`: 规则管理器，提供 `resolve_wire_generation()` 方法
- `VerilogParser`: Verilog 解析器，提供 `parse_file()` 方法
- `PortInfo`: 端口信息数据结构
- 异常类: `VCGRuntimeError`, `VCGSyntaxError`, `VCGFileError`, `VCGParseError`

---

## 10. 验证完整性检查清单

- [ ] 所有 API 接口已测试
- [ ] 所有参数组合已覆盖
- [ ] 所有分支条件已验证
- [ ] 所有异常场景已测试
- [ ] 边界值测试已完成
- [ ] 特殊字符处理已验证
- [ ] 性能测试已执行（如需要）
- [ ] 并发安全测试已完成（如需要）
