"""
VerilogAST 模块单元测试
测试平台: pytest
测试范围: SIMPLE端口、VECTOR端口、参数管理、Builder构建流程
"""

import pytest
import sys
import os

# 导入被测模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
from src.VerilogAst import VerilogAST, VerilogASTBuilder, PortInfo, ParameterInfo, PortType,PortDirection, VerilogASTError


#============================================================================
# 第一部分：VerilogASTBuilder 基本功能测试
# ============================================================================

class TestVerilogASTBuilderBasic:
    """测试VerilogASTBuilder的基本功能"""
    
    def test_create_builder(self):
        """测试创建Builder实例"""
        builder = VerilogASTBuilder()
        assert builder is not None
    
    def test_set_module_name(self):
        """测试设置模块名"""
        builder = VerilogASTBuilder()
        result = builder.set_module_name("test_module")
        assert result is builder# 验证链式调用
        ast = builder.build()
        info = ast.get_module_info()
        assert info["name"] == "test_module"
    
    def test_set_module_name_twice_raises_error(self):
        """测试重复设置模块名应抛出异常"""
        builder = VerilogASTBuilder()
        builder.set_module_name("module1")
        
        with pytest.raises(ValueError) as excinfo:
            builder.set_module_name("module2")
        assert "already set" in str(excinfo.value).lower()
    
    def test_build_without_module_name_raises_error(self):
        """测试未设置模块名就build应抛出异常"""
        builder = VerilogASTBuilder()
        builder.add_port("clk", direction="input")
        
        with pytest.raises(VerilogASTError) as excinfo:
            builder.build()
        assert "module name not set" in str(excinfo.value).lower()
    
    def test_build_twice_raises_error(self):
        """测试重复build应抛出异常"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        ast1 = builder.build()
        
        with pytest.raises(VerilogASTError) as excinfo:
            ast2 = builder.build()
        assert "already built" in str(excinfo.value).lower()
    
    def test_reset_and_reuse(self):
        """测试reset后可以重用Builder"""
        builder = VerilogASTBuilder()
        
        # 第一次构建
        builder.set_module_name("module1")
        builder.add_port("clk", direction="input")
        ast1 = builder.build()
        
        # reset
        builder.reset()
        
        # 第二次构建
        builder.set_module_name("module2")
        builder.add_port("rst", direction="input")
        ast2 = builder.build()
        
        # 验证两个AST独立
        info1 = ast1.get_module_info()
        info2 = ast2.get_module_info()
        assert info1["name"] == "module1"
        assert info2["name"] == "module2"
        assert len(ast1.get_port_info()) == 1
        assert len(ast2.get_port_info()) == 1
        assert ast1.get_port_info()[0].name == "clk"
        assert ast2.get_port_info()[0].name == "rst"


# ============================================================================
# 第二部分：SIMPLE端口测试
# ============================================================================

class TestSimplePorts:
    """测试SIMPLE类型端口（单bit端口）"""
    
    def test_basic_input_port(self):
        """测试基本单bit输入端口"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("clk", direction="input")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.name == "clk"
        assert port.port_type == PortType.SIMPLE
        assert port.width == 1
        assert port.range_string == ""
        assert port.is_complete == True
        assert port.direction == "input"
    
    def test_basic_output_port(self):
        """测试基本单bit输出端口"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("valid", direction="output")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.name == "valid"
        assert port.port_type == PortType.SIMPLE
        assert port.direction == "output"
        assert port.width == 1
    
    def test_inout_port(self):
        """测试双向单bit端口"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("sda", direction="inout")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.name == "sda"
        assert port.port_type == PortType.SIMPLE
        assert port.direction == "inout"
    
    def test_port_with_net_type(self):
        """测试带网络类型的单bit端口"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("flag", direction="output", net_type="reg")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.net_type == "reg"
        assert port.port_type == PortType.SIMPLE
    
    def test_incomplete_port(self):
        """测试无方向的端口（不完整）"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("unknown")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.is_complete == False
        assert port.direction is None


# ============================================================================
# 第三部分：VECTOR端口测试
# ============================================================================

class TestVectorPorts:
    """测试VECTOR类型端口（向量端口）"""
    
    def test_standard_vector_descending(self):
        """测试标准向量端口（降序 [7:0]）"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data", direction="input", msb_expr="7", lsb_expr="0")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.port_type == PortType.VECTOR
        assert port.width ==8
        assert port.range_string == "[7:0]"
    def test_standard_vector_ascending(self):
        """测试标准向量端口（升序 [0:7]）"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("addr", direction="input", msb_expr="0", lsb_expr="7")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.port_type == PortType.VECTOR
        assert port.width == 8  # abs(0-7)+1
    
    def test_different_width_vectors(self):
        """测试不同宽度的向量"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data16", direction="input", msb_expr="15", lsb_expr="0")
        builder.add_port("data32", direction="output", msb_expr="31", lsb_expr="0")
        builder.add_port("data64", direction="inout", msb_expr="63", lsb_expr="0")
        ast = builder.build()
        
        ports = ast.get_port_info()
        assert ports[0].width == 16
        assert ports[1].width == 32
        assert ports[2].width == 64
    
    def test_non_zero_start_vector(self):
        """测试非零起始位的向量"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("slice", direction="input", msb_expr="31", lsb_expr="16")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.width == 16
        assert port.range_string == "[31:16]"
    
    def test_vector_with_net_type(self):
        """测试向量端口带网络类型"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("reg_data", direction="output", msb_expr="7", lsb_expr="0", net_type="reg")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.net_type == "reg"
        assert port.port_type == PortType.VECTOR
    
    def test_minimum_width_vector(self):
        """测试最小宽度（1bit向量）"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data", direction="input", msb_expr="0", lsb_expr="0")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.port_type == PortType.VECTOR
        assert port.width == 1
    
    def test_large_width_vectors(self):
        """测试大宽度向量"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data128", direction="input", msb_expr="127", lsb_expr="0")
        builder.add_port("data256", direction="input", msb_expr="255", lsb_expr="0")
        ast = builder.build()
        
        ports = ast.get_port_info()
        assert ports[0].width == 128
        assert ports[1].width == 256


# ============================================================================
# 第四部分：参数表达式测试
# ============================================================================

class TestParameterExpressions:
    """测试参数化表达式的端口"""
    
    def test_simple_parameter_expression_optimization(self):
        """测试简单参数表达式（特殊优化：N-1:0 -> N）"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data", direction="input", msb_expr="N-1", lsb_expr="0")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.width == "N"# 特殊优化
        assert port.range_string == "[N-1:0]"
    
    def test_other_parameter_names(self):
        """测试其他参数名"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data", direction="input", msb_expr="WIDTH-1", lsb_expr="0")
        builder.add_port("addr", direction="input", msb_expr="ADDR_WIDTH-1", lsb_expr="0")
        ast = builder.build()
        
        ports = ast.get_port_info()
        assert ports[0].width == "WIDTH"
        assert ports[1].width == "ADDR_WIDTH"
    
    def test_arithmetic_expression(self):
        """测试算术表达式"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data", direction="input", msb_expr="2*WIDTH-1", lsb_expr="0")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        #宽度可能是 "2*WIDTH" 或计算结果
        assert isinstance(port.width, (str, int))
        assert port.range_string == "[2*WIDTH-1:0]"
    
    def test_compound_parameter_expression(self):
        """测试复合参数表达式"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data", direction="input", msb_expr="WIDTH+HEIGHT-1", lsb_expr="0")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        # 宽度为表达式字符串或计算结果
        assert isinstance(port.width, (str, int))
    
    def test_system_function_expression(self):
        """测试系统函数表达式"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("addr", direction="input", msb_expr="$clog2(DEPTH)-1", lsb_expr="0")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        # 宽度应包含系统函数
        assert isinstance(port.width, str)
        assert port.range_string == "[$clog2(DEPTH)-1:0]"
    
    def test_non_zero_start_parameter_expression(self):
        """测试非零起始的参数表达式"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data", direction="input", msb_expr="WIDTH-1", lsb_expr="4")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        # 宽度为表达式计算结果
        assert isinstance(port.width, (str, int))


# ============================================================================
# 第五部分：参数管理测试
# ============================================================================

class TestParameterManagement:
    """测试参数管理功能"""
    
    def test_add_basic_parameter(self):
        """测试添加基本参数"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_parameter("WIDTH", default_value="8")
        ast = builder.build()
        
        params = ast.get_parameter_info()
        assert len(params) == 1
        assert params[0].name == "WIDTH"
        assert params[0].default_value == "8"
        assert params[0].param_type == "parameter"
    
    def test_add_localparam(self):
        """测试添加localparam"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_parameter("DEPTH", param_type="localparam", default_value="1024")
        ast = builder.build()
        
        param = ast.get_parameter_info()[0]
        assert param.param_type == "localparam"
        assert param.default_value == "1024"
    
    def test_multiple_parameters_order(self):
        """测试多个参数顺序"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_parameter("WIDTH", default_value="8")
        builder.add_parameter("HEIGHT", default_value="16")
        builder.add_parameter("DEPTH", default_value="32")
        ast = builder.build()
        
        params = ast.get_parameter_info()
        assert len(params) == 3
        assert params[0].name == "WIDTH"
        assert params[1].name == "HEIGHT"
        assert params[2].name == "DEPTH"
    
    def test_duplicate_parameter_overwrite(self):
        """测试重复添加参数（覆盖行为）"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_parameter("WIDTH", default_value="8")
        builder.add_parameter("WIDTH", default_value="16")
        ast = builder.build()
        
        params = ast.get_parameter_info()
        assert len(params) == 1
        assert params[0].default_value == "16"


# ============================================================================
# 第六部分：端口方向和网络类型测试
# ============================================================================

class TestPortDirectionAndNetType:
    """测试端口方向和网络类型"""
    
    def test_all_directions_coverage(self):
        """测试三种方向全覆盖"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("in_port", direction="input")
        builder.add_port("out_port", direction="output")
        builder.add_port("inout_port", direction="inout")
        ast = builder.build()
        
        summary = ast.get_module_info()["port_summary"]
        assert summary["input"] == 1
        assert summary["output"] == 1
        assert summary["inout"] == 1
        assert summary["total"] == 3
    
    def test_case_insensitive_directions(self):
        """测试大小写不敏感"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("port1", direction="INPUT")
        builder.add_port("port2", direction="Output")
        builder.add_port("port3", direction="InOut")
        ast = builder.build()
        
        summary = ast.get_module_info()["port_summary"]
        # 验证统计时正确识别（内部转小写）
        assert summary["input"] == 1
        assert summary["output"] == 1
        assert summary["inout"] == 1
    
    def test_default_net_type(self):
        """测试默认网络类型"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data", direction="input", msb_expr="7", lsb_expr="0")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.net_type == "wire"  # 默认值
    
    def test_explicit_wire_type(self):
        """测试显式指定wire"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data", direction="input", net_type="wire")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.net_type == "wire"
    
    def test_reg_type(self):
        """测试指定reg"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data", direction="output", net_type="reg")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.net_type == "reg"
    
    def test_custom_net_type(self):
        """测试用户自定义类型"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data", direction="output", net_type="logic")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.net_type == "logic"


# ============================================================================
# 第七部分：多次更新测试
# ============================================================================

class TestMultipleUpdates:
    """测试端口的多次更新功能"""
    
    def test_step_by_step_simple_port(self):
        """测试分步构建单bit端口"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("clk")
        builder.update_port("clk", direction="input")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.name == "clk"
        assert port.direction == "input"
        assert port.is_complete == True
    
    def test_step_by_step_vector_port(self):
        """测试分步构建向量端口"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data")
        builder.update_port("data", direction="output")
        builder.update_port("data", msb_expr="7", lsb_expr="0")
        builder.update_port("data", net_type="reg")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.port_type == PortType.VECTOR
        assert port.direction == "output"
        assert port.width == 8
        assert port.net_type == "reg"
    
    def test_partial_update_no_overwrite(self):
        """测试部分更新不覆盖已有属性"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data", direction="input", msb_expr="7")
        builder.update_port("data", lsb_expr="0")  # 不影响direction和msb_expr
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.direction == "input"
        assert port.msb_expr == "7"
        assert port.lsb_expr == "0"
    
    def test_none_value_not_overwrite(self):
        """测试None值不覆盖"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data", direction="input", msb_expr="7", lsb_expr="0")
        builder.update_port("data", msb_expr=None)  # None不应覆盖
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.msb_expr == "7"  # 未被覆盖


# ============================================================================
# 第八部分：边界条件测试
# ============================================================================

class TestBoundaryConditions:
    """测试边界条件"""
    
    def test_empty_module(self):
        """测试零端口模块"""
        builder = VerilogASTBuilder()
        builder.set_module_name("empty_module")
        ast = builder.build()
        
        ports = ast.get_port_info()
        summary = ast.get_module_info()["port_summary"]
        assert len(ports) == 0
        assert summary["total"] == 0
    
    def test_large_number_of_ports(self):
        """测试大量端口"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        
        for i in range(100):
            builder.add_port(f"port{i}", direction="input")
        
        ast = builder.build()
        ports = ast.get_port_info()
        assert len(ports) == 100# 验证顺序
        for i in range(100):
            assert ports[i].name == f"port{i}"
    
    def test_empty_string_expressions(self):
        """测试空字符串表达式"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data", direction="input", msb_expr="", lsb_expr="")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.port_type == PortType.SIMPLE# 空表达式视为无表达式
        assert port.width == 1
    
    def test_only_msb_no_lsb(self):
        """测试只有msb无lsb"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data", direction="input", msb_expr="7")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.port_type == PortType.SIMPLE  # 缺少lsb
        assert port.width == 1
    
    def test_only_lsb_no_msb(self):
        """测试只有lsb无msb"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data", direction="input", lsb_expr="0")
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.port_type == PortType.SIMPLE
        assert port.width == 1
    
    def test_port_order_preservation(self):
        """测试端口添加顺序保持"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("port1", direction="input")
        builder.add_port("port2", direction="output")
        builder.add_port("port3", direction="inout")
        builder.add_port("port4", direction="input")
        ast = builder.build()
        
        ports = ast.get_port_info()
        assert ports[0].name == "port1"
        assert ports[1].name == "port2"
        assert ports[2].name == "port3"
        assert ports[3].name == "port4"
    
    def test_duplicate_port_overwrite_keep_order(self):
        """测试重复添加端口覆盖但保持顺序"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("port1", direction="input")
        builder.add_port("port2", direction="output")
        builder.add_port("port1", direction="inout")  # 覆盖
        ast = builder.build()
        
        ports = ast.get_port_info()
        assert len(ports) == 2
        assert ports[0].name == "port1"# 顺序不变
        assert ports[0].direction == "inout"  # 内容更新
        assert ports[1].name == "port2"


# ============================================================================
# 第九部分：集成测试
# ============================================================================

class TestIntegration:
    """集成测试用例"""
    
    def test_verilog95_style_module(self):
        """测试Verilog-95风格模块"""
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
        ports = ast.get_port_info()
        
        # 验证：4个端口全部完整
        assert len(ports) == 4
        assert all(p.is_complete for p in ports)
        
        # 验证顺序
        assert ports[0].name == "clk"
        assert ports[1].name == "rst"
        assert ports[2].name == "enable"
        assert ports[3].name == "count"
        
        # 验证count为8bit输出寄存器
        assert ports[3].port_type == PortType.VECTOR
        assert ports[3].width == 8
        assert ports[3].net_type == "reg"
    
    def test_verilog2001_style_module(self):
        """测试Verilog-2001风格模块"""
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
        ports = ast.get_port_info()
        
        # 验证所有端口一次性完整
        assert len(ports) == 6
        assert all(p.is_complete for p in ports)
        
        # 验证a, b为8bit输入
        assert ports[2].width == 8
        assert ports[3].width == 8
        
        # 验证sum为9bit输出
        assert ports[4].width == 9
        
        # 验证carry为1bit输出
        assert ports[5].width == 1
    
    def test_complex_parameterized_module(self):
        """测试带参数的复杂模块"""
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
        
        # 验证模块信息
        assert info["name"] == "fifo"
        assert len(info["parameters"]) == 3
        assert len(info["ports"]) == 8
        
        # 验证端口统计
        summary = info["port_summary"]
        assert summary["total"] == 8
        assert summary["input"] == 5
        assert summary["output"] == 3
        
        # 验证参数化端口宽度
        ports = ast.get_port_info()
        assert ports[4].width == "DATA_WIDTH"
        assert ports[5].width == "DATA_WIDTH"
    
    def test_mixed_style_module(self):
        """测试混合风格模块"""
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
        ports = ast.get_port_info()
        
        # 验证所有端口最终完整
        assert len(ports) == 4
        assert all(p.is_complete for p in ports)
        
        # 验证顺序：clk, rst, data_in, data_out
        assert ports[0].name == "clk"
        assert ports[1].name == "rst"
        assert ports[2].name == "data_in"
        assert ports[3].name == "data_out"


# ============================================================================
# 第十部分：表达式计算专项测试
# ============================================================================

class TestExpressionCalculation:
    """表达式计算专项测试"""
    
    @pytest.mark.parametrize("msb,lsb,expected_width", [
        ("7", "0", 8),
        ("15", "0", 16),
        ("31", "0", 32),
        ("63", "0", 64),
        ("0", "7", 8),  # 反向范围
        ("31", "16", 16),  # 非零起始
        ("0", "0", 1),  # 单bit向量
        ("10", "5", 6),  # 任意范围
    ])
    def test_constant_expressions(self, msb, lsb, expected_width):
        """测试常量表达式计算"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data", direction="input", msb_expr=msb, lsb_expr=lsb)
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.width == expected_width
    
    @pytest.mark.parametrize("msb,lsb,expected_width", [
        ("N-1", "0", "N"),
        ("WIDTH-1", "0", "WIDTH"),
        ("DATA_WIDTH-1", "0", "DATA_WIDTH"),
    ])
    def test_parameter_expression_optimization(self, msb, lsb, expected_width):
        """测试参数表达式特殊优化"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("data", direction="input", msb_expr=msb, lsb_expr=lsb)
        ast = builder.build()
        
        port = ast.get_port_info()[0]
        assert port.width == expected_width
    
    def test_complex_arithmetic_expressions(self):
        """测试复杂算术表达式"""
        test_cases = [
            ("2*N-1", "0"),
            ("N+M-1", "0"),
            ("$clog2(DEPTH)-1", "0"),
        ]
        
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        
        for i, (msb, lsb) in enumerate(test_cases):
            builder.add_port(f"port{i}", direction="input", msb_expr=msb, lsb_expr=lsb)
        
        ast = builder.build()
        ports = ast.get_port_info()
        
        # 验证宽度为字符串或计算结果
        for port in ports:
            assert isinstance(port.width, (str, int))


# ============================================================================
# 第十一部分：VerilogAST类测试
# ============================================================================

class TestVerilogAST:
    """测试VerilogAST类的方法"""
    
    def test_get_port_info(self):
        """测试get_port_info方法"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_port("clk", direction="input")
        builder.add_port("data", direction="output", msb_expr="7", lsb_expr="0")
        ast = builder.build()
        
        ports = ast.get_port_info()
        assert isinstance(ports, list)
        assert len(ports) == 2
        assert all(isinstance(p, PortInfo) for p in ports)
    def test_get_parameter_info(self):
        """测试get_parameter_info方法"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        builder.add_parameter("WIDTH", default_value="8")
        builder.add_parameter("DEPTH", default_value="16")
        ast = builder.build()
        
        params = ast.get_parameter_info()
        assert isinstance(params, list)
        assert len(params) == 2
        assert all(isinstance(p, ParameterInfo) for p in params)
    
    def test_get_module_info(self):
        """测试get_module_info方法"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test_module")
        builder.add_parameter("WIDTH", default_value="8")
        builder.add_port("clk", direction="input")
        builder.add_port("data", direction="output", msb_expr="7", lsb_expr="0")
        ast = builder.build()
        
        info = ast.get_module_info()
        
        # 验证返回字典结构
        assert isinstance(info, dict)
        assert "name" in info
        assert "parameters" in info
        assert "ports" in info
        assert "port_summary" in info
        # 验证内容
        assert info["name"] == "test_module"
        assert len(info["parameters"]) == 1
        assert len(info["ports"]) == 2
        
        # 验证port_summary
        summary = info["port_summary"]
        assert summary["total"] == 2
        assert summary["input"] == 1
        assert summary["output"] == 1
        assert summary["inout"] == 0
    
    def test_port_summary_statistics(self):
        """测试端口统计信息"""
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        
        # 添加各种方向的端口
        builder.add_port("in1", direction="input")
        builder.add_port("in2", direction="input")
        builder.add_port("out1", direction="output")
        builder.add_port("out2", direction="output")
        builder.add_port("out3", direction="output")
        builder.add_port("io1", direction="inout")
        builder.add_port("incomplete")# 无方向
        
        ast = builder.build()
        summary = ast.get_module_info()["port_summary"]
        
        assert summary["total"] == 7
        assert summary["input"] == 2
        assert summary["output"] == 3
        assert summary["inout"] == 1


# ============================================================================
# 第十二部分：综合场景测试
# ============================================================================

class TestComprehensiveScenarios:
    """综合场景测试"""
    
    def test_complete_module_example(self):
        """测试完整模块示例（文档第9.1节）"""
        # 1. 创建Builder
        builder = VerilogASTBuilder()
        
        # 2. 设置模块名
        builder.set_module_name("test_module")
        
        # 3. 添加参数
        builder.add_parameter("DATA_WIDTH", default_value="8")
        
        # 4. 添加SIMPLE端口
        builder.add_port("clk", direction="input")
        builder.add_port("rst_n", direction="input")
        
        # 5. 添加VECTOR端口
        builder.add_port("data_in", direction="input", msb_expr="DATA_WIDTH-1", lsb_expr="0")
        builder.add_port("data_out", direction="output", msb_expr="7", lsb_expr="0", net_type="reg")
        
        # 6. 构建AST
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
    
    def test_all_exceptions(self):
        """测试所有异常情况（文档第9.2节）"""
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
        
        # 测试重复build
        builder = VerilogASTBuilder()
        builder.set_module_name("test")
        ast1 = builder.build()
        try:
            ast2 = builder.build()
            assert False, "Should raise VerilogASTError"
        except VerilogASTError:
            pass  # 正确


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])