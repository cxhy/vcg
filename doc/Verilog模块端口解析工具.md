# Verilog模块端口解析工具技术文档

## 一、项目概述

本工具是一个基于PLY（Python Lex-Yacc）实现的Verilog模块端口解析器，能够自动提取Verilog代码中的模块信息，包括模块名、参数列表、端口声明等。目前支持Verilog-1995和Verilog-2001标准语法，未来将扩展SystemVerilog支持。

### 核心功能
- ✅ 解析Verilog模块声明
- ✅ 提取模块名、参数(parameter/localparam)
- ✅ 提取端口信息（方向、类型、位宽、数组维度）
- ✅ 支持条件编译预处理（`` `ifdef``, `` `ifndef``, `` `else`` 等）
- ✅ 自动计算端口位宽（支持参数化表达式）
- ✅ 兼容Verilog-1995和Verilog-2001两种端口声明风格

---

## 二、架构设计

### 2.1 整体流程

```
Verilog源代码
    ↓
[1] VerilogPreprocess (预处理)
    - 条件编译处理
    - 提取模块端口区域
    ↓
[2] VerilogLexer (词法分析)
    - Token识别
    ↓
[3] VerilogParser (语法分析)
    - 使用VerilogASTBuilder构建AST
    ↓
[4] VerilogAST (结果输出)
    - PortInfo: 端口信息对象
    - ParameterInfo: 参数信息对象
```

### 2.2 核心模块说明

| 模块 | 职责 | 关键类/方法 |
|------|------|------------|
| **VerilogPreprocess** | 预处理器 | `preprocess_file()`, `preprocess_string()` |
| **VerilogLexer** | 词法分析器 | `build()`, `token()` |
| **VerilogAst** | 数据结构 | `VerilogASTBuilder`, `PortInfo`, `ParameterInfo` |
| **VerilogParser** | 语法解析器 | `parse_file()`, `parse_string()`, `get_module_info()` |

---

## 三、快速入门

### 3.1 基本用法示例

#### **方式1：解析文件**

```python
from VerilogParser import VerilogParser

# 1. 创建解析器实例
parser = VerilogParser()

# 2. 解析Verilog文件
ast = parser.parse_file("your_module.v")

# 3. 获取模块信息
if ast:
    print(f"模块名: {ast.module_name}")
    
    # 获取所有端口
    ports = ast.get_port_info()
    for port in ports:
        print(f"  {port.direction} {port.net_type} [{port.range_string}] {port.name}")
    
    # 获取所有参数
    params = ast.get_parameter_info()
    for param in params:
        print(f"  {param.param_type} {param.name} = {param.default_value}")
```

#### **方式2：解析字符串**

```python
verilog_code = """
module adder #(
    parameter WIDTH = 8
)(
    input  wire [WIDTH-1:0] a,
    input  wire [WIDTH-1:0] b,
    output wire [WIDTH:0]   sum
);
endmodule
"""

parser = VerilogParser()
ast = parser.parse_string(verilog_code)
```

### 3.2 带宏定义的解析

```python
# 定义预处理宏
macros = {
    'USE_REG': '1',
    'DATA_WIDTH': '32'
}

parser = VerilogParser(macros=macros, debug=False)
ast = parser.parse_file("module_with_ifdef.v")
```

---

## 四、下游调用指南

### 4.1 获取端口信息详解

#### **方法1：使用 `get_port_info()` 获取端口列表**

```python
ast = parser.parse_file("your_module.v")

# 获取所有端口
ports = ast.get_port_info()

for port in ports:
    # 基本信息
    print(f"端口名: {port.name}")
    print(f"方向: {port.direction}")      # 'input', 'output', 'inout'
    print(f"类型: {port.net_type}")       # 'wire', 'reg', 'logic'
    
    # 位宽信息
    print(f"范围字符串: {port.range_string}")  # 例: '[7:0]'
    print(f"位宽: {port.width}")              # 自动计算，例: 8
    print(f"端口类型: {port.port_type}")      # SIMPLE/VECTOR/ARRAY_2D/ARRAY_3D
    
    # 原始表达式（用于参数化设计）
    print(f"MSB表达式: {port.msb_expr}")
    print(f"LSB表达式: {port.lsb_expr}")
```

#### **方法2：使用 `get_module_info()` 获取完整字典**

```python
module_info = parser.get_module_info()

# 返回字典结构
{
    "name": "module_name",
    "parameters": [
        {
            "name": "WIDTH",
            "type": "parameter",
            "default_value": "8"
        }
    ],
    "ports": [
        {
            "name": "clk",
            "direction": "input",
            "net_type": "wire",
            "range": "",
            "width": 1,
            "type": "simple"
        },
        {
            "name": "data",
            "direction": "input",
            "net_type": "wire",
            "range": "[WIDTH-1:0]",
            "width": "WIDTH",  # 保留参数化表达式
            "type": "vector"
        }
    ]
}
```

### 4.2 端口分类筛选

```python
ports = ast.get_port_info()

# 按方向分类
input_ports = [p for p in ports if p.direction == 'input']
output_ports = [p for p in ports if p.direction == 'output']
inout_ports = [p for p in ports if p.direction == 'inout']

# 按类型分类
simple_ports = [p for p in ports if p.port_type == PortType.SIMPLE]
vector_ports = [p for p in ports if p.port_type == PortType.VECTOR]

# 按net_type分类
reg_ports = [p for p in ports if p.net_type == 'reg']
wire_ports = [p for p in ports if p.net_type == 'wire']
```

### 4.3 参数处理

```python
params = ast.get_parameter_info()

for param in params:
    print(f"名称: {param.name}")
    print(f"类型: {param.param_type}")        # 'parameter' 或 'localparam'
    print(f"默认值: {param.default_value}")
```

### 4.4 位宽计算能力

工具内置 `ExpressionCalculator`，能够自动计算位宽表达式：

```python
# 示例1：简单表达式
# [7:0] → width = 8

# 示例2：参数化表达式
# [WIDTH-1:0] → width = "WIDTH"（保留符号表达式）

# 示例3：复杂表达式
# [$clog2(DEPTH)-1:0] → width = "$clog2(DEPTH)"（保留函数调用）

port = ports[0]
width = port.width  # 自动计算或返回表达式字符串
```

---

## 五、高级特性

### 5.1 条件编译支持

```python
# 示例Verilog代码
"""
module test;
`ifdef USE_REG
    output reg [7:0] data;
`else
    output wire [7:0] data;
`endif
endmodule
"""

# 解析时传入宏定义
parser = VerilogParser(macros={'USE_REG': '1'})
ast = parser.parse_string(verilog_code)
# 结果：data端口的net_type为'reg'
```

### 5.2 兼容两种语法风格

#### **Verilog-2001风格**（推荐）
```verilog
module counter (
    input  wire        clk,
    input  wire        rst,
    output reg  [7:0]  count
);
```

#### **Verilog-1995风格**
```verilog
module counter (clk, rst, count);
    input  clk;
    input  rst;
    output [7:0] count;
    reg    [7:0] count;
```

**两种风格均能正确解析！**

### 5.3 错误处理

```python
parser = VerilogParser(debug=False)
ast = parser.parse_file("module.v")

if ast:
    print("解析成功")
else:
    print("解析失败，查看日志")

# 检查解析错误
if parser.parse_errors:
    for error in parser.parse_errors:
        print(f"错误: {error}")
```

---

## 六、典型应用场景

### 6.1 自动生成模块实例化代码

```python
ast = parser.parse_file("dut.v")
ports = ast.get_port_info()

# 生成实例化模板
print(f"{ast.module_name} u_{ast.module_name} (")
for i, port in enumerate(ports):
    comma = "," if i < len(ports)-1 else ""
    print(f"    .{port.name}({port.name}){comma}")
print(");")
```

### 6.2 生成测试平台信号声明

```python
for port in ast.get_port_info():
    if port.direction == 'input':
        print(f"reg  {port.range_string} {port.name};")
    elif port.direction == 'output':
        print(f"wire {port.range_string} {port.name};")
```

### 6.3 接口验证

```python
def check_interface_compliance(ast, expected_ports):
    """检查模块是否符合接口规范"""
    actual_ports = {p.name: p for p in ast.get_port_info()}
    
    for exp_name, exp_direction in expected_ports.items():
        if exp_name not in actual_ports:
            print(f"缺少端口: {exp_name}")
        elif actual_ports[exp_name].direction != exp_direction:
            print(f"端口方向错误: {exp_name}")
```

---

## 七、注意事项与限制

### 7.1 当前限制
- ⚠️ **不支持SystemVerilog**特性（interface、struct等）
- ⚠️ **不解析模块内部逻辑**（always块、assign语句等仅做语法识别）
- ⚠️ **复杂表达式**可能无法完全化简（保留原始字符串）

### 7.2 最佳实践
1. **文件编码**：建议使用UTF-8编码
2. **宏定义传递**：如果代码中使用`` `ifdef``，务必传入对应的macros字典
3. **错误检查**：始终检查`parse_errors`列表
4. **日志调试**：设置`debug=True`可输出详细解析过程

### 7.3 性能建议
- 单次解析器实例可重复使用（内部会reset）
- 大批量文件建议复用VerilogParser实例
- 预处理器可以单独使用以验证宏展开结果

---

## 八、完整示例代码

```python
#!/usr/bin/env python3
from VerilogParser import VerilogParser
from VerilogAst import PortType

def analyze_module(filepath):
    """完整的模块分析示例"""
    # 1. 创建解析器
    parser = VerilogParser(macros={'SIM_MODE': '1'}, debug=False)
    
    # 2. 解析文件
    ast = parser.parse_file(filepath)
    
    if not ast:
        print(f"❌ 解析失败: {filepath}")
        return
    
    # 3. 输出模块摘要
    print(f"\n{'='*60}")
    print(f"模块名称: {ast.module_name}")
    print(f"{'='*60}\n")
    
    # 4. 输出参数信息
    params = ast.get_parameter_info()
    if params:
        print("📌 参数列表:")
        for param in params:
            print(f"  {param.param_type:12} {param.name:20} = {param.default_value}")
        print()
    
    # 5. 输出端口信息
    ports = ast.get_port_info()
    print(f"📌 端口列表 (共{len(ports)}个):")
    print(f"  {'方向':<8} {'类型':<8} {'位宽':<12} {'范围':<20} {'名称'}")
    print(f"  {'-'*70}")
    
    for port in ports:
        width_str = str(port.width) if isinstance(port.width, int) else f"{port.width}"
        print(f"  {port.direction:<8} {port.net_type:<8} "
              f"{width_str:<12} {port.range_string:<20} {port.name}")
    
    # 6. 统计信息
    summary = ast.get_module_info()['port_summary']
    print(f"\n📊 统计: INPUT={summary['input']}, "
          f"OUTPUT={summary['output']}, INOUT={summary['inout']}")
    
    # 7. 检查错误
    if parser.parse_errors:
        print(f"\n⚠️  解析警告 ({len(parser.parse_errors)}个):")
        for err in parser.parse_errors:
            print(f"  - {err}")

if __name__ == "__main__":
    analyze_module("example_module.v")
```

---

## 九、API参考速查表

### VerilogParser类

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `__init__` | `macros`, `debug` | - | 初始化解析器 |
| `parse_file` | `filepath: str` | `VerilogAST` | 解析Verilog文件 |
| `parse_string` | `verilog_code: str` | `VerilogAST` | 解析代码字符串 |
| `get_module_info` | - | `Dict` | 获取完整模块信息字典 |

### VerilogAST类

| 方法/属性 | 返回值 | 说明 |
|----------|--------|------|
| `module_name` | `str` | 模块名称 |
| `get_port_info()` | `List[PortInfo]` | 获取所有端口 |
| `get_parameter_info()` | `List[ParameterInfo]` | 获取所有参数 |
| `get_module_info()` | `Dict` | 获取完整信息 |

### PortInfo类关键属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 端口名 |
| `direction` | `str` | 'input'/'output'/'inout' |
| `net_type` | `str` | 'wire'/'reg'/'logic' |
| `width` | `int/str` | 自动计算的位宽 |
| `range_string` | `str` | 范围字符串如'[7:0]' |
| `port_type` | `PortType` | 端口类型枚举 |
| `msb_expr` | `str` | MSB原始表达式 |
| `lsb_expr` | `str` | LSB原始表达式 |

---

## 十、未来扩展计划

- 🔜 SystemVerilog interface支持
- 🔜 struct/union端口类型
- 🔜 modport解析
- 🔜 更完善的表达式计算引擎
