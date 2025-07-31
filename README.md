# VCG (Verilog Code Generator) 使用手册

##  概述

VCG是一个强大的Verilog代码生成工具，它允许工程师在Verilog文件中嵌入Python代码块，通过编程方式自动生成复杂的Verilog代码结构。VCG特别适用于需要大量重复实例化、复杂连接规则或动态参数配置的硬件设计场景。

##  快速开始

### 安装与基本用法

```bash
# 基本用法
vcg.py your_design.v

# 启用调试模式
vcg.py your_design.v --log-level DEBUG

# 使用宏定义
vcg.py your_design.v --macros "WIDTH=32,DEPTH=1024"
```

### 宏定义格式

VCG支持两种宏定义格式：

```bash
# 简单宏列表（定义为空值）
--macros "MACRO1,MACRO2,MACRO3"

# 键值对宏定义
--macros "WIDTH=32,DEPTH=1024,ENABLE=1"
```

 > **注意**：不能在同一命令中混合使用两种格式

## 日志系统
### 命令行日志参数
```python
# 设置日志级别
--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}  # 默认: WARNING

# 日志文件输出
--log-file FILENAME

# 静默模式
--quiet  # 控制台只显示错误信息
```
### 日志级别说明
| 级别 | 描述 | 控制台格式 | 使用场景 |
|------|------|------------|----------|
| `DEBUG` | 最详细的调试信息 | 详细格式（含行号） | 开发调试、问题诊断 |
| `INFO` | 一般信息性消息 | 简洁格式 | 正常运行监控 |
| `WARNING` | 警告信息（默认） | 简洁格式 | 生产环境推荐 |
| `ERROR` | 错误信息 | 简洁格式 | 错误追踪 |
| `CRITICAL` | 严重错误 | 简洁格式 | 系统故障 |

### 实用日志配置示例
调试命令示范
```bash
vcg.py design.v --log-level DEBUG --log-file debug.log
```
- 控制台显示详细调试信息（含行号）
- 文件记录完整调试日志


##  VCG块语法

### 基本结构

在Verilog文件中使用特殊注释标记来定义VCG代码块：

```verilog
module example();

//VCG_BEGIN
//for i in range(4):
//    print(f"wire [7:0] data_{i};")
//VCG_END

//VCG_GEN_BEGIN_0
wire [7:0] data_0;
wire [7:0] data_1;
wire [7:0] data_2;
wire [7:0] data_3;
//VCG_GEN_END_0

endmodule
```

### 标记说明

- `//VCG_BEGIN` / `//VCG_END`：标记Python代码块的开始和结束
- `//VCG_GEN_BEGIN_X` / `//VCG_GEN_END_X`：标记生成代码的插入区域（X为块ID）

> **提示**：生成区域会在首次运行时自动创建，后续运行会更新其中的内容

##  内置函数详解

### 1. Instance() - 模块实例化

生成模块实例化代码，支持自动端口连接和参数配置。

```python
Instance(file_path, module_name, instance_name)
```

**参数说明**：
- `file_path`：模块定义文件路径
- `module_name`：模块名称
- `instance_name`：实例名称

**示例**：
```verilog
//VCG_BEGIN
//Instance("uart_tx.v", "uart_tx", "u_uart_tx")
//VCG_END
```

### 2. Connect() - 信号连接规则

定义端口到信号的连接映射规则，支持模式匹配和函数变换。

```python
Connect(port_pattern, signal_pattern, port_type=None)
```

**参数说明**：
- `port_pattern`：端口名称模式（支持`*`通配符）
- `signal_pattern`：目标信号模式（支持函数调用）
- `port_type`：可选，过滤端口类型（`input`/`output`/`inout`）

**基础示例**：
```python
# 直接映射
Connect("clk", "sys_clk")
Connect("rst_n", "sys_rst_n")

# 通配符映射
Connect("data_*", "bus_data_*")
Connect("*_valid", "*_vld")
```

**高级函数变换**：
```python
# 字符串函数处理
Connect("*_enable", "${upper(*_en)}")     # data_enable -&gt; DATA_EN
Connect("*_input", "${replace(*, 'input', 'in')}")  # data_input -&gt; data_in

# 行内注释
Connect("*_data", "*_bus /*data bus*/")
```

**端口类型过滤**：
```python
# 只连接输入端口
Connect("*", "tb_*", port_type="input")

# 只连接输出端口  
Connect("*_out", "*_result", port_type="output")
```

### 3. ConnectParam() - 参数连接

定义模块参数的连接规则。

```python
ConnectParam(param_name, param_value)
```

**示例**：
```python
ConnectParam("WIDTH", "32")
ConnectParam("DEPTH", "1024")
ConnectParam("*_WIDTH", "DATA_WIDTH")  # 支持通配符
```

### 4. WiresRule() - 线网生成规则

定义从端口生成wire声明的规则。

```python
WiresRule(port_pattern, wire_pattern, width=None, expression=None)
```

**参数说明**：
- `port_pattern`：端口名称模式
- `wire_pattern`：wire名称模式
- `width`：可选，指定位宽
- `expression`：可选，指定赋值表达式

**示例**：
```python
# 基本wire生成
WiresRule("*_in", "*_wire")

# 指定位宽
WiresRule("data_*", "internal_*", width="16")

# 生成带赋值的wire
WiresRule("*_const", "*_wire", expression="1'b0")

# 禁用某些端口的wire生成
WiresRule("clk", "")  # 空字符串表示不生成
```

### 5. WiresDef() - 生成线网声明

根据预设规则生成wire声明代码。

```python
WiresDef(file_path, module_name, port_type=None)
```

**参数说明**：
- `file_path`：模块文件路径
- `module_name`：模块名称  
- `port_type`：可选，只处理特定类型端口

**示例**：
```python
# 生成所有端口的wire
WiresDef("memory.v", "memory")

# 只生成输入端口的wire
WiresDef("cpu.v", "cpu", port_type="input")
```

##  完整使用示例

### 示例1：批量实例化

```verilog
module top_module();

//VCG_BEGIN
//# 批量生成memory实例
//for i in range(4):
//    Connect("addr", f"mem_addr_{i}")
//    Connect("data_*", f"mem_data_{i}_*") 
//    Connect("*_en", f"mem_{i}_*_en")
//    ConnectParam("ADDR_WIDTH", "10")
//    ConnectParam("DATA_WIDTH", "32")
//    Instance("memory.v", "memory", f"u_memory_{i}")
//    print()  # 添加空行分隔
//VCG_END

//VCG_GEN_BEGIN_0
memory #(
    .ADDR_WIDTH         (10),
    .DATA_WIDTH         (32)
) u_memory_0 (
    .addr               (mem_addr_0),        // input [9:0]
    .data_in            (mem_data_0_in),     // input [31:0]
    .data_out           (mem_data_0_out),    // output [31:0]
    .read_en            (mem_0_read_en),     // input
    .write_en           (mem_0_write_en)     // input
);

memory #(
    .ADDR_WIDTH         (10),
    .DATA_WIDTH         (32)
) u_memory_1 (
    .addr               (mem_addr_1),        // input [9:0]
    .data_in            (mem_data_1_in),     // input [31:0]
    .data_out           (mem_data_1_out),    // output [31:0]
    .read_en            (mem_1_read_en),     // input
    .write_en           (mem_1_write_en)     // input
);
// ... 更多实例
//VCG_GEN_END_0

endmodule
```

### 示例2：复杂连接规则

```verilog
module interconnect();

//VCG_BEGIN
//# 定义复杂的信号映射规则
//connections = {
//    "cpu": {"prefix": "cpu", "suffix": ""},
//    "dma": {"prefix": "dma", "suffix": "_dma"},  
//    "uart": {"prefix": "uart", "suffix": "_uart"}
//}
//
//for name, config in connections.items():
//    # 设置连接规则
//    Connect("*", f"{config['prefix']}_*{config['suffix']}")
//    Connect("clk", "sys_clk")
//    Connect("rst_n", "sys_rst_n") 
//    
//    # 根据模块类型设置不同参数
//    if name == "cpu":
//        ConnectParam("CACHE_SIZE", "4096")
//    elif name == "uart":
//        ConnectParam("BAUD_RATE", "115200")
//    
//    Instance(f"{name}.v", name, f"u_{name}")
//    print()
//VCG_END

endmodule
```

### 示例3：自动线网生成

```verilog
module wrapper();

//VCG_BEGIN
//# 设置wire生成规则
//WiresRule("*_input", "*_i")           # 输入信号重命名
//WiresRule("*_output", "*_o")          # 输出信号重命名  
//WiresRule("*_enable", "*_en")         # 使能信号缩写
//WiresRule("clk", "")                  # 时钟不生成wire
//WiresRule("rst_n", "")                # 复位不生成wire
//WiresRule("*_const", "*_wire", expression="1'b0")  # 常量wire
//
//# 生成wire声明
//WiresDef("processor.v", "processor")
//VCG_END

//VCG_GEN_BEGIN_0
wire [31:0] data_i;
wire [31:0] addr_i;
wire [7:0] status_o;
wire valid_en;
wire ready_en;
wire error_wire = 1'b0;
//VCG_GEN_END_0

endmodule
```

##  最佳实践

### 1. 代码组织建议

```python
# 推荐的代码块组织方式
//VCG_BEGIN
//# 1. 首先定义所有连接规则
//Connect("*", "internal_*")
//Connect("clk", "sys_clk")
//
//# 2. 然后定义参数规则  
//ConnectParam("WIDTH", "32")
//
//# 3. 最后进行实例化
//Instance("module.v", "module", "u_module")
//VCG_END
```

### 2. 使用字典和列表进行批量处理

```python
//VCG_BEGIN
//# 使用数据结构简化重复代码
//modules = [
//    {"name": "alu", "width": 32, "stages": 4},
//    {"name": "multiplier", "width": 16, "stages": 8},
//    {"name": "divider", "width": 32, "stages": 16}
//]
//  
//for mod in modules:
//    Connect("*", f"{mod['name']}_*")
//    Connect("clk", "sys_clk")
//    ConnectParam("WIDTH", str(mod['width']))
//    ConnectParam("STAGES", str(mod['stages']))
//    Instance(f"{mod['name']}.v", mod['name'], f"u_{mod['name']}")
//    print()
//VCG_END
```

## 高级模式匹配技巧
### 1.多级通配符

```python
Connect("bus_*_*", "interconnect_${*0}_${*1}")
# bus_axi_data -> interconnect_axi_data
# bus_ahb_addr -> interconnect_ahb_addr
```

### 2.函数组合使用
```python
Connect("*_in", "${upper(replace(*,'_in',''))}_INPUT")
# data_in -> DATA_INPUT
# addr_in -> ADDR_INPUT
```

### 3.注释嵌入连接
```python
Connect("enable", "1 /*always enabled*/")
Connect("debug_*", "0 /*debug disabled in release*/")
```



##  注意事项与限制

### 函数调用顺序

```python
# ✅ 正确的顺序
Connect("*", "sig_*")           # 先定义连接规则
ConnectParam("WIDTH", "32")     # 再定义参数规则
Instance("mod.v", "mod", "u1")  # 最后实例化

# ❌ 错误的顺序 - Instance会清空之前的规则
Instance("mod.v", "mod", "u1")  # 实例化后规则被清空
Connect("*", "sig_*")           # 这个规则不会生效
```

### Wire规则限制

```python
# ✅ 正确的顺序
WiresRule("*_in", "*_wire")     # 先定义规则
WiresDef("mod.v", "mod")        # 再生成wire

# ❌ 错误的顺序
WiresDef("mod.v", "mod")        # 生成后规则被清空
WiresRule("*_in", "*_wire")     # 这个规则不会生效
```

### 模式匹配限制

```python
# ✅ 支持的模式
Connect("data_*", "bus_*")      # 单通配符
Connect("*_valid_*", "*_vld_*") # 多通配符
Connect("exact_name", "target") # 精确匹配

# ❌ 不支持的模式
Connect("data_[0-9]+", "bus_*") # 不支持正则表达式
Connect("data_?", "bus_*")      # 不支持?通配符
```

### 函数调用限制

```python
# ✅ 支持的函数
Connect("*", "${upper(*)}")     # 大小写转换
Connect("*", "${replace(*, 'old', 'new')}")  # 字符串替换

# ❌ 不支持的函数  
Connect("*", "${len(*)}")       # 不支持len等其他函数
Connect("*", "${custom_func(*)}")  # 不支持自定义函数
```

### 块嵌套限制

```verilog
//VCG_BEGIN
//if condition:
//    # 不能在这里再包含VCG_BEGIN/VCG_END
//VCG_END
```

##  故障排除

### 常见错误及解决方案

#### 1. 文件未找到错误
```
VCG Error: File Missing: module.v
```
**解决方案**：检查文件路径是否正确，确保文件存在且可访问。

#### 2. Python语法错误  
```
VCG Error: Python syntax Error: invalid syntax (Line 3)
```
**解决方案**：检查VCG块中的Python代码语法，注意缩进和语法规范。

#### 3. 宏格式错误
```
VCG Error: 不能混合使用宏格式
```
**解决方案**：统一使用一种宏格式，不要混合简单列表和键值对格式。

#### 4. 连接规则不生效
**症状**：Instance生成的代码中端口连接没有按预期映射
**解决方案**：确保Connect规则在Instance调用之前定义。

