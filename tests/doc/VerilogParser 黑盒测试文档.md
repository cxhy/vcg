# VerilogParser 黑盒测试文档

## 1. 模块概述

**VerilogParser** 是一个用于解析Verilog模块声明的语法分析器，主要功能是提取Verilog模块的端口、参数等关键信息。

**支持的语法版本：**
- Verilog-1995
- Verilog-2001
- SystemVerilog（预留接口，暂不测试）

**核心能力：**
- 解析模块名称
- 提取参数定义（parameter/localparam）
- 提取端口声明（支持两种语法风格）
- 提供结构化的模块信息输出
- 宏预处理支持
- 语法错误容错

---

## 2. 编程接口（API）

### 2.1 类初始化

```python
VerilogParser(macros: Optional[Dict[str, str]] = None, debug: bool = False)
```

**参数说明：**
- `macros`: 可选，预处理宏定义字典，格式为 `{"宏名": "宏值"}`
- `debug`: 可选，是否启用调试模式，默认False

**返回值：** VerilogParser实例对象

---

### 2.2 核心方法

#### 2.2.1 parse_file - 文件解析

```python
parse_file(filepath: str) -> Optional[VerilogAST]
```

**功能：** 从文件路径读取并解析Verilog代码

**参数：**
- `filepath`: Verilog文件的完整路径（字符串）

**返回值：**
- 成功：返回 `VerilogAST` 对象
- 失败：返回 `None`

**失败场景：**
- 文件不存在
- 文件无读取权限
- 编码错误
- 语法解析失败

---

#### 2.2.2 parse_string - 字符串解析

```python
parse_string(verilog_code: str) -> Optional[VerilogAST]
```

**功能：** 直接解析Verilog代码字符串

**参数：**
- `verilog_code`: Verilog源代码字符串

**返回值：**
- 成功：返回 `VerilogAST` 对象
- 失败：返回 `None`

---

#### 2.2.3 get_module_info - 获取模块信息

```python
get_module_info() -> Optional[Dict[str, Any]]
```

**功能：** 获取解析后的模块结构化信息

**前置条件：** 必须先成功调用 `parse_file` 或 `parse_string`

**返回值：**
- 成功：返回包含以下字段的字典
- 失败（未解析或解析失败）：返回 `None`

**返回字典结构：**
```python
{
    "name": str,              # 模块名称
    "parameters": [           # 参数列表
        {
            "name": str,           # 参数名
            "type": str,           # 类型: "parameter" 或 "localparam"
            "default_value": str   # 默认值
        }
    ],
    "ports": [                # 端口列表
        {
            "name": str,           # 端口名
            "direction": str,      # 方向: "input"/"output"/"inout"
            "net_type": str,       # 网络类型: "wire"/"reg"/"logic"
            "range": str,          # 范围字符串，如 "[7:0]"
            "width": int,          # 位宽
            "type": str            # 端口类型枚举值
        }
    ]
}
```

---

## 3. 功能点分解与测试覆盖

### 3.1 模块声明解析

| 功能点ID | 功能描述 | 测试场景 | 预期结果 |
|---------|---------|---------|---------|
| F1.1 | 解析基本模块名 | `module test_mod; endmodule` | 正确提取模块名 "test_mod" |
| F1.2 | 解析带下划线的模块名 | `module test_mod_123; endmodule` | 正确提取模块名 |
| F1.3 | 空模块（无参数无端口） | `module empty; endmodule` | 返回空参数列表和空端口列表 |
| F1.4 | 模块名缺失 | `module ; endmodule` | 解析失败，返回None或错误 |

---

### 3.2 参数声明解析

#### 3.2.1 模块头部参数（Verilog-2001风格）

| 功能点ID | 功能描述 | 测试代码示例 | 预期结果 |
|---------|---------|-------------|---------|
| F2.1 | 单个parameter | `module m #(parameter P=1); endmodule` | 提取参数名"P"，类型"parameter"，值"1" |
| F2.2 | 单个localparam | `module m #(localparam L=2); endmodule` | 提取参数名"L"，类型"localparam"，值"2" |
| F2.3 | 多个参数（逗号分隔） | `module m #(parameter A=1, parameter B=2); endmodule` | 提取两个参数 |
| F2.4 | 混合parameter和localparam | `module m #(parameter P=1, localparam L=2); endmodule` | 正确区分类型 |
| F2.5 | 参数值为表达式 | `parameter WIDTH = 8*2` | 提取表达式字符串 "8*2" |
| F2.6 | 参数值为负数 | `parameter OFFSET = -10` | 提取值 "-10" |
| F2.7 | 参数值为十六进制 | `parameter ADDR = 16'hFFFF` | 提取值 "16'hFFFF" |
| F2.8 | 参数值为二进制 | `parameter MASK = 4'b1010` | 提取值 "4'b1010" |
| F2.9 | 参数值为八进制 | `parameter VAL = 8'o377` | 提取值 "8'o377" |
| F2.10 | 参数值包含运算符 | `parameter SIZE = 2**10` | 提取表达式 "2**10" |
| F2.11 | 空参数列表 | `module m #(); endmodule` | 返回空参数列表 |
| F2.12 | 参数声明语法错误 | `module m #(parameter); endmodule` | 记录错误，继续解析 |

#### 3.2.2 模块内部参数声明

| 功能点ID | 功能描述 | 测试代码示例 | 预期结果 |
|---------|---------|-------------|---------|
| F2.13 | 模块体内parameter | `module m; parameter P=1; endmodule` | 提取参数 |
| F2.14 | 模块体内localparam | `module m; localparam L=2; endmodule` | 提取参数 |
| F2.15 | 模块体内多个参数 | `module m; parameter A=1, B=2; endmodule` | 提取所有参数 |

---

### 3.3 端口声明解析

#### 3.3.1 Verilog-2001风格（ANSI风格）

端口声明在模块头部，包含方向、类型、位宽和名称

| 功能点ID | 功能描述 | 测试代码示例 | 预期结果 |
|---------|---------|-------------|---------|
| F3.1 | input端口（无类型） | `module m(input clk); endmodule` | direction="input", net_type="wire" |
| F3.2 | output端口（无类型） | `module m(output data); endmodule` | direction="output", net_type="wire" |
| F3.3 | inout端口（无类型） | `module m(inout bus); endmodule` | direction="inout", net_type="wire" |
| F3.4 | input wire端口 | `module m(input wire clk); endmodule` | direction="input", net_type="wire" |
| F3.5 | output reg端口 | `module m(output reg q); endmodule` | direction="output", net_type="reg" |
| F3.6 | 带位宽的端口 | `module m(input [7:0] data); endmodule` | width=8, range="[7:0]" |
| F3.7 | 非标准位宽（大端序） | `module m(input [31:0] bus); endmodule` | width=32, msb=31, lsb=0 |
| F3.8 | 非标准位宽（小端序） | `module m(input [0:7] data); endmodule` | width=8, msb=0, lsb=7 |
| F3.9 | 位宽使用参数表达式 | `module m(input [WIDTH-1:0] d); endmodule` | 提取表达式 "WIDTH-1" 和 "0" |
| F3.10 | 位宽使用复杂表达式 | `module m(input [2**N-1:0] d); endmodule` | 提取表达式 |
| F3.11 | 多个端口（逗号分隔） | `module m(input a, input b, output c); endmodule` | 提取3个端口 |
| F3.12 | logic类型端口（SV） | `module m(input logic sig); endmodule` | net_type="logic" |
| F3.13 | 空端口列表 | `module m(); endmodule` | 返回空端口列表 |

#### 3.3.2 Verilog-1995风格（非ANSI风格）

端口名称在模块头部，方向和类型在模块体内声明

| 功能点ID | 功能描述 | 测试代码示例 | 预期结果 |
|---------|---------|-------------|---------|
| F3.14 | 端口列表+input声明 | `module m(clk); input clk; endmodule` | 正确关联端口 |
| F3.15 | 端口列表+output声明 | `module m(data); output data; endmodule` | 正确关联端口 |
| F3.16 | 端口列表+inout声明 | `module m(bus); inout bus; endmodule` | 正确关联端口 |
| F3.17 | 多端口+批量声明 | `module m(a,b); input a,b; endmodule` | 关联多个端口 |
| F3.18 | 带位宽的V95声明 | `module m(d); input [7:0] d; endmodule` | 提取位宽 |
| F3.19 | input wire明确声明 | `module m(c); input wire c; endmodule` | net_type="wire" |
| F3.20 | output reg明确声明 | `module m(q); output reg q; endmodule` | net_type="reg" |
| F3.21 | 端口未声明方向 | `module m(x); endmodule` | 记录为未定义或默认处理 |
| F3.22 | 多端口混合声明 | `module m(a,b,c); input a; output b,c; endmodule` | 正确区分方向 |

---

### 3.4 表达式解析支持

用于参数值和位宽表达式

| 功能点ID | 功能描述 | 测试表达式 | 预期结果 |
|---------|---------|-----------|---------|
| F4.1 | 加法 | `WIDTH+1` | 保留表达式字符串 |
| F4.2 | 减法 | `SIZE-1` | 保留表达式字符串 |
| F4.3 | 乘法 | `8*2` | 保留表达式字符串 |
| F4.4 | 除法 | `WIDTH/2` | 保留表达式字符串 |
| F4.5 | 模运算 | `N%4` | 保留表达式字符串 |
| F4.6 | 幂运算 | `2**N` | 保留表达式字符串 |
| F4.7 | 括号表达式 | `(WIDTH+1)/2` | 保留表达式字符串 |
| F4.8 | 三元运算符 | `EN ? 8 : 4` | 保留表达式字符串 |
| F4.9 | 逻辑与 | `A && B` | 保留表达式字符串 |
| F4.10 | 逻辑或 | `A || B` | 保留表达式字符串 |
| F4.11 | 按位与 | `MASK & 8'hFF` | 保留表达式字符串 |
| F4.12 | 按位或 | `A | B` | 保留表达式字符串 |
| F4.13 | 按位异或 | `A ^ B` | 保留表达式字符串 |
| F4.14 | 左移 | `1 << N` | 保留表达式字符串 |
| F4.15 | 右移 | `VAL >> 2` | 保留表达式字符串 |
| F4.16 | 比较运算 | `WIDTH > 8` | 保留表达式字符串 |
| F4.17 | 一元负号 | `-OFFSET` | 保留表达式字符串 |
| F4.18 | 一元取反 | `~MASK` | 保留表达式字符串 |
| F4.19 | 函数调用 | `$clog2(SIZE)` | 保留表达式字符串 |
| F4.20 | 位选择 | `BUS[3]` | 保留表达式字符串 |
| F4.21 | 位片选择 | `DATA[7:4]` | 保留表达式字符串 |
| F4.22 | 拼接 | `{A, B, C}` | 保留表达式字符串 |

---

### 3.5 错误处理和容错

| 功能点ID | 功能描述 | 测试场景 | 预期行为 |
|---------|---------|---------|---------|
| F5.1 | 文件不存在 | 解析不存在的文件路径 | 返回None，记录错误日志 |
| F5.2 | 文件编码错误 | 包含非UTF-8字符的文件 | 返回None，记录错误 |
| F5.3 | 模块声明语法错误 | 缺少endmodule |尝试恢复，记录错误 |
| F5.4 | 端口声明语法错误 | `module m(input ); endmodule` | 记录错误，继续解析 |
| F5.5 | 参数声明语法错误 | `parameter ;` | 记录错误，继续解析 |
| F5.6 | 位宽表达式错误 | `input [error] d;` | 记录错误，继续解析 |
| F5.7 | 表达式语法错误 | `parameter P = ++;` | 记录错误 |
| F5.8 | EOF前遇到语法错误 | 不完整的模块 | 记录错误，返回部分结果 |
| F5.9 | 多次调用parse方法 | 解析多个不同模块 | 每次独立解析，不互相影响 |

---

### 3.6 宏预处理

| 功能点ID | 功能描述 | 测试场景 | 预期结果 |
|---------|---------|---------|---------|
| F6.1 | 初始化时传入宏 | `macros={"WIDTH": "8"}` | 宏替换生效 |
| F6.2 | 宏在参数中使用 | `parameter P = \`WIDTH` | 替换为宏值 |
| F6.3 | 宏在位宽中使用 | `input [\`WIDTH-1:0] d;` | 替换为宏值 |
| F6.4 | 未定义的宏 | 使用未定义的\`MACRO | 按预处理器默认行为 |

---

## 4. 边界条件和特殊场景

### 4.1 极端情况

| 场景ID | 描述 | 测试用例 | 预期结果 |
|-------|------|---------|---------|
| B1 | 完全空模块 | `module e; endmodule` | 成功解析，空列表 |
| B2 | 超长模块名 | 1000字符的模块名 | 正常解析或合理限制 |
| B3 | 大量端口 | 1000个端口 | 正常解析 |
| B4 | 大量参数 | 1000个参数 | 正常解析 |
| B5 | 深度嵌套表达式 | `((((A+B)+C)+D)+E)` | 正常解析 |
| B6 | 超大数值 | `128'hFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF` | 保留原字符串 |
| B7 | 空字符串解析 | `parse_string("")` | 返回None或空AST |
| B8 | 仅空白符 | `parse_string("   \n\n  ")` | 返回None或空AST |

### 4.2 混合风格

| 场景ID | 描述 | 测试用例 | 预期结果 |
|-------|------|---------|---------|
| B9 | V95和V2001混合 | 同时使用两种端口声明风格 | 正确解析，允许混合 |
| B10 | 头部和内部都有参数 | 参数同时在#()和模块体内 | 全部提取 |

### 4.3 注释和空白

| 场景ID | 描述 | 测试用例 | 预期结果 |
|-------|------|---------|---------|
| B11 | 单行注释 | 代码中包含 `// comment` | 注释被忽略 |
| B12 | 多行注释 | 代码中包含 `/* comment */` | 注释被忽略 |
| B13 | 注释嵌入声明 | `input /* comment */ clk` | 正常解析 |

---

## 5. 测试数据准备建议

### 5.1 基础测试用例文件

| 文件名 | 用途 | 关键特征 |
|-------|------|---------|
| `basic_empty.v` | 空模块 | 无参数无端口 |
| `basic_ports_v2001.v` | V2001端口 | ANSI风格端口声明 |
| `basic_ports_v95.v` | V95端口 | 非ANSI风格 |
| `basic_params.v` | 参数测试 | 多种参数类型 |
| `complex_expressions.v` | 复杂表达式 | 各类运算符 |
| `mixed_style.v` | 混合风格 | V95+V2001 |
| `error_syntax.v` | 语法错误 | 各种错误场景 |
| `large_scale.v` | 大规模模块 | 大量端口和参数 |

### 5.2 推荐测试框架

```python
# 示例测试结构
class TestVerilogParser:
    def setup(self):
        self.parser = VerilogParser()
    
    def test_parse_empty_module(self):
        ast = self.parser.parse_string("module empty; endmodule")
        assert ast is not None
        info = self.parser.get_module_info()
        assert info['name'] == 'empty'
        assert len(info['ports']) == 0
        assert len(info['parameters']) == 0
    
    def test_parse_v2001_input_port(self):
        code = "module test(input clk); endmodule"
        ast = self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert len(info['ports']) == 1
        assert info['ports'][0]['name'] == 'clk'
        assert info['ports'][0]['direction'] == 'input'
    
    # ... 更多测试用例
```

---

## 6. 验证检查清单

### 6.1 功能正确性验证

- [ ] 所有端口名称正确提取
- [ ] 所有端口方向正确识别
- [ ] 所有端口类型正确识别
- [ ] 所有端口位宽正确计算
- [ ] 所有参数名称正确提取
- [ ] 所有参数类型正确区分
- [ ] 所有参数默认值正确保存
- [ ] 模块名称正确提取

### 6.2 兼容性验证

- [ ] Verilog-1995语法全覆盖
- [ ] Verilog-2001语法全覆盖
- [ ] 混合语法正确处理
- [ ] 各种表达式类型支持

### 6.3 健壮性验证

- [ ] 文件不存在时不崩溃
- [ ] 语法错误时不崩溃
- [ ] 空输入时不崩溃
- [ ] 大规模输入时性能可接受
- [ ] 多次调用不相互干扰

### 6.4 输出验证

- [ ] 返回值类型正确
- [ ] 字典结构符合文档
- [ ] 所有字段都存在
- [ ] 字段值类型正确

---

## 7. 已知限制

根据代码分析，以下功能**不在测试范围内**：

1. **SystemVerilog接口解析**：代码中预留但未实现
2. **模块内部逻辑**：assign、always、实例化等仅做语法解析，不提取详细信息
3. **表达式求值**：表达式仅保存字符串形式，不计算具体值
4. **语义检查**：不检查端口名冲突、参数重定义等语义问题
5. **跨文件引用**：不处理`include指令和多文件依赖

---

## 8. 测试执行建议

### 8.1 优先级划分

**P0（必须测试）：**
- 基本模块解析（F1组）
- 基本端口解析（F3.1-F3.13）
- 基本参数解析（F2.1-F2.12）
- 文件不存在错误处理（F5.1）

**P1（重要测试）：**
- V95风格端口（F3.14-F3.22）
- 表达式支持（F4组）
- 其他错误处理（F5组）

**P2（补充测试）：**
- 边界条件（B组）
- 宏预处理（F6组）
- 性能测试

