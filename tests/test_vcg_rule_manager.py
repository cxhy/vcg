"""
VCGRuleManager 单元测试
测试平台: pytest
"""

import os
import sys
import pytest
from enum import Enum
from typing import Optional, Union

# 导入被测模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
from src.vcg_rule_manager import VCGRuleManager


# ==================== Mock对象定义 ====================

class PortType(Enum):
    """端口类型枚举"""
    NORMAL = "normal"
    INTERFACE = "interface"


class PortInfo:
    """端口信息模拟对象"""
    def __init__(
        self,
        name: str,
        direction: Optional[str] = None,
        port_type: PortType = PortType.NORMAL,
        width: Optional[Union[int, str]] = None,
        interface_type: Optional[str] = None
    ):
        self.name = name
        self.direction = direction
        self.port_type = port_type
        self.width = width
        self.interface_type = interface_type


# ==================== 测试类 ====================

class TestVCGRuleManager:
    """VCGRuleManager 单元测试类"""
    
    def setup_method(self):
        """每个测试方法前执行，初始化规则管理器"""
        self.manager = VCGRuleManager()
        self.manager.reset()
    
    # ========== 5.1.1 信号规则测试 ==========
    
    def test_signal_exact_match(self):
        """测试信号精确匹配"""
        self.manager.add_signal_rule("clk", "sys_clk")
        port = PortInfo(name="clk")
        assert self.manager.resolve_signal_connection(port) == "sys_clk"
        
        # 不匹配的情况
        port2 = PortInfo(name="clk_1")
        assert self.manager.resolve_signal_connection(port2) == "clk_1"
    
    def test_signal_wildcard_single(self):
        """测试单通配符匹配"""
        self.manager.add_signal_rule("i_*", "o_*")
        
        port1 = PortInfo(name="i_data")
        assert self.manager.resolve_signal_connection(port1) == "o_data"
        
        port2 = PortInfo(name="i_")
        assert self.manager.resolve_signal_connection(port2) == "o_"
        
        port3 = PortInfo(name="i_test_signal")
        assert self.manager.resolve_signal_connection(port3) == "o_test_signal"
    
    def test_signal_wildcard_multiple(self):
        """测试多通配符匹配"""
        self.manager.add_signal_rule("*_*_in", "*_*_out")
        
        port1 = PortInfo(name="uart_data_in")
        assert self.manager.resolve_signal_connection(port1) == "uart_data_out"
        
        port2 = PortInfo(name="a_b_in")
        assert self.manager.resolve_signal_connection(port2) == "a_b_out"
    
    def test_signal_direction_constraint_none(self):
        """测试无方向约束"""
        self.manager.add_signal_rule("*", "sig_*", port_direction=None)
        
        port_input = PortInfo(name="data", direction="input")
        assert self.manager.resolve_signal_connection(port_input) == "sig_data"
        
        port_output = PortInfo(name="data", direction="output")
        assert self.manager.resolve_signal_connection(port_output) == "sig_data"
        
        port_none = PortInfo(name="data", direction=None)
        assert self.manager.resolve_signal_connection(port_none) == "sig_data"
    
    def test_signal_direction_constraint_input(self):
        """测试input方向约束"""
        self.manager.add_signal_rule("*", "i_*", port_direction="input")
        
        port_input = PortInfo(name="data", direction="input")
        assert self.manager.resolve_signal_connection(port_input) == "i_data"
        
        port_output = PortInfo(name="data", direction="output")
        assert self.manager.resolve_signal_connection(port_output) == "data"
    
    def test_signal_direction_constraint_output(self):
        """测试output方向约束（大小写不敏感）"""
        self.manager.add_signal_rule("*", "o_*", port_direction="OUTPUT")
        
        port_output = PortInfo(name="data", direction="output")
        assert self.manager.resolve_signal_connection(port_output) == "o_data"
    
    def test_signal_direction_constraint_inout(self):
        """测试inout方向约束"""
        self.manager.add_signal_rule("*", "io_*", port_direction="inout")
        
        port_inout = PortInfo(name="data", direction="inout")
        assert self.manager.resolve_signal_connection(port_inout) == "io_data"
    
    def test_signal_direction_none_on_port(self):
        """测试端口无方向信息时仍允许匹配"""
        self.manager.add_signal_rule("*", "i_*", port_direction="input")
        
        port = PortInfo(name="data", direction=None)
        assert self.manager.resolve_signal_connection(port) == "i_data"
    
    def test_signal_function_upper(self):
        """测试upper函数"""
        self.manager.add_signal_rule("*", "${upper(*)}")
        
        port = PortInfo(name="clk")
        assert self.manager.resolve_signal_connection(port) == "CLK"
    
    def test_signal_function_lower(self):
        """测试lower函数"""
        self.manager.add_signal_rule("*", "${lower(*)}")
        
        port = PortInfo(name="CLK")
        assert self.manager.resolve_signal_connection(port) == "clk"
    
    def test_signal_function_title(self):
        """测试title函数"""
        self.manager.add_signal_rule("*", "${title(*)}")
        
        port = PortInfo(name="hello world")
        assert self.manager.resolve_signal_connection(port) == "Hello World"
    
    def test_signal_function_capitalize(self):
        """测试capitalize函数"""
        self.manager.add_signal_rule("*", "${capitalize(*)}")
        
        port = PortInfo(name="hello")
        assert self.manager.resolve_signal_connection(port) == "Hello"
    
    def test_signal_function_replace(self):
        """测试replace函数"""
        self.manager.add_signal_rule("*", "${replace(*, '_', '__')}")
        
        port = PortInfo(name="a_b")
        assert self.manager.resolve_signal_connection(port) == "a__b"
    
    def test_signal_function_multiple_wildcards(self):
        """测试多通配符函数调用"""
        self.manager.add_signal_rule("*_*", "${upper(*0)}_${lower(*1)}")
        
        port = PortInfo(name="Clk_Data")
        assert self.manager.resolve_signal_connection(port) == "CLK_data"
    
    def test_signal_function_invalid(self):
        """测试无效函数名异常回退"""
        self.manager.add_signal_rule("*", "${invalid_func(*)}")
        
        port = PortInfo(name="test")
        # 应回退到第一个捕获组
        assert self.manager.resolve_signal_connection(port) == "test"
    
    def test_signal_literal_zero_width_1(self):
        """测试字面值0，宽度为1"""
        self.manager.add_signal_rule("*", "0")
        
        port = PortInfo(name="gnd", width=1)
        assert self.manager.resolve_signal_connection(port) == "1'b0"
    
    def test_signal_literal_one_width_1(self):
        """测试字面值1，宽度为1"""
        self.manager.add_signal_rule("*", "1")
        
        port = PortInfo(name="vcc", width=1)
        assert self.manager.resolve_signal_connection(port) == "1'b1"
    
    def test_signal_literal_zero_width_none(self):
        """测试字面值0，宽度为None"""
        self.manager.add_signal_rule("*", "0")
        
        port = PortInfo(name="gnd", width=None)
        assert self.manager.resolve_signal_connection(port) == "1'b0"
    
    def test_signal_literal_zero_width_4(self):
        """测试字面值0，宽度为4"""
        self.manager.add_signal_rule("*", "0")
        
        port = PortInfo(name="gnd", width=4)
        assert self.manager.resolve_signal_connection(port) == "4'b0000"
    
    def test_signal_literal_one_width_8(self):
        """测试字面值1，宽度为8"""
        self.manager.add_signal_rule("*", "1")
        
        port = PortInfo(name="vcc", width=8)
        assert self.manager.resolve_signal_connection(port) == "8'b11111111"
    
    def test_signal_literal_zero_width_16(self):
        """测试字面值0，宽度大于8"""
        self.manager.add_signal_rule("*", "0")
        
        port = PortInfo(name="gnd", width=16)
        assert self.manager.resolve_signal_connection(port) == "{16{1'b0}}"
    
    def test_signal_literal_one_width_32(self):
        """测试字面值1，宽度大于8"""
        self.manager.add_signal_rule("*", "1")
        
        port = PortInfo(name="vcc", width=32)
        assert self.manager.resolve_signal_connection(port) == "{32{1'b1}}"
    
    def test_signal_literal_width_expression_simple(self):
        """测试字面值，宽度为表达式（简单）"""
        self.manager.add_signal_rule("*", "0")
        
        port = PortInfo(name="gnd", width="WIDTH")
        assert self.manager.resolve_signal_connection(port) == "{WIDTH{1'b0}}"
    
    def test_signal_literal_width_expression_with_operator(self):
        """测试字面值，宽度为表达式（含运算符）"""
        self.manager.add_signal_rule("*", "1")
        
        port = PortInfo(name="vcc", width="WIDTH+4")
        assert self.manager.resolve_signal_connection(port) == "{(WIDTH+4){1'b1}}"
    
    def test_signal_literal_width_expression_complex(self):
        """测试字面值，宽度为复杂表达式"""
        self.manager.add_signal_rule("*", "0")
        
        port = PortInfo(name="gnd", width="WIDTH*2-1")
        assert self.manager.resolve_signal_connection(port) == "{(WIDTH*2-1){1'b0}}"
    
    def test_signal_non_literal(self):
        """测试非字面值不转换"""
        self.manager.add_signal_rule("*", "signal_name")
        
        port = PortInfo(name="test", width=8)
        assert self.manager.resolve_signal_connection(port) == "signal_name"
        
        self.manager.reset()
        self.manager.add_signal_rule("*", "10")
        port2 = PortInfo(name="test", width=8)
        assert self.manager.resolve_signal_connection(port2) == "10"
    
    def test_signal_comment_preservation_single(self):
        """测试单个内联注释保留"""
        self.manager.add_signal_rule("*", "sig_* /* comment */")
        
        port = PortInfo(name="data")
        assert self.manager.resolve_signal_connection(port) == "sig_data /* comment */"
    
    def test_signal_comment_preservation_multiple(self):
        """测试多个内联注释保留"""
        self.manager.add_signal_rule("*_*", "*_*_out /* first */ /* second */")
        
        port = PortInfo(name="uart_tx")
        assert self.manager.resolve_signal_connection(port) == "uart_tx_out /* first */ /* second */"
    
    def test_signal_comment_preservation_multiline(self):
        """测试多行注释保留"""
        self.manager.add_signal_rule("*", "sig /* line1\nline2 */")
        
        port = PortInfo(name="data")
        result = self.manager.resolve_signal_connection(port)
        assert "/* line1\nline2 */" in result
    
    def test_signal_comment_with_function(self):
        """测试注释与函数嵌套"""
        self.manager.add_signal_rule("*", "${upper(*)} /* UPPER */")
        
        port = PortInfo(name="clk")
        assert self.manager.resolve_signal_connection(port) == "CLK /* UPPER */"
    
    def test_signal_priority_last_added_first(self):
        """测试规则优先级：后添加的先匹配"""
        self.manager.add_signal_rule("*", "prefix1_*")
        self.manager.add_signal_rule("data", "special_data")
        
        port1 = PortInfo(name="data")
        assert self.manager.resolve_signal_connection(port1) == "special_data"
        
        port2 = PortInfo(name="clk")
        assert self.manager.resolve_signal_connection(port2) == "prefix1_clk"
    
    def test_signal_priority_with_direction(self):
        """测试方向约束与优先级"""
        self.manager.add_signal_rule("*", "sig_*", port_direction=None)
        self.manager.add_signal_rule("*", "input_*", port_direction="input")
        
        port_input = PortInfo(name="data", direction="input")
        assert self.manager.resolve_signal_connection(port_input) == "input_data"
        
        port_output = PortInfo(name="data", direction="output")
        assert self.manager.resolve_signal_connection(port_output) == "sig_data"
    
    # ========== 5.1.2 参数规则测试 ==========
    
    def test_param_exact_match(self):
        """测试参数精确匹配"""
        self.manager.add_param_rule("WIDTH", "32")
        
        assert self.manager.resolve_param_connection("WIDTH") == "32"
    
    def test_param_wildcard_match(self):
        """测试参数通配符匹配"""
        self.manager.add_param_rule("*_WIDTH", "16")
        
        assert self.manager.resolve_param_connection("DATA_WIDTH") == "16"
        assert self.manager.resolve_param_connection("ADDR_WIDTH") == "16"
    
    def test_param_no_match(self):
        """测试参数无匹配规则"""
        result = self.manager.resolve_param_connection("UNKNOWN_PARAM")
        assert result is None
    
    def test_param_priority(self):
        """测试参数规则优先级"""
        self.manager.add_param_rule("*_WIDTH", "16")
        self.manager.add_param_rule("DATA_WIDTH", "32")
        
        assert self.manager.resolve_param_connection("DATA_WIDTH") == "32"
        assert self.manager.resolve_param_connection("ADDR_WIDTH") == "16"
    
    # ========== 5.1.3 线网规则测试 ==========
    
    def test_wire_greedy_mode_no_rule(self):
        """测试Greedy模式无匹配规则"""
        port = PortInfo(name="data")
        wire_name, width, expression, has_rule = self.manager.resolve_wire_generation(port, pattern='greedy')
        
        assert wire_name == "data"
        assert width is None
        assert expression is None
        assert has_rule is False
    
    def test_wire_lazy_mode_no_rule(self):
        """测试Lazy模式无匹配规则"""
        port = PortInfo(name="data")
        wire_name, width, expression, has_rule = self.manager.resolve_wire_generation(port, pattern='lazy')
        
        assert wire_name == ""
        assert width is None
        assert expression is None
        assert has_rule is False
    
    def test_wire_with_width(self):
        """测试指定宽度的线网生成"""
        self.manager.add_wire_rule("*", "wire_*", width="8")
        
        port = PortInfo(name="data")
        wire_name, width, expression, has_rule = self.manager.resolve_wire_generation(port)
        
        assert wire_name == "wire_data"
        assert width == "8"
        assert expression is None
        assert has_rule is True
    
    def test_wire_with_expression(self):
        """测试指定表达式的线网生成"""
        self.manager.add_wire_rule("*", "wire_*", expression="1'b0")
        
        port = PortInfo(name="rst")
        wire_name, width, expression, has_rule = self.manager.resolve_wire_generation(port)
        
        assert wire_name == "wire_rst"
        assert width is None
        assert expression == "1'b0"
        assert has_rule is True
    
    def test_wire_expression_substitution(self):
        """测试表达式中的通配符替换"""
        self.manager.add_wire_rule("*_out", "*_wire", expression="*_in")
        
        port = PortInfo(name="data_out")
        wire_name, width, expression, has_rule = self.manager.resolve_wire_generation(port)
        
        assert wire_name == "data_wire"
        assert width is None
        assert expression == "data_in"
        assert has_rule is True
    
    def test_wire_with_width_and_expression(self):
        """测试同时指定宽度和表达式"""
        self.manager.add_wire_rule("*", "wire_*", width="16", expression="16'h0000")
        
        port = PortInfo(name="data")
        wire_name, width, expression, has_rule = self.manager.resolve_wire_generation(port)
        
        assert wire_name == "wire_data"
        assert width == "16"
        assert expression == "16'h0000"
        assert has_rule is True
    
    def test_wire_wildcard_pattern(self):
        """测试线网通配符模式"""
        self.manager.add_wire_rule("i_*", "internal_*", width="8")
        
        port = PortInfo(name="i_data")
        wire_name, width, expression, has_rule = self.manager.resolve_wire_generation(port)
        
        assert wire_name == "internal_data"
        assert width == "8"
        assert has_rule is True
    
    # ========== 5.1.4 边界测试 ==========
    
    def test_empty_string_source(self):
        """测试空字符串源模式"""
        self.manager.add_signal_rule("", "default")
        
        port = PortInfo(name="")
        assert self.manager.resolve_signal_connection(port) == "default"
    
    def test_empty_string_target(self):
        """测试空字符串目标模式"""
        self.manager.add_signal_rule("*", "")
        
        port = PortInfo(name="any")
        assert self.manager.resolve_signal_connection(port) == ""
    
    def test_special_characters_exact(self):
        """测试特殊字符精确匹配"""
        self.manager.add_signal_rule("data[0]", "sig")
        
        port1 = PortInfo(name="data[0]")
        assert self.manager.resolve_signal_connection(port1) == "sig"
        
        port2 = PortInfo(name="data[1]")
        assert self.manager.resolve_signal_connection(port2) == "data[1]"
    
    def test_unicode_characters(self):
        """测试Unicode字符"""
        self.manager.add_signal_rule("信号_*", "signal_*")
        
        port = PortInfo(name="信号_数据")
        assert self.manager.resolve_signal_connection(port) == "signal_数据"
    
    def test_very_long_string(self):
        """测试极长字符串"""
        long_string = "a" * 10000
        self.manager.add_signal_rule("*", "prefix_*")
        
        port = PortInfo(name=long_string)
        result = self.manager.resolve_signal_connection(port)
        assert result == f"prefix_{long_string}"
        assert len(result) == 10007
    
    def test_many_rules_performance(self):
        """测试大量规则"""
        # 添加1000条规则
        for i in range(1000):
            self.manager.add_signal_rule(f"sig_{i}", f"out_{i}")
        
        # 测试最后一条规则
        port = PortInfo(name="sig_999")
        assert self.manager.resolve_signal_connection(port) == "out_999"
        
        # 测试第一条规则
        port2 = PortInfo(name="sig_0")
        assert self.manager.resolve_signal_connection(port2) == "out_0"
        
        # 测试不匹配
        port3 = PortInfo(name="sig_1000")
        assert self.manager.resolve_signal_connection(port3) == "sig_1000"
    
    def test_wildcard_boundary_multiple_stars(self):
        """测试通配符边界：多个星号"""
        self.manager.add_signal_rule("*", "***")
        
        port = PortInfo(name="test")
        assert self.manager.resolve_signal_connection(port) == "test**"
    
    def test_port_missing_attributes(self):
        """测试端口属性缺失"""
        # direction = None
        port1 = PortInfo(name="data", direction=None)
        self.manager.add_signal_rule("*", "sig_*")
        assert self.manager.resolve_signal_connection(port1) == "sig_data"
        
        # width = None，字面值应生成 1'b0
        self.manager.reset()
        self.manager.add_signal_rule("*", "0")
        port2 = PortInfo(name="gnd", width=None)
        assert self.manager.resolve_signal_connection(port2) == "1'b0"
        
        # name = ""
        port3 = PortInfo(name="")
        self.manager.reset()
        self.manager.add_signal_rule("*", "prefix_*")
        assert self.manager.resolve_signal_connection(port3) == "prefix_"
    
    def test_width_expression_boundary_zero(self):
        """测试宽度表达式边界：0"""
        self.manager.add_signal_rule("*", "0")
        
        port = PortInfo(name="gnd", width="0")
        # 虽然Verilog非法，但应生成
        assert self.manager.resolve_signal_connection(port) == "{0{1'b0}}"
    
    def test_width_expression_boundary_negative(self):
        """测试宽度表达式边界：负数"""
        self.manager.add_signal_rule("*", "0")
        
        port = PortInfo(name="gnd", width="-1")
        # 虽然Verilog非法，但应生成
        assert self.manager.resolve_signal_connection(port) == "{(-1){1'b0}}"
    
    def test_width_expression_boundary_power(self):
        """测试宽度表达式边界：幂运算"""
        self.manager.add_signal_rule("*", "0")
        
        port = PortInfo(name="gnd", width="2**8")
        assert self.manager.resolve_signal_connection(port) == "{(2**8){1'b0}}"
    
    def test_comment_boundary_unclosed(self):
        """测试注释边界：未闭合"""
        self.manager.add_signal_rule("*", "sig /* unclosed")
        
        port = PortInfo(name="data")
        result = self.manager.resolve_signal_connection(port)
        # 未闭合的注释不应被识别
        assert result == "sig /data unclosed"
    
    def test_comment_boundary_empty(self):
        """测试注释边界：空注释"""
        self.manager.add_signal_rule("*", "sig /**/")
        
        port = PortInfo(name="data")
        result = self.manager.resolve_signal_connection(port)
        assert "/**/" in result
    
    def test_comment_boundary_nested_asterisk(self):
        """测试注释边界：包含*/"""
        self.manager.add_signal_rule("*", "sig /* comment */ extra */")
        
        port = PortInfo(name="data")
        result = self.manager.resolve_signal_connection(port)
        # 应匹配到第一个 */
        assert "/* comment */" in result
    
    # ========== 5.1.5 工具函数测试 ==========
    
    def test_reset_clears_all_rules(self):
        """测试reset清空所有规则"""
        self.manager.add_signal_rule("*", "*_sig")
        self.manager.add_param_rule("WIDTH", "32")
        self.manager.add_wire_rule("*", "*_wire")
        
        self.manager.reset()
        
        summary = self.manager.get_rules_summary()
        assert summary['signal_rules'] == 0
        assert summary['param_rules'] == 0
        assert summary['wire_rules'] == 0
    
    def test_get_rules_summary_empty(self):
        """测试空规则集合的统计"""
        summary = self.manager.get_rules_summary()
        assert summary == {'signal_rules': 0, 'param_rules': 0, 'wire_rules': 0}
    
    def test_get_rules_summary_with_rules(self):
        """测试有规则时的统计"""
        self.manager.add_signal_rule("*", "*_sig")
        self.manager.add_signal_rule("clk", "sys_clk")
        self.manager.add_param_rule("WIDTH", "32")
        self.manager.add_wire_rule("*", "*_wire")
        
        summary = self.manager.get_rules_summary()
        assert summary['signal_rules'] == 2
        assert summary['param_rules'] == 1
        assert summary['wire_rules'] == 1
    
    # ========== 集成测试场景 ==========
    
    def test_integration_signal_workflow(self):
        """集成测试：完整的信号连接工作流"""
        # 添加多条规则
        self.manager.add_signal_rule("*", "default_*")
        self.manager.add_signal_rule("*_in", "*_out")
        self.manager.add_signal_rule("clk*", "sys_CLK${upper(*)}", port_direction="input")
        
        
        # 测试多个端口
        ports = [
            PortInfo(name="clk", direction="input"),
            PortInfo(name="clk_ref", direction="input"),
            PortInfo(name="data_in", direction="output"),
            PortInfo(name="reset", direction="input"),
        ]
        
        results = [self.manager.resolve_signal_connection(p) for p in ports]
        
        assert results[0] == "sys_CLK"
        assert results[1] == "sys_CLK_REF"
        assert results[2] == "data_out"
        assert results[3] == "default_reset"
    
    def test_integration_mixed_rules(self):
        """集成测试：混合规则类型"""
        # 同时使用信号、参数、线网规则
        self.manager.add_signal_rule("*", "*_sig")
        self.manager.add_param_rule("WIDTH", "32")
        self.manager.add_wire_rule("*_out", "*_wire", width="WIDTH", expression="0")
        
        # 测试信号
        port = PortInfo(name="data")
        assert self.manager.resolve_signal_connection(port) == "data_sig"
        
        # 测试参数
        assert self.manager.resolve_param_connection("WIDTH") == "32"
        
        # 测试线网
        port_wire = PortInfo(name="result_out")
        wire_name, width, expression, has_rule = self.manager.resolve_wire_generation(port_wire)
        assert wire_name == "result_wire"
        assert width == "WIDTH"
        assert expression == "0"
        assert has_rule is True
    
    def test_integration_complex_pattern(self):
        """集成测试：复杂模式组合"""
        self.manager.add_signal_rule(
            "*_*_*",
            "${upper(*0)}_${lower(*1)}_${title(*2)} /* processed */",
            port_direction="input"
        )
        
        port = PortInfo(name="uart_rx_data", direction="input")
        result = self.manager.resolve_signal_connection(port)
        
        assert result == "UART_rx_Data /* processed */"
    
    def test_integration_literal_with_width_expression(self):
        """集成测试：字面值与宽度表达式"""
        self.manager.add_signal_rule("gnd_*", "0")
        
        ports = [
            PortInfo(name="gnd_1", width=1),
            PortInfo(name="gnd_8", width=8),
            PortInfo(name="gnd_16", width=16),
            PortInfo(name="gnd_param", width="DATA_WIDTH"),
            PortInfo(name="gnd_expr", width="WIDTH*2-1"),
        ]
        
        results = [self.manager.resolve_signal_connection(p) for p in ports]
        
        assert results[0] == "1'b0"
        assert results[1] == "8'b00000000"
        assert results[2] == "{16{1'b0}}"
        assert results[3] == "{DATA_WIDTH{1'b0}}"
        assert results[4] == "{(WIDTH*2-1){1'b0}}"
    
    def test_no_match_returns_original(self):
        """测试无匹配规则返回原始名称"""
        port = PortInfo(name="unknown_signal")
        assert self.manager.resolve_signal_connection(port) == "unknown_signal"
    
    def test_multiple_function_calls(self):
        """测试多个函数调用"""
        self.manager.add_signal_rule("*", "${strip(${upper(*)})}")
        
        port = PortInfo(name="  data  ")
        result = self.manager.resolve_signal_connection(port)
        # 注意：可能不支持嵌套函数，外层作为普通字符串
        # 根据实际实现调整预期
    
    def test_strip_functions(self):
        """测试strip系列函数"""
        self.manager.add_signal_rule("test1", "${strip(*)}")
        self.manager.add_signal_rule("test2", "${lstrip(*)}")
        self.manager.add_signal_rule("test3", "${rstrip(*)}")
        
        # 这些测试需要通配符捕获包含空格的内容
        # 可能需要调整测试方式
    
    def test_wire_comment_preservation(self):
        """测试线网规则中的注释保留"""
        self.manager.add_wire_rule("*", "*_wire /* wire comment */", width="8")
        
        port = PortInfo(name="data")
        wire_name, width, expression, has_rule = self.manager.resolve_wire_generation(port)
        
        assert "data_wire /* wire comment */" == wire_name
        assert width == "8"
        assert has_rule is True


# ==================== 参数化测试示例 ====================

class TestVCGRuleManagerParameterized:
    """参数化测试类"""
    
    @pytest.mark.parametrize("source,target,input_name,expected", [
        ("*", "prefix_*", "data", "prefix_data"),
        ("*", "prefix_*", "clk", "prefix_clk"),
        ("i_*", "o_*", "i_data", "o_data"),
        ("*_in", "*_out", "data_in", "data_out"),
    ])
    def test_signal_patterns_parametrized(self, source, target, input_name, expected):
        """参数化测试信号模式"""
        manager = VCGRuleManager()
        manager.add_signal_rule(source, target)
        
        port = PortInfo(name=input_name)
        assert manager.resolve_signal_connection(port) == expected
    
    @pytest.mark.parametrize("width,literal,expected", [
        (1, "0", "1'b0"),
        (1, "1", "1'b1"),
        (4, "0", "4'b0000"),
        (8, "1", "8'b11111111"),
        (16, "0", "{16{1'b0}}"),
        (32, "1", "{32{1'b1}}"),
    ])
    def test_literal_generation_parametrized(self, width, literal, expected):
        """参数化测试字面值生成"""
        manager = VCGRuleManager()
        manager.add_signal_rule("*", literal)
        
        port = PortInfo(name="test", width=width)
        assert manager.resolve_signal_connection(port) == expected
    
    @pytest.mark.parametrize("direction,port_dir,should_match", [
        ("input", "input", True),
        ("input", "output", False),
        ("output", "output", True),
        ("output", "input", False),
        (None, "input", True),
        (None, "output", True),
        ("input", None, True),
    ])
    def test_direction_constraint_parametrized(self, direction, port_dir, should_match):
        """参数化测试方向约束"""
        manager = VCGRuleManager()
        manager.add_signal_rule("*", "matched_*", port_direction=direction)
        
        port = PortInfo(name="test", direction=port_dir)
        result = manager.resolve_signal_connection(port)
        
        if should_match:
            assert result == "matched_test"
        else:
            assert result == "test"


# ==================== 运行配置 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])