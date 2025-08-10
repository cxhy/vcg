# VCG (Verilog Code Generator) 详细使用说明

## 项目概述

VCG (Verilog Code Generator) 是一个强大的Verilog代码自动生成工具，通过在Verilog文件中嵌入Python代码块来实现智能化的代码生成。该工具特别适用于复杂的模块实例化、线网声明和信号连接的自动化处理。

### 核心特性

- **嵌入式Python执行**：在Verilog文件中直接编写Python代码
- **智能模块实例化**：自动解析模块接口并生成实例化代码
- **灵活的线网管理**：支持多种线网声明模式和规则
- **强大的规则系统**：支持模式匹配和信号映射规则
- **完善的日志系统**：提供详细的调试和错误信息
- **宏支持**：兼容Verilog预处理器宏定义

## 安装和环境要求

### 系统要求
- Python 3.6 或更高版本
- 支持的操作系统：Linux, macOS, Windows

### 依赖安装
VCG只需要独立安装一个第三方库：

```bash
pip install ply
```

其他所有依赖模块已包含在项目本地目录中，无需额外安装。

## 命令行参数详解

### 基本语法
```bash
python vcg_main.py <verilog_file> [options]
```

### 参数说明

#### 必需参数
- `file`：要处理的Verilog文件路径

#### 可选参数

**调试选项**
- `--debug`：启用调试模式，显示详细的处理信息
- `--macros MACRO_LIST`：指定Verilog宏定义
  - 格式1：`MACRO1,MACRO2` （无值宏）
  - 格式2：`MACRO1=val1,MACRO2=val2` （带值宏）

**日志选项**
- `--log-level LEVEL`：设置日志级别
  - 可选值：`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
  - 默认：`WARNING`
- `--log-file FILE`：将日志输出到文件
- `--quiet`：静默模式，仅在控制台显示错误信息

### 使用示例
```bash
# 基本使用
python vcg_main.py uart.v

# 调试模式
python vcg_main.py uart.v --debug

# 指定宏定义
python vcg_main.py uart.v --macros "WIDTH=8,DEPTH=16"

# 详细日志并输出到文件
python vcg_main.py uart.v --log-level DEBUG --log-file vcg.log
```

## VCG语法和功能说明

### VCG代码块结构

VCG代码必须包含在特定的注释标记之间：

```verilog
//VCG_BEGIN
// Python代码写在这里
// 每行以 // 开头
//VCG_END
```

生成的内容将自动插入到 `//VCG_GEN_BEGIN_X` 和 `//VCG_GEN_END_X` 标记之间。

## 核心规则系统详解

VCG的核心优势在于其强大的规则匹配和转换系统，该系统支持三种类型的规则处理：

### 规则优先级机制

VCG采用**后进先出（LIFO）**的规则优先级机制。这意味着：
- 最后定义的规则具有最高优先级
- 在匹配时，系统从最新的规则开始检查
- 第一个匹配成功的规则将被应用，后续规则被忽略
- 每次调用Instance函数会清空之前所有Connect/ConnectParam函数指定的规则
- 每次调用WiresDef函数会清空之前所有WiredRule函数指定的规则

**实践建议**：将最具体的规则放在最后定义，将通用规则放在前面定义。

### 信号连接规则详解

#### 基本连接规则

信号连接规则负责将模块端口映射到具体的信号名称。

**语法**：
```python
Connect(源端口, 例化名, 端口类型=None)
```

#### 模式匹配系统

**通配符支持**：
- 使用 `*` 作为通配符，匹配任意长度的字符序列
- 支持在同一模式中使用多个通配符
- 系统自动将模式转换为正则表达式进行匹配

```verilog
//VCG_BEGIN
// Connect("clk_*", "sys_clk_*")     // 单通配符匹配
// Connect("*_req_*", "*_request_*") // 多通配符匹配
// Connect("data", "sys_data")       // 精确匹配（无通配符）
//VCG_END
```

**端口类型过滤**：
- 支持按端口方向过滤规则应用范围
- 可选值：`"input"`, `"output"`, `"inout"`
- 不指定时，规则对所有端口类型生效

```verilog
//VCG_BEGIN
// Connect("*", "ext_*", "input")   // 仅对输入端口生效
// Connect("*", "out_*", "output")  // 仅对输出端口生效
//VCG_END
```

#### 高级模式替换

**函数调用表达式**：

VCG支持在目标模式中使用python内置的字符串处理函数，格式为 `${function_name(arguments)}`：

```verilog
//VCG_BEGIN
// Connect("*", "${upper(*)}")           // 转换为大写
// Connect("*_in", "${replace(*, '_in', '_input')}")  // 字符串替换
// Connect("data_*", "${capitalize(*)}_BUS")  // 首字母大写并添加后缀
//VCG_END
```

**可用函数列表**：
- `upper()` - 转换为大写
- `lower()` - 转换为小写  
- `title()` - 每个单词首字母大写
- `capitalize()` - 首字母大写
- `replace(old, new)` - 字符串替换
- `strip()`, `lstrip()`, `rstrip()` - 去除空白字符

**多通配符引用**：
- `*` - 引用第一个捕获的内容
- `*0` - 引用第一个捕获的内容（等同于*）
- `*1` - 引用第二个捕获的内容
- `*2` - 引用第三个捕获的内容，依此类推

```verilog
//VCG_BEGIN
// Connect("*_to_*", "${upper(*0)}_TO_${lower(*1)}")
// // 如果输入是 "cpu_to_mem"，输出为 "CPU_TO_mem"
//VCG_END
```

#### 特殊值处理

**字面量自动扩展**：

当目标信号指定为字面量 `"0"` 或 `"1"` 时，VCG会自动根据端口位宽生成正确的Verilog位宽表示：

```verilog
//VCG_BEGIN
// Connect("enable", "1")    // 1位端口 → 1'b1
// Connect("data", "0")      // 8位端口 → 8'b00000000  
// Connect("mask", "1")      // 参数化位宽 → {WIDTH{1'b1}}
//VCG_END
```

**位宽处理规则**：
- 1位信号：生成 `1'b0` 或 `1'b1`
- 固定多位信号：生成 `n'b000...` 或 `n'b111...`
- 参数化位宽：生成 `{(width_expr){1'b0}}` 或 `{width_expr{1'b1}}`

#### 行内注释支持

VCG支持在连接规则中嵌入注释，这些注释会被保留在生成的代码中：

```verilog
//VCG_BEGIN
// Connect("clk", "sys_clk /*主系统时钟*/")
// Connect("rst", "sys_rst /*同步复位信号*/") 
//VCG_END
```

生成的代码中会保留这些注释：
```verilog
.clk    (sys_clk /*主系统时钟*/),
.rst    (sys_rst /*同步复位信号*/)
```

### 参数连接规则详解

参数连接规则用于为模块参数指定具体的数值。

#### 基本参数规则

**语法**：
```python
ConnectParam(参数名称模式, 参数值)
```

**特性**：
- 支持通配符模式匹配参数名称
- 按优先级顺序匹配，第一个匹配的规则生效
- 未匹配的参数将使用模块的默认值

```verilog
//VCG_BEGIN
// ConnectParam("WIDTH", "8")
// ConnectParam("*_DEPTH", "1024")     // 匹配所有以_DEPTH结尾的参数
// ConnectParam("CLK_*", "100000000")  // 匹配所有以CLK_开头的参数
//VCG_END
```

### wire规则详解

wire规则系统负责自动生成wire声明。

#### wire信号生成模式

VCG提供两种wire生成模式：

**Greedy模式（贪婪模式）**：
- 为所有扫描到的端口生成线网声明
- 没有匹配规则的端口使用端口名作为线网名
- 适用于需要完整线网声明的场景

**Lazy模式（懒惰模式）**：
- 仅为匹配规则的端口生成线网声明
- 没有匹配规则的端口被跳过
- 适用于只需要特定线网声明的场景

#### 基本线网规则

**语法**：
```python
WiresRule(端口模式, 线网名称模式, 位宽=None, 表达式=None)
```

**基本示例**：
```verilog
//VCG_BEGIN
// WiresRule("clk*", "*")              // 时钟信号保持原名
// WiresRule("data_*", "w_*")          // 数据信号添加w_前缀
// WiresRule("*_valid", "*_vld")       // valid信号简化为vld
//VCG_END
```

#### 位宽定义

VCG支持为生成的线网指定位宽：

```verilog
//VCG_BEGIN
// WiresRule("data_*", "w_*", "32")           // 固定32位宽
// WiresRule("addr_*", "w_*", "ADDR_WIDTH")   // 参数化位宽
// WiresRule("byte_*", "w_*", "8")            // 固定8位宽
//VCG_END
```

**位宽自动推导**：
- 如果规则未指定位宽，VCG会尝试从端口信息中推导
- 支持整数位宽、参数化表达式、复杂的位宽计算

#### 表达式绑定

VCG支持为线网生成赋值表达式，这对于常量绑定和简单逻辑组合非常有用：

```verilog
//VCG_BEGIN
// WiresRule("enable", "tie_high", "1", "1'b1")        // 常量绑定
// WiresRule("*_n", "*_inv", "", "~*")                 // 逻辑取反
// WiresRule("unused_*", "", "", "")                   // 跳过生成（空名称）
//VCG_END
```

生成的代码示例：
```verilog
wire            tie_high = 1'b1;    // input enable , 
wire            data_inv = ~data;   // input data_n ,
// unused信号被跳过，不生成任何声明
```

#### 高级线网生成

**条件生成**：
通过返回空的线网名称来跳过特定端口的生成：

```verilog
//VCG_BEGIN
// WiresRule("clk", "")        // 时钟信号不生成wire声明
// WiresRule("rst_n", "")      // 复位信号不生成wire声明  
// WiresRule("*", "w_*")       // 其他信号添加w_前缀
//VCG_END
```

**复杂模式匹配**：
```verilog
//VCG_BEGIN
// WiresRule("*_i2c_*", "${upper(*0)}_I2C_${lower(*1)}")
// WiresRule("mem_*_*", "memory_${*0}_${*1}_wire")
//VCG_END
```

### 线网声明生成

#### 基本使用

**语法**：
```python
WiresDef(文件路径, 模块名称, 端口类型=None, 模式='greedy')
```

**参数说明**：
- `文件路径`：要解析的Verilog文件路径
- `模块名称`：目标模块名称
- `端口类型`：可选的端口类型过滤（"input"、"output"、"inout"）
- `模式`：生成模式（"greedy" 或 "lazy"）

#### 实际应用示例

```verilog
//VCG_BEGIN
// # 设置线网生成规则
// WiresRule("clk", "")                    // 时钟不生成wire
// WiresRule("rst*", "")                   // 复位信号不生成wire
// WiresRule("*_valid", "*_vld")           // valid信号简化
// WiresRule("*", "w_*")                   // 其他信号添加前缀
// 
// # 生成特定模块的输入信号线网（lazy模式）
// WiresDef("uart.v", "uart_core", "input", "lazy")
//VCG_END
```

### 模块实例化

#### 基本实例化

**语法**：
```python
Instance(文件路径, 模块名称, 实例名称)
```

VCG会自动：
- 解析模块的端口和参数定义
- 应用已定义的连接规则和参数规则
- 生成格式化的实例化代码
- 添加端口注释（包括方向和位宽信息）

#### 实例化流程

1. **模块解析**：解析指定文件中的模块定义
2. **规则应用**：按优先级应用信号连接和参数规则
3. **代码生成**：生成格式化的实例化代码
4. **注释生成**：为每个端口添加方向和位宽注释

## 完整使用示例

### 示例1：复杂的信号映射和实例化

```verilog
module uart_system (
    input sys_clk,
    input sys_rst_n,
    // 其他端口...
);

//VCG_BEGIN
// # 建立信号连接规则（按优先级从低到高）
// Connect("*", "uart_*")              // 通用规则：添加uart_前缀
// Connect("clk*", "sys_clk")          // 时钟连接规则
// Connect("rst*", "sys_rst_n")        // 复位连接规则
// Connect("*_data", "bus_*_data")     // 数据总线规则
// Connect("tx_ready", "uart_tx_rdy")  // 特定信号重命名
// 
// # 设置参数
// ConnectParam("BAUD_RATE", "115200")
// ConnectParam("DATA_WIDTH", "8")
// 
// # 生成实例
// Instance("uart_core.v", "uart_core", "u_uart_core")
//VCG_END

endmodule
```

### 示例2：智能线网生成

```verilog
module memory_controller;

//VCG_BEGIN
// # 设置线网生成规则
// WiresRule("clk*", "*")                // 时钟保持原名
// WiresRule("rst*", "*")                      // 复位保持原名  
// WiresRule("mem_*_addr", "w_*_address", "[31:0]")  // 地址线重命名并指定位宽
// WiresRule("mem_*_data", "w_*_data", "[63:0]")     // 数据线重命名并指定位宽
// WiresRule("*_valid", "w_*_vld")             // valid信号简化
// WiresRule("*_ready", "w_*_rdy")             // ready信号简化
// WiresRule("tie_*", "w_tie_*", "1", "1'b*")  // 常量绑定（*匹配0或1）
// WiresRule("unused_*", "")                   // 未使用信号跳过生成
// 
// # 生成特定类型的线网（lazy模式，只生成匹配规则的）
// WiresDef("ddr_controller.v", "ddr_ctrl", "input", "lazy")
//VCG_END

endmodule
```

### 示例3：高级函数应用

```verilog
//VCG_BEGIN
// # 复杂的字符串变换
// Connect("*_req_*", "${upper(*0)}_REQUEST_${lower(*1)}")
// Connect("i2c_*", "${replace(*, 'i2c', 'I2C')}_BUS")
// Connect("*_clk_div_*", "clk_${*0}_div${*1}")
// 
// # 条件性的参数设置
// ConnectParam("*_WIDTH", "32")
// ConnectParam("FIFO_*_DEPTH", "512") 
// Instance("i2c_top.v", "i2c_top", "u_i2c_top")
// 
// # 带表达式的线网生成
// WiresRule("*_mask", "w_*_mask", "[DATA_WIDTH-1:0]", "{DATA_WIDTH{1'b1}}")
// WiresRule("*_zero", "w_*_zero", "[DATA_WIDTH-1:0]", "{DATA_WIDTH{1'b0}}")
// WiresDef("i2c_top.v", "i2c_top")
//VCG_END
```

## 最佳实践和使用技巧

### 规则设计原则

1. **从通用到具体**：先定义通用规则，再定义特殊情况的规则
2. **合理使用优先级**：利用后进先出的特性，将特殊规则放在后面
3. **避免规则冲突**：确保不同规则之间的逻辑一致性
4. **使用端口类型过滤**：减少不必要的规则匹配，提高性能

### 模式设计技巧

1. **通配符的合理使用**：
   - 尽量避免过于宽泛的模式（如单独使用`*`）
   - 在模式中包含足够的上下文信息

2. **函数调用的最佳实践**：
   - 优先使用内置安全函数
   - 合理嵌套函数调用以实现复杂变换
   - 注意函数参数的引用方式（`*`, `*0`, `*1`等）

3. **注释的有效使用**：
   - 在复杂的信号名称中添加描述性注释
   - 利用注释传递设计意图和约束信息

### 调试和优化

1. **使用调试模式**：
   ```bash
   python vcg_main.py file.v --debug --log-level DEBUG
   ```

2. **分步验证规则**：
   - 先定义简单规则，验证效果
   - 逐步添加复杂规则，观察变化

3. **性能优化建议**：
   - 合理使用lazy模式减少不必要的生成
   - 避免过于复杂的正则表达式模式
   - 使用端口类型过滤减少匹配次数

### 常见陷阱和注意事项

1. **规则优先级理解**：记住后定义的规则优先级更高
2. **通配符贪婪匹配**：`*`会匹配尽可能长的字符序列
3. **字面量自动转换**：`"0"`和`"1"`会根据位宽自动扩展
4. **函数调用安全性**：只能使用预定义的安全函数集合
5. **模式匹配区分大小写**：确保模式中的大小写与实际信号名一致

通过合理运用VCG的规则系统，可以大大提高Verilog代码生成的效率和一致性，特别是在大型项目中处理重复性的模块实例化和信号连接工作时，VCG能够显著减少手工编码的工作量并降低出错概率。