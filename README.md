# VCG - Verilog Code Generator

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)

🚀 **智能化Verilog代码生成工具** - 通过Python脚本自动化生成复杂的模块实例化、信号连接和线网声明。

## ✨ 核心特性

- 🎯 **嵌入式Python执行** - 在Verilog文件中直接编写Python代码块
- 🔗 **智能信号映射** - 支持通配符模式匹配和复杂的信号转换规则  
- 📡 **自动模块实例化** - 解析模块接口，自动生成标准化实例代码
- 🌐 **灵活线网管理** - 智能生成wire声明，支持lazy/greedy双模式
- 🎨 **强大规则系统** - 优先级规则引擎，支持正则替换和内联函数
- 🔍 **完善调试支持** - 详细的日志系统和错误诊断

## 🚀 快速开始

### 安装依赖

```bash
pip install ply
```

### 基本使用

1. **在Verilog文件中添加VCG代码块：**

```verilog
module uart_top (
    input clk,
    input rst_n,
    output uart_tx
);

//VCG_BEGIN
// # 定义信号连接规则
// Connect("clk", "sys_clk")
// Connect("rst*", "sys_rst_n") 
// Connect("*", "uart_*")
// 
// # 设置模块参数
// ConnectParam("BAUD_RATE", "115200")
// 
// # 生成实例化代码
// Instance("uart_core.v", "uart_core", "u_uart_core")
//VCG_END

endmodule
```

2. **运行VCG处理：**

```bash
python vcg_main.py uart_top.v
```

3. **查看生成的结果：**

```verilog
//VCG_GEN_BEGIN_0
uart_core #(
    .BAUD_RATE          (115200)
) u_uart_core (
    .clk                (sys_clk),           // input
    .rst_n              (sys_rst_n),         // input  
    .uart_tx            (uart_uart_tx),      // output
    .data_in            (uart_data_in),      // input [7:0]
    .valid              (uart_valid)         // input
);
//VCG_GEN_END_0
```

## 🛠️ 高级功能预览

### 智能模式匹配

```python
# 通配符匹配和转换
Connect("*_req", "bus_*_request")
Connect("data_*", "${upper(*)}_BUS") 

# 函数式信号处理
Connect("*_to_*", "${upper(*0)}_TO_${lower(*1)}")
```

### 灵活线网生成

```python
# 自定义线网规则
WiresRule("clk*", "*")                    # 时钟信号保持原名
WiresRule("*_data", "w_*", "32")      # 数据线指定位宽
WiresRule("unused_*", "")                 # 跳过未使用信号

# 批量生成线网声明
WiresDef("memory.v", "mem_ctrl", "input", "lazy")
```

### 条件参数绑定

```python
# 模式化参数设置
ConnectParam("*_WIDTH", "32")
ConnectParam("FIFO_*_DEPTH", "1024")
```

## 📖 完整文档

- 📋 **[详细使用手册](MANUAL.md)** - 完整的功能说明和最佳实践
- 💡 **[示例集合](examples/)** - 丰富的实际应用案例

## 🎯 适用场景

- ✅ 大型SoC设计中的模块互连
- ✅ 总线接口的标准化实例化  
- ✅ 重复性信号连接的自动化
- ✅ 复杂层次化设计的代码维护
- ✅ 设计模板和IP集成

## 🔧 命令行选项

```bash
# 基本使用
python vcg_main.py design.v

# 调试模式 + 详细日志
python vcg_main.py design.v --debug --log-level DEBUG

# 指定宏定义
python vcg_main.py design.v --macros "WIDTH=32,DEPTH=1024"

# 输出日志到文件
python vcg_main.py design.v --log-file vcg.log
```

## 🏗️ 系统要求

- **Python**: 3.6 或更高版本
- **平台**: Linux, macOS, Windows
- **依赖**: PLY (Python Lex-Yacc)

## 🤝 贡献指南

我们欢迎社区贡献！请遵循以下步骤：

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📝 许可证

本项目采用 GNU General Public License v3.0 许可证。详见 [LICENSE](LICENSE) 文件。

## 📬 联系方式

- **作者**: cxhy <cxhy1981@gmail.com>
- **项目主页**: [GitHub Repository](https://github.com/cxhy/vcg)
- **问题报告**: [Issues](https://github.com/cxhy/vcg/issues)

---

⭐ **如果这个项目对您有帮助，请给我们一个Star！**

---

## 🔍 快速导航

| 文档 | 描述 |
|------|------|
| [使用手册](doc/MANUAL.md) | 详细的功能说明和使用指南 |
| [示例代码](examples/) | 实际应用示例 |

---

**VCG - 让Verilog开发更智能、更高效！** 🎉