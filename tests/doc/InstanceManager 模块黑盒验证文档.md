# InstanceManager 模块黑盒验证文档

## 1. 模块概述

**模块名称**: `InstanceManager`

**功能描述**: 该模块用于解析Verilog文件并自动生成模块实例化代码。它能够读取Verilog模块定义，提取端口和参数信息，并根据规则管理器的配置生成格式化的实例化代码。

**依赖项**:
- `VerilogParser`: Verilog文件解析器
- `VCGRuleManager`: 规则管理器，用于解析信号连接和参数值
- 相关异常类和日志模块

---

## 2. 编程接口 (API)

### 2.1 构造函数

```python
__init__(rule_manager: VCGRuleManager, macros=None)
```

**参数**:
- `rule_manager` (VCGRuleManager, 必需): 规则管理器对象，用于解析端口连接和参数值
- `macros` (可选): 宏定义字典，传递给Verilog解析器

**返回**: InstanceManager对象实例

**功能**: 初始化InstanceManager，设置规则管理器、宏定义、日志记录器和默认对齐宽度(18)

---

### 2.2 generate_instance

```python
generate_instance(file_path: str, module_name: str, instance_name: str) -> str
```

**参数**:
- `file_path` (str, 必需): Verilog源文件的路径
- `module_name` (str, 必需): 要实例化的模块名称
- `instance_name` (str, 必需): 实例的名称

**返回**: 
- `str`: 格式化的Verilog实例化代码字符串

**异常**:
- `VCGFileError`: 当Verilog文件不存在时抛出
- `VCGParseError`: 当文件解析失败或生成实例时发生错误时抛出

**功能**: 解析指定的Verilog文件，提取模块的端口和参数信息，生成格式化的实例化代码

---

### 2.3 set_alignment

```python
set_alignment(align: int) -> None
```

**参数**:
- `align` (int, 必需): 对齐宽度值

**返回**: 无

**功能**: 设置实例化代码中端口名和信号名的对齐宽度

---

### 2.4 get_alignment

```python
get_alignment() -> int
```

**参数**: 无

**返回**: 
- `int`: 当前的对齐宽度值

**功能**: 获取当前设置的对齐宽度

---

## 3. 功能点分解

### 3.1 文件解析功能

#### 功能点 3.1.1: 正常文件解析
- **输入**: 存在且格式正确的Verilog文件路径
- **预期输出**: 成功返回AST对象
- **验证方法**: 提供标准Verilog模块文件，验证无异常抛出

#### 功能点 3.1.2: 文件不存在处理
- **输入**: 不存在的文件路径
- **预期输出**: 抛出 `VCGFileError` 异常，错误消息包含文件路径
- **验证方法**: 提供不存在的路径，捕获并验证异常类型和消息

#### 功能点 3.1.3: 文件格式错误处理
- **输入**: 格式错误的Verilog文件
- **预期输出**: 抛出 `VCGParseError` 异常
- **验证方法**: 提供语法错误的Verilog文件，验证异常抛出

---

### 3.2 端口连接生成功能

#### 功能点 3.2.1: 基本端口连接
- **输入**: 包含标准input/output端口的模块
- **预期输出**: 生成所有端口的连接语句
- **验证方法**: 检查输出中每个端口都有对应的 `.port_name(signal_name)` 格式

#### 功能点 3.2.2: 空连接处理
- **输入**: rule_manager返回空字符串的端口
- **预期输出**: 端口连接为 `.port_name()`
- **验证方法**: 配置rule_manager返回空字符串，验证输出格式

#### 功能点 3.2.3: 多类型端口处理
- **输入**: 包含input、output、inout端口的模块
- **预期输出**: 所有类型端口都正确连接并生成对应注释
- **验证方法**: 验证不同direction的端口注释正确性

---

### 3.3 参数连接生成功能

#### 功能点 3.3.1: 有参数模块实例化
- **输入**: 包含parameter定义的模块，rule_manager返回参数值
- **预期输出**: 生成 `module_name #(...)` 格式的实例化代码
- **验证方法**: 验证输出包含参数section，格式正确

#### 功能点 3.3.2: 无参数模块实例化
- **输入**: 不包含parameter的模块
- **预期输出**: 生成 `module_name instance_name (...)` 格式
- **验证方法**: 验证输出不包含 `#(` 字符

#### 功能点 3.3.3: 部分参数覆盖
- **输入**: 模块有多个参数，rule_manager只返回部分参数值
- **预期输出**: 只生成有值的参数连接
- **验证方法**: 验证输出中只包含返回值不为None的参数

---

### 3.4 代码格式化功能

#### 功能点 3.4.1: 对齐宽度设置
- **输入**: 调用 `set_alignment(n)` 设置不同对齐值
- **预期输出**: 端口名和参数名按指定宽度左对齐
- **验证方法**: 
  - 测试align=10, 20, 30等不同值
  - 验证输出中端口名和左括号间的空格数

#### 功能点 3.4.2: 逗号分隔符处理
- **输入**: 多个端口/参数
- **预期输出**: 
  - 除最后一项外，每行末尾有逗号
  - 最后一项末尾无逗号
- **验证方法**: 检查输出中逗号分布

#### 功能点 3.4.3: 缩进处理
- **输入**: 任意模块
- **预期输出**: 参数和端口行缩进4个空格
- **验证方法**: 验证每行开头的空格数

---

### 3.5 端口注释生成功能

#### 功能点 3.5.1: 基本方向注释
- **输入**: 包含direction属性的端口
- **预期输出**: 注释以 `// direction` 开头
- **验证方法**: 验证input端口注释包含"// input"

#### 功能点 3.5.2: 无方向端口
- **输入**: direction为空的端口
- **预期输出**: 不生成注释
- **验证方法**: 验证输出行中无 `//` 字符

#### 功能点 3.5.3: net_type注释
- **输入**: net_type为非wire类型（如reg）
- **预期输出**: 注释包含net_type
- **测试用例**:
  - net_type='reg': 注释应包含"reg"
  - net_type='wire': 注释不应包含"wire"
  - net_type=None: 注释不包含net_type

#### 功能点 3.5.4: range_string注释
- **输入**: 包含位宽信息的端口
- **预期输出**: 注释包含range_string（如[7:0]）
- **验证方法**: 验证多位端口注释包含位宽信息

#### 功能点 3.5.5: INTERFACE类型端口
- **输入**: port_type为INTERFACE的端口
- **预期输出**: 注释包含 `<interface_type>`
- **验证方法**: 验证输出包含尖括号包裹的接口类型

#### 功能点 3.5.6: 数组端口注释
- **输入**: port_type为ARRAY_2D或ARRAY_3D
- **预期输出**: 注释包含 `[ARRAY]` 标记
- **测试用例**:
  - ARRAY_2D: 包含"[ARRAY]"
  - ARRAY_3D: 包含"[ARRAY]"
  - 普通端口: 不包含"[ARRAY]"

#### 功能点 3.5.7: 组合注释
- **输入**: 端口同时具有direction、net_type、range_string等多个属性
- **预期输出**: 注释按顺序包含所有属性，用空格分隔
- **验证方法**: 验证复杂端口注释格式为 `// direction net_type range_string [special_marker]`

---

### 3.6 日志功能

#### 功能点 3.6.1: 信息日志
- **触发条件**: 调用主要API方法
- **预期行为**: 记录操作开始和成功完成的信息
- **验证方法**: 检查日志输出包含"Generating instance"和"generated successfully"

#### 功能点 3.6.2: 调试日志
- **触发条件**: 启用debug模式
- **预期行为**: 记录端口数量、参数数量、连接详情等
- **验证方法**: 检查日志中的详细信息

#### 功能点 3.6.3: 错误日志
- **触发条件**: 发生异常
- **预期行为**: 记录错误信息
- **验证方法**: 触发异常时验证错误日志输出

---

## 4. 边界条件测试

### 4.1 输入边界

| 边界条件 | 测试值 | 预期行为 |
|---------|--------|---------|
| 空模块（无端口无参数） | 空模块定义 | 生成只有模块名和实例名的实例化代码 |
| 超长模块名 | 100+字符模块名 | 正常处理，不截断 |
| 超长端口名 | 100+字符端口名 | 正常处理，对齐可能超出预设宽度 |
| 端口数量=0 | 无端口模块 | 生成 `module_name instance_name ();` |
| 端口数量=1 | 单端口模块 | 最后一个端口无逗号 |
| 端口数量>100 | 大量端口 | 所有端口都正确连接 |
| 参数数量=0 | 无参数模块 | 不生成参数section |
| 参数数量>50 | 大量参数 | 所有参数都正确连接 |

### 4.2 对齐宽度边界

| 对齐值 | 预期行为 |
|--------|---------|
| align = 1 | 最小对齐，正常工作 |
| align = 0 | 边界值，验证是否崩溃 |
| align = -1 | 负值，验证错误处理 |
| align = 100 | 大值对齐，正常工作但格式稀疏 |

### 4.3 字符串边界

| 场景 | 测试数据 | 预期行为 |
|-----|---------|---------|
| 特殊字符端口名 | `port_$name`, `port[0]` | 正确处理或合理报错 |
| 空字符串 | file_path='', module_name='' | 抛出相应异常 |
| 路径包含空格 | `'/path/to file.v'` | 正常解析 |
| Unicode字符 | 中文路径、模块名 | 根据系统支持情况处理 |

### 4.4 异常分支覆盖

| 异常类型 | 触发条件 | 必须验证的内容 |
|---------|---------|---------------|
| VCGFileError | 文件不存在 | 异常类型、错误消息包含文件路径 |
| VCGParseError | 解析失败 | 异常类型、错误消息说明原因 |
| VCGParseError | AST为None | 捕获并转换异常 |
| 其他Exception | 未预期错误 | 捕获并转换为VCGParseError |

---

## 5. 测试用例矩阵

### 5.1 基本功能测试用例

| 用例ID | 测试场景 | 输入 | 预期输出 |
|--------|---------|------|---------|
| TC-001 | 最简单模块 | 1个input，1个output，无参数 | 正确的2行端口连接 |
| TC-002 | 带参数模块 | 2个参数，3个端口 | 参数section + 端口section |
| TC-003 | 复杂端口类型 | 包含INTERFACE、ARRAY_2D端口 | 正确的特殊类型注释 |
| TC-004 | 所有端口方向 | input、output、inout各1个 | 注释正确标识方向 |
| TC-005 | 不同位宽 | [0:0], [7:0], [31:0]端口 | 注释包含完整位宽 |

### 5.2 边界测试用例

| 用例ID | 测试场景 | 输入 | 预期输出 |
|--------|---------|------|---------|
| TC-101 | 文件不存在 | 无效路径 | VCGFileError异常 |
| TC-102 | 空模块 | 无端口无参数 | 最小化实例代码 |
| TC-103 | 大型模块 | 100+端口 | 所有端口正确连接 |
| TC-104 | 全部参数为None | 模块有参数但rule_manager都返回None | 无参数section |

### 5.3 格式测试用例

| 用例ID | 测试场景 | 操作 | 验证点 |
|--------|---------|------|--------|
| TC-201 | 默认对齐 | 不设置alignment | 使用18的默认值 |
| TC-202 | 自定义对齐 | set_alignment(25) | 端口名左对齐到25位 |
| TC-203 | 逗号正确性 | 3个端口 | 前2个有逗号，最后1个无 |
| TC-204 | 缩进正确性 | 任意模块 | 每个端口/参数行4空格缩进 |

---

## 6. 验证策略建议

### 6.1 功能验证
1. **正向测试**: 覆盖所有功能点的正常流程
2. **负向测试**: 覆盖所有异常分支
3. **组合测试**: 测试功能组合场景（如：有参数+多端口+特殊类型）

### 6.2 边界验证
1. 针对每个边界条件创建专门测试用例
2. 使用等价类划分和边界值分析方法
3. 特别关注空值、最小值、最大值场景

### 6.3 回归验证
1. 构建标准测试套件，包含典型Verilog模块
2. 建立输出基准（golden reference）
3. 每次修改后对比输出差异

### 6.4 验证工具建议
```python
# 示例：验证框架伪代码
def verify_instance_generation(test_case):
    # 1. 准备测试数据
    im = InstanceManager(mock_rule_manager, mock_macros)
    
    # 2. 执行被测方法
    result = im.generate_instance(test_case.file, test_case.module, test_case.instance)
    
    # 3. 验证输出
    assert_contains(result, expected_module_name)
    assert_contains(result, expected_instance_name)
    assert_port_count(result, expected_count)
    assert_format_correct(result)
    
    # 4. 验证可选功能
    if test_case.has_parameters:
        assert_contains(result, "#(")
    
    return True
```

---

## 7. 输出格式规范

### 7.1 无参数模块输出格式
```verilog
module_name instance_name (
    .port1            (signal1),              // input [7:0]
    .port2            (signal2)               // output
);
```

### 7.2 有参数模块输出格式
```verilog
module_name #(
    .PARAM1           (value1),
    .PARAM2           (value2)
) instance_name (
    .port1            (signal1),              // input [7:0]
    .port2            (signal2)               // output
);
```

### 7.3 特殊端口注释格式
- 基本端口: `// direction [range]`
- 非wire类型: `// direction net_type [range]`
- 接口端口: `// direction <interface_type>`
- 数组端口: `// direction [range] [ARRAY]`

---

## 8. Mock对象要求

为完成黑盒验证，需要准备以下Mock对象：

### 8.1 Mock VCGRuleManager
```python
# 需要实现的接口：
- resolve_signal_connection(port: PortInfo) -> str
- resolve_param_connection(param_name: str) -> Optional[str]
```

### 8.2 Mock VerilogParser
```python
# 需要实现的接口：
- parse_file(file_path: str) -> AST_Object
# AST_Object需要实现：
- get_port_info() -> List[PortInfo]
- get_parameter_info() -> List[ParameterInfo]
```

---

## 9. 验证完成标准

- ✅ 所有功能点测试用例通过
- ✅ 所有边界条件测试用例通过  
- ✅ 所有异常分支被触发并正确处理
- ✅ 代码覆盖率达到100%（通过黑盒测试可推断）
- ✅ 输出格式符合Verilog语法规范
- ✅ 无未处理的异常泄漏
- ✅ 日志输出完整且信息充分

---

## 10. 注意事项

1. **文件依赖**: 需要准备各种类型的Verilog测试文件
2. **规则管理器**: Mock对象行为需要覆盖空字符串、None、正常值等情况
3. **并发安全**: 文档未提及线程安全，建议测试多实例并发场景
4. **性能测试**: 建议测试大文件（10000+行）的解析性能
5. **内存泄漏**: 长时间运行测试，监控内存使用