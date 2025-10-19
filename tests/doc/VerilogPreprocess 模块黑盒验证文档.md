# VerilogPreprocess.py 黑盒验证文档

## 1. 模块概述

`VerilogPreprocess` 是一个专门用于 Verilog 代码条件编译预处理的 Python 模块。该模块的核心功能是处理 Verilog 代码中的条件编译指令（如 `ifdef`、`ifndef`、`else`、`elsif`、`endif`），并提取模块声明及端口定义部分。

**重要说明：** 本预处理器仅处理条件编译指令，**不展开宏参数**，这与标准的 Verilog 预处理器有所不同。

---

## 2. 编程接口（API）

### 2.1 类初始化

```python
VerilogPreprocess(macros=None)
```

**功能：** 创建预处理器实例并初始化宏定义。

**参数：**
- `macros`: 宏定义，支持三种格式：
  - `None`: 无宏定义（空字典）
  - `Dict[str, str]`: 字典格式，如 `{"MACRO1": "value1", "MACRO2": "value2"}`
  - `List[str]`: 字符串列表，如 `["MACRO1", "MACRO2"]`（默认值为 "1"）
  - `List[Tuple[str, str]]`: 元组列表，如 `[("MACRO1", "value1"), ("MACRO2", "value2")]`

**返回：** `VerilogPreprocess` 实例

**异常：**
- `ValueError`: 当宏定义格式不正确时抛出

---

### 2.2 主要方法

#### 2.2.1 预处理文件

```python
preprocess_file(file_path: str) -> str
```

**功能：** 读取并预处理 Verilog 文件。

**参数：**
- `file_path` (str): Verilog 文件的路径

**返回：** 
- `str`: 预处理后的 Verilog 代码（仅包含模块声明和端口定义）

**异常：**
- `FileNotFoundError`: 文件不存在
- `RuntimeError`: 预处理过程中发生错误

---

#### 2.2.2 预处理字符串

```python
preprocess_string(verilog_code: str) -> str
```

**功能：** 直接预处理 Verilog 代码字符串。

**参数：**
- `verilog_code` (str): Verilog 代码字符串

**返回：** 
- `str`: 预处理后的 Verilog 代码（仅包含模块声明和端口定义）

**异常：**
- `RuntimeError`: 预处理过程中发生错误

---

#### 2.2.3 宏管理方法

```python
get_macros() -> Dict[str, str]
```

**功能：** 获取当前定义的所有宏（返回副本，不影响内部状态）。

**返回：** 
- `Dict[str, str]`: 宏定义字典

---

```python
clear_macros() -> None
```

**功能：** 清空所有宏定义。

**返回：** 无

---

## 3. 功能点详细说明

### 3.1 宏定义初始化（`_parse_macros`）

#### 功能点 3.1.1: 处理 None 输入
- **输入：** `macros = None`
- **预期输出：** 返回空字典 `{}`
- **测试用例：** `VerilogPreprocess(None)`

#### 功能点 3.1.2: 处理字典输入
- **输入：** `macros = {"ENABLE": "1", "WIDTH": "32"}`
- **预期输出：** 返回相同的字典
- **边界条件：**
  - 键必须是字符串
  - 值必须是字符串
  - 空字典应正常处理

#### 功能点 3.1.3: 处理字符串列表输入
- **输入：** `macros = ["ENABLE", "DEBUG"]`
- **预期输出：** `{"ENABLE": "1", "DEBUG": "1"}`
- **边界条件：**
  - 空列表应返回空字典
  - 列表中的每个元素必须是字符串

#### 功能点 3.1.4: 处理元组列表输入
- **输入：** `macros = [("ENABLE", "1"), ("WIDTH", "32")]`
- **预期输出：** `{"ENABLE": "1", "WIDTH": "32"}`
- **边界条件：**
  - 元组必须是二元组
  - 元组的两个元素都必须是字符串

#### 功能点 3.1.5: 异常处理
- **测试场景：**
  - 字典的键不是字符串
  - 字典的值不是字符串
  - 列表中包含非字符串、非元组的元素
  - 元组长度不是 2
  - 元组中的元素不是字符串
  - 传入不支持的类型（如整数、浮点数）
- **预期输出：** 抛出 `ValueError` 异常

---

### 3.2 文件读取（`read_file`）

#### 功能点 3.2.1: 读取存在的文件
- **输入：** 有效的文件路径
- **预期输出：** 返回文件内容字符串
- **编码支持：** 优先使用 UTF-8，失败时回退到 Latin-1

#### 功能点 3.2.2: 处理不存在的文件
- **输入：** 不存在的文件路径
- **预期输出：** 抛出 `FileNotFoundError` 异常，消息格式为 `"Verilog File Missing: {file_path}"`

#### 功能点 3.2.3: 编码处理
- **测试场景：**
  - UTF-8 编码的文件
  - Latin-1 编码的文件
  - 包含特殊字符的文件

---

### 3.3 移除模块前内容（`remove_pre_module_content`）

#### 功能点 3.3.1: 正常移除
- **输入：** 包含模块前注释、包含语句等的 Verilog 代码
- **预期输出：** 从第一个 `module` 关键字开始的内容
- **测试用例：**
```verilog
// 这是注释
`include "header.v"

module test_module;
  // 模块内容
endmodule
```
- **预期结果：** 只保留从 `module test_module;` 开始的内容

#### 功能点 3.3.2: 无模块的情况
- **输入：** 不包含 `module` 关键字的代码
- **预期输出：** 空字符串或空行

#### 功能点 3.3.3: 模块关键字识别
- **测试场景：**
  - `module test_module;`
  - `  module test_module;`（带前导空格）
  - `module test_module(port1, port2);`
  - 注释中的 "module" 不应触发（但代码未处理注释，需注意）

---

### 3.4 提取模块端口声明（`extract_module_ports_section`）

#### 功能点 3.4.1: 提取模块声明
- **输入：** 包含完整模块定义的代码
- **预期输出：** 
  - 第一个返回值：模块声明及所有端口/参数声明
  - 第二个返回值：字符串 `"endmodule"`

#### 功能点 3.4.2: 识别模块声明结束
- **测试场景：**
  - 模块声明在一行内结束：`module test;`
  - 模块声明跨多行：
```verilog
module test(
  input clk,
  input rst
);
```

#### 功能点 3.4.3: 识别端口声明关键字
- **支持的关键字：**
  - `input`
  - `output`
  - `inout`
  - `parameter`
- **测试场景：**
  - 单行声明：`input wire clk;`
  - 多行声明：
```verilog
input wire [7:0] 
  data;
```
  - 带前导空格的声明
  - 大小写不敏感（`INPUT`、`Input` 等）

#### 功能点 3.4.4: 处理多行声明
- **输入：** 跨多行的端口声明
- **预期输出：** 完整保留声明（直到遇到分号）
- **测试用例：**
```verilog
input wire [31:0]
  data_in,
  data_out;
```

#### 功能点 3.4.5: 遇到 endmodule 停止
- **输入：** 包含模块内部逻辑的完整模块
- **预期输出：** 只提取到端口声明部分，遇到 `endmodule` 或非声明语句停止

---

### 3.5 条件编译处理（`process_conditional_compilation`）

这是核心功能，需要详细测试所有分支。

#### 功能点 3.5.1: `ifdef` 指令处理

**子功能点 3.5.1.1: 宏已定义**
- **输入：**
```verilog
`ifdef ENABLE
  input enable;
`endif
```
- **宏定义：** `{"ENABLE": "1"}`
- **预期输出：** 保留 `input enable;`

**子功能点 3.5.1.2: 宏未定义**
- **输入：** 同上
- **宏定义：** `{}`
- **预期输出：** 移除 `input enable;`

#### 功能点 3.5.2: `ifndef` 指令处理

**子功能点 3.5.2.1: 宏未定义**
- **输入：**
```verilog
`ifndef DISABLE
  input enable;
`endif
```
- **宏定义：** `{}`
- **预期输出：** 保留 `input enable;`

**子功能点 3.5.2.2: 宏已定义**
- **输入：** 同上
- **宏定义：** `{"DISABLE": "1"}`
- **预期输出：** 移除 `input enable;`

#### 功能点 3.5.3: `else` 指令处理

**子功能点 3.5.3.1: ifdef 不满足，else 分支生效**
- **输入：**
```verilog
`ifdef ENABLE
  input enable;
`else
  input disable;
`endif
```
- **宏定义：** `{}`
- **预期输出：** 保留 `input disable;`，移除 `input enable;`

**子功能点 3.5.3.2: ifdef 满足，else 分支不生效**
- **输入：** 同上
- **宏定义：** `{"ENABLE": "1"}`
- **预期输出：** 保留 `input enable;`，移除 `input disable;`

#### 功能点 3.5.4: `elsif` 指令处理

**子功能点 3.5.4.1: ifdef 满足，elsif 不执行**
- **输入：**
```verilog
`ifdef MACRO1
  input port1;
`elsif MACRO2
  input port2;
`endif
```
- **宏定义：** `{"MACRO1": "1", "MACRO2": "1"}`
- **预期输出：** 保留 `input port1;`，移除 `input port2;`

**子功能点 3.5.4.2: ifdef 不满足，elsif 满足**
- **输入：** 同上
- **宏定义：** `{"MACRO2": "1"}`
- **预期输出：** 移除 `input port1;`，保留 `input port2;`

**子功能点 3.5.4.3: ifdef 和 elsif 都不满足**
- **输入：** 同上
- **宏定义：** `{}`
- **预期输出：** 移除所有内容

**子功能点 3.5.4.4: 多个 elsif**
- **输入：**
```verilog
`ifdef MACRO1
  input port1;
`elsif MACRO2
  input port2;
`elsif MACRO3
  input port3;
`else
  input port4;
`endif
```
- **测试场景：**
  - 只有 MACRO1 定义
  - 只有 MACRO2 定义
  - 只有 MACRO3 定义
  - 都不定义（走 else）
  - 多个都定义（只有第一个满足的生效）

#### 功能点 3.5.5: 嵌套条件编译

**子功能点 3.5.5.1: 两层嵌套**
- **输入：**
```verilog
`ifdef OUTER
  input outer_port;
  `ifdef INNER
    input inner_port;
  `endif
`endif
```
- **测试场景：**
  - 只定义 OUTER：保留 `outer_port`，移除 `inner_port`
  - 只定义 INNER：移除所有
  - 都定义：保留所有
  - 都不定义：移除所有

**子功能点 3.5.5.2: 三层或更多嵌套**
- **输入：** 多层嵌套的条件编译
- **预期行为：** 正确处理条件栈

**子功能点 3.5.5.3: 嵌套中的 else 和 elsif**
- **输入：**
```verilog
`ifdef OUTER
  `ifdef INNER
    input port1;
  `else
    input port2;
  `endif
`else
  input port3;
`endif
```
- **测试所有可能的宏定义组合**

#### 功能点 3.5.6: 注释处理

**子功能点 3.5.6.1: 单行注释**
- **输入：** 包含 `//` 的行
- **预期输出：** 根据条件编译状态决定是否保留

**子功能点 3.5.6.2: 多行注释**
- **输入：** 包含 `/*` 的行
- **预期输出：** 根据条件编译状态决定是否保留

#### 功能点 3.5.7: 边界条件

- **空内容：** 空字符串输入
- **只有指令没有内容：** 只有 `ifdef`、`endif`
- **不匹配的指令：** `endif` 多于 `ifdef`（应该能容错）
- **指令不匹配：** `ifdef` 多于 `endif`（未闭合）
- **空白行：** 条件块中的空白行应正确处理

---

### 3.6 完整预处理流程

#### 功能点 3.6.1: `preprocess_file` 集成测试
- **测试流程：**
  1. 读取文件
  2. 移除模块前内容
  3. 处理条件编译
  4. 提取模块和端口声明
  5. 返回结果

#### 功能点 3.6.2: `preprocess_string` 集成测试
- **与 `preprocess_file` 的区别：** 不需要读取文件

#### 功能点 3.6.3: 异常处理
- **测试场景：**
  - 文件读取失败时的 `RuntimeError`
  - 预处理过程中任何异常的捕获和封装

---

## 4. 边界条件测试清单

### 4.1 输入边界

| 测试项 | 边界条件 | 预期行为 |
|--------|----------|----------|
| 空文件 | 文件内容为空字符串 | 返回 `endmodule` |
| 空字符串 | 输入空字符串 | 返回 `endmodule` |
| 无模块定义 | 代码中不包含 `module` 关键字 | 返回 `endmodule` |
| 无端口模块 | `module test; endmodule` | 返回模块声明和 `endmodule` |
| 超大文件 | 数十万行的文件 | 正常处理（性能测试） |
| 特殊字符 | 包含 Unicode、特殊符号 | 正确读取和处理 |

### 4.2 宏定义边界

| 测试项 | 边界条件 | 预期行为 |
|--------|----------|----------|
| 空宏定义 | `{}` 或 `[]` | 所有 `ifdef` 失败，`ifndef` 成功 |
| 大量宏 | 100+ 个宏定义 | 正常处理 |
| 宏名特殊字符 | 包含下划线、数字 | 正确匹配 |
| 宏值为空 | `{"MACRO": ""}` | 宏被认为已定义 |

### 4.3 条件编译边界

| 测试项 | 边界条件 | 预期行为 |
|--------|----------|----------|
| 最大嵌套深度 | 10+ 层嵌套 | 正常处理 |
| 无 `endif` | `ifdef` 未闭合 | 处理到文件末尾 |
| 多余 `endif` | `endif` 多于 `ifdef` | 安全忽略（栈为空时） |
| 连续条件块 | 多个 `ifdef` 块相邻 | 独立处理每个块 |
| 空条件块 | `ifdef`/`endif` 之间无内容 | 正常处理 |

### 4.4 端口声明边界

| 测试项 | 边界条件 | 预期行为 |
|--------|----------|----------|
| 无端口 | 模块无端口声明 | 只返回模块声明 |
| 超长声明 | 跨多行的复杂声明 | 完整提取 |
| 混合声明 | input/output/inout/parameter 混合 | 全部提取 |
| 声明后的逻辑 | 端口声明后有 wire、assign 等 | 只提取声明，忽略逻辑 |

---

## 5. 测试用例示例

### 5.1 基本条件编译测试

```python
# 测试用例 1: 简单 ifdef
code = """
module test;
`ifdef ENABLE
  input enable_port;
`endif
  input common_port;
endmodule
"""

preprocessor = VerilogPreprocess({"ENABLE": "1"})
result = preprocessor.preprocess_string(code)
# 验证: result 应包含 enable_port 和 common_port
```

### 5.2 嵌套条件编译测试

```python
# 测试用例 2: 嵌套条件
code = """
module test;
`ifdef LEVEL1
  input port1;
  `ifdef LEVEL2
    input port2;
  `else
    input port3;
  `endif
`endif
endmodule
"""

# 场景 1: 都定义
preprocessor = VerilogPreprocess({"LEVEL1": "1", "LEVEL2": "1"})
result = preprocessor.preprocess_string(code)
# 验证: 包含 port1 和 port2，不含 port3

# 场景 2: 只定义 LEVEL1
preprocessor = VerilogPreprocess({"LEVEL1": "1"})
result = preprocessor.preprocess_string(code)
# 验证: 包含 port1 和 port3，不含 port2
```

### 5.3 elsif 分支测试

```python
# 测试用例 3: elsif 逻辑
code = """
module test;
`ifdef MODE1
  parameter MODE = 1;
`elsif MODE2
  parameter MODE = 2;
`elsif MODE3
  parameter MODE = 3;
`else
  parameter MODE = 0;
`endif
endmodule
"""

# 分别测试定义 MODE1, MODE2, MODE3, 无定义四种情况
```

### 5.4 文件读取测试

```python
# 测试用例 4: 文件读取
preprocessor = VerilogPreprocess()

# 正常情况
result = preprocessor.preprocess_file("valid_file.v")

# 异常情况
try:
    result = preprocessor.preprocess_file("nonexistent.v")
except FileNotFoundError as e:
    # 验证异常消息格式
    assert "Verilog File Missing" in str(e)
```

---

## 6. 验证检查点

### 6.1 功能验证检查点

- [ ] 宏定义的三种初始化格式都能正确解析
- [ ] 宏定义格式错误时能抛出正确的异常
- [ ] 文件不存在时抛出 `FileNotFoundError`
- [ ] UTF-8 和 Latin-1 编码的文件都能正确读取
- [ ] 能正确移除 module 之前的所有内容
- [ ] 能正确识别模块声明（单行和多行）
- [ ] 能正确提取所有端口声明（input/output/inout/parameter）
- [ ] 多行端口声明能完整提取（直到分号）
- [ ] `ifdef` 在宏定义时保留内容，未定义时移除
- [ ] `ifndef` 在宏未定义时保留内容，定义时移除
- [ ] `else` 分支的逻辑正确（与前面条件相反）
- [ ] `elsif` 只在前面条件都不满足时才评估
- [ ] 多个 `elsif` 中只有第一个满足的生效
- [ ] 嵌套条件编译的逻辑正确
- [ ] 条件编译中的注释根据条件正确保留或移除
- [ ] `preprocess_file` 和 `preprocess_string` 输出一致
- [ ] `get_macros` 返回的是副本（修改不影响内部状态）
- [ ] `clear_macros` 能清空所有宏定义

### 6.2 边界条件检查点

- [ ] 空文件/空字符串不会导致崩溃
- [ ] 无 module 的代码能正常处理
- [ ] 未闭合的 `ifdef` 不会导致错误
- [ ] 多余的 `endif` 能安全处理
- [ ] 深层嵌套（10 层以上）能正常工作
- [ ] 超大文件（100MB+）能正常处理
- [ ] 特殊字符（中文、符号等）能正确处理
- [ ] 空的条件块能正常处理
- [ ] 连续的条件块能独立处理

### 6.3 异常处理检查点

- [ ] 所有可预见的异常都被正确捕获
- [ ] 异常消息清晰明确
- [ ] `RuntimeError` 包含原始错误信息

---

## 7. 典型使用场景

### 场景 1: 根据不同配置生成模块接口

```python
# 场景: 同一个 Verilog 模块需要在不同配置下生成不同的接口
preprocessor = VerilogPreprocess(["ENABLE_FEATURE_A", "MODE_32BIT"])
result = preprocessor.preprocess_file("configurable_module.v")
# 结果: 只包含 FEATURE_A 和 32 位模式相关的端口
```

### 场景 2: 批量处理多个文件

```python
# 场景: 处理多个文件，使用相同的宏定义
configs = {"DEBUG": "1", "SIMULATION": "1"}
preprocessor = VerilogPreprocess(configs)

files = ["module1.v", "module2.v", "module3.v"]
results = {}

for file in files:
    results[file] = preprocessor.preprocess_file(file)
```

### 场景 3: 动态切换配置

```python
# 场景: 需要用不同配置处理同一文件
code = "..." # Verilog 代码

# 配置 1
preprocessor = VerilogPreprocess({"MODE_A": "1"})
result_a = preprocessor.preprocess_string(code)

# 配置 2: 重新创建实例
preprocessor = VerilogPreprocess({"MODE_B": "1"})
result_b = preprocessor.preprocess_string(code)
```

---

## 8. 已知限制

1. **不处理宏展开**：如 `` `MACRO_NAME`` 不会被替换为宏的值
2. **不处理 `define` 指令**：文件中的 `` `define`` 不会被解析
3. **注释检测简单**：只检测行首的 `//` 和 `/*`，行内注释可能处理不当
4. **不验证 Verilog 语法**：只做文本处理，不检查语法正确性
5. **只提取声明部分**：模块内部逻辑全部被移除

---

## 9. 测试建议

### 9.1 单元测试策略

1. **宏解析器测试** (`_parse_macros`)：测试所有输入格式和异常情况
2. **文件读取测试** (`read_file`)：测试不同编码和文件状态
3. **内容移除测试** (`remove_pre_module_content`)：测试各种模块前内容
4. **端口提取测试** (`extract_module_ports_section`)：测试各种声明格式
5. **条件编译测试** (`process_conditional_compilation`)：重点测试所有分支组合
6. **集成测试**：测试 `preprocess_file` 和 `preprocess_string`

### 9.2 测试覆盖率目标

- **分支覆盖率**：100%（所有 if/else 分支都被测试）
- **语句覆盖率**：100%
- **条件编译组合**：覆盖所有逻辑组合（ifdef/ifndef/else/elsif）

### 9.3 回归测试

建议建立测试集，包含：
- 真实 Verilog 项目的典型文件
- 各种极端情况的合成案例
- 已发现 bug 的重现案例

---

## 10. 快速参考

### 支持的条件编译指令

| 指令 | 语法 | 说明 |
|------|------|------|
| `ifdef` | `` `ifdef MACRO_NAME`` | 如果宏已定义，包含后续内容 |
| `ifndef` | `` `ifndef MACRO_NAME`` | 如果宏未定义，包含后续内容 |
| `elsif` | `` `elsif MACRO_NAME`` | 前面条件不满足时评估 |
| `else` | `` `else`` | 前面所有条件都不满足时执行 |
| `endif` | `` `endif`` | 结束条件块 |

### 支持的端口声明关键字

- `input`
- `output`
- `inout`
- `parameter`

**注意**：大小写不敏感

---

## 附录：完整测试矩阵

为方便验证，建议按以下矩阵组织测试用例：

| 功能模块 | 测试项 | 优先级 | 测试方法 |
|---------|--------|--------|---------|
| 宏解析 | Dict 输入 | P0 | 单元测试 |
| 宏解析 | List[str] 输入 | P0 | 单元测试 |
| 宏解析 | List[Tuple] 输入 | P0 | 单元测试 |
| 宏解析 | None 输入 | P1 | 单元测试 |
| 宏解析 | 异常处理 | P0 | 单元测试 |
| 文件读取 | UTF-8 编码 | P0 | 集成测试 |
| 文件读取 | Latin-1 编码 | P1 | 集成测试 |
| 文件读取 | 文件不存在 | P0 | 单元测试 |
| 条件编译 | ifdef - 满足 | P0 | 单元测试 |
| 条件编译 | ifdef - 不满足 | P0 | 单元测试 |
| 条件编译 | ifndef - 满足 | P0 | 单元测试 |
| 条件编译 | ifndef - 不满足 | P0 | 单元测试 |
| 条件编译 | else 分支 | P0 | 单元测试 |
| 条件编译 | elsif - 单个 | P0 | 单元测试 |
| 条件编译 | elsif - 多个 | P1 | 单元测试 |
| 条件编译 | 嵌套 - 2 层 | P0 | 单元测试 |
| 条件编译 | 嵌套 - 3+ 层 | P1 | 单元测试 |
| 端口提取 | 单行声明 | P0 | 单元测试 |
| 端口提取 | 多行声明 | P0 | 单元测试 |
| 端口提取 | 混合声明 | P1 | 单元测试 |
| 集成测试 | preprocess_file | P0 | 集成测试 |
| 集成测试 | preprocess_string | P0 | 集成测试 |

**优先级说明：**
- **P0**: 核心功能，必须通过
- **P1**: 重要功能，建议通过
- **P2**: 边界情况，可选
