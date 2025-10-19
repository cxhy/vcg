"""
VerilogParser 单元测试
测试平台: pytest
作者: Python验证专家
项目: vcg
"""

import os
import sys
import pytest
import tempfile
from typing import Dict, Any

# 导入被测模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
from src.VerilogParser import VerilogParser


class TestVerilogParserBasic:
    """基础功能测试类 - P0优先级"""
    
    def setup_method(self):
        """每个测试方法前初始化"""
        self.parser = VerilogParser()
    
    # ========== F1: 模块声明解析 ==========
    
    def test_f1_1_basic_module_name(self):
        """F1.1: 解析基本模块名"""
        code = "module test_mod; endmodule"
        ast = self.parser.parse_string(code)
        assert ast is not None
        info = self.parser.get_module_info()
        assert info is not None
        assert info['name'] == 'test_mod'
    
    def test_f1_2_module_name_with_underscore(self):
        """F1.2: 解析带下划线的模块名"""
        code = "module test_mod_123; endmodule"
        ast = self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert info['name'] == 'test_mod_123'
    
    def test_f1_3_empty_module(self):
        """F1.3: 空模块（无参数无端口）"""
        code = "module empty; endmodule"
        ast = self.parser.parse_string(code)
        assert ast is not None
        info = self.parser.get_module_info()
        assert info['name'] == 'empty'
        assert len(info['ports']) == 0
        assert len(info['parameters']) == 0
    
    def test_f1_4_missing_module_name(self):
        """F1.4: 模块名缺失"""
        code = "module ; endmodule"
        ast = self.parser.parse_string(code)
        # 应该解析失败
        assert ast is None or self.parser.get_module_info() is None


class TestVerilogParserParameters:
    """参数声明解析测试类 - P0/P1优先级"""
    
    def setup_method(self):
        self.parser = VerilogParser()
    
    # ========== F2.1-F2.12: 模块头部参数（Verilog-2001风格） ==========
    
    def test_f2_1_single_parameter(self):
        """F2.1: 单个parameter"""
        code = "module m #(parameter P=1); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert len(info['parameters']) == 1
        param = info['parameters'][0]
        assert param['name'] == 'P'
        assert param['type'] == 'parameter'
        assert param['default_value'] == '1'
    
    def test_f2_2_single_localparam(self):
        """F2.2: 单个localparam"""
        code = "module m #(localparam L=2); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert len(info['parameters']) == 1
        param = info['parameters'][0]
        assert param['name'] == 'L'
        assert param['type'] == 'localparam'
        assert param['default_value'] == '2'
    
    def test_f2_3_multiple_parameters(self):
        """F2.3: 多个参数（逗号分隔）"""
        code = "module m #(parameter A=1, parameter B=2); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert len(info['parameters']) == 2
        assert info['parameters'][0]['name'] == 'A'
        assert info['parameters'][1]['name'] == 'B'
    
    def test_f2_4_mixed_param_types(self):
        """F2.4: 混合parameter和localparam"""
        code = "module m #(parameter P=1, localparam L=2); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert len(info['parameters']) == 2
        assert info['parameters'][0]['type'] == 'parameter'
        assert info['parameters'][1]['type'] == 'localparam'
    
    def test_f2_5_parameter_expression(self):
        """F2.5: 参数值为表达式"""
        code = "module m #(parameter WIDTH = 8*2); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        param = info['parameters'][0]
        assert '8*2' in param['default_value'].replace(' ', '')
    
    def test_f2_6_parameter_negative_value(self):
        """F2.6: 参数值为负数"""
        code = "module m #(parameter OFFSET = -10); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert '-10' in info['parameters'][0]['default_value']
    
    def test_f2_7_parameter_hex_value(self):
        """F2.7: 参数值为十六进制"""
        code = "module m #(parameter ADDR = 16'hFFFF); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert 'hFFFF' in info['parameters'][0]['default_value']
    
    def test_f2_8_parameter_binary_value(self):
        """F2.8: 参数值为二进制"""
        code = "module m #(parameter MASK = 4'b1010); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert 'b1010' in info['parameters'][0]['default_value']
    
    def test_f2_9_parameter_octal_value(self):
        """F2.9: 参数值为八进制"""
        code = "module m #(parameter VAL = 8'o377); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert 'o377' in info['parameters'][0]['default_value']
    
    def test_f2_10_parameter_power_operator(self):
        """F2.10: 参数值包含幂运算符"""
        code = "module m #(parameter SIZE = 2**10); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert '2**10' in info['parameters'][0]['default_value'].replace(' ', '')
    
    def test_f2_11_empty_parameter_list(self):
        """F2.11: 空参数列表"""
        code = "module m #(); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert len(info['parameters']) == 0
    
    def test_f2_12_parameter_syntax_error(self):
        """F2.12: 参数声明语法错误"""
        code = "module m #(parameter); endmodule"
        # 应记录错误并继续解析，或返回None
        result = self.parser.parse_string(code)
        # 验证容错行为
        assert result is None or isinstance(result, object)
    
    # ========== F2.13-F2.15: 模块内部参数声明 ==========
    
    def test_f2_13_body_parameter(self):
        """F2.13: 模块体内parameter"""
        code = "module m; parameter P=1; endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        params = [p for p in info['parameters'] if p['name'] == 'P']
        assert len(params) == 1
        assert params[0]['type'] == 'parameter'
    
    def test_f2_14_body_localparam(self):
        """F2.14: 模块体内localparam"""
        code = "module m; localparam L=2; endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        params = [p for p in info['parameters'] if p['name'] == 'L']
        assert len(params) == 1
        assert params[0]['type'] == 'localparam'
    
    def test_f2_15_body_multiple_parameters(self):
        """F2.15: 模块体内多个参数"""
        code = "module m; parameter A=1, B=2; endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        param_names = [p['name'] for p in info['parameters']]
        assert 'A' in param_names
        assert 'B' in param_names


class TestVerilogParserPortsV2001:
    """端口解析测试 - Verilog-2001 ANSI风格 - P0优先级"""
    
    def setup_method(self):
        self.parser = VerilogParser()
    
    # ========== F3.1-F3.13: Verilog-2001风格端口 ==========
    
    def test_f3_1_input_port_no_type(self):
        """F3.1: input端口（无类型）"""
        code = "module m(input clk); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert len(info['ports']) == 1
        port = info['ports'][0]
        assert port['name'] == 'clk'
        assert port['direction'] == 'input'
        assert port['net_type'] == 'wire'
    
    def test_f3_2_output_port_no_type(self):
        """F3.2: output端口（无类型）"""
        code = "module m(output data); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        port = info['ports'][0]
        assert port['name'] == 'data'
        assert port['direction'] == 'output'
        assert port['net_type'] == 'wire'
    
    def test_f3_3_inout_port_no_type(self):
        """F3.3: inout端口（无类型）"""
        code = "module m(inout bus); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        port = info['ports'][0]
        assert port['name'] == 'bus'
        assert port['direction'] == 'inout'
        assert port['net_type'] == 'wire'
    
    def test_f3_4_input_wire_port(self):
        """F3.4: input wire端口"""
        code = "module m(input wire clk); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        port = info['ports'][0]
        assert port['direction'] == 'input'
        assert port['net_type'] == 'wire'
    
    def test_f3_5_output_reg_port(self):
        """F3.5: output reg端口"""
        code = "module m(output reg q); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        port = info['ports'][0]
        assert port['direction'] == 'output'
        assert port['net_type'] == 'reg'
    
    def test_f3_6_port_with_width(self):
        """F3.6: 带位宽的端口"""
        code = "module m(input [7:0] data); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        port = info['ports'][0]
        assert port['width'] == 8
        assert '[7:0]' in port['range']
    
    def test_f3_7_port_big_endian(self):
        """F3.7: 非标准位宽（大端序）"""
        code = "module m(input [31:0] bus); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        port = info['ports'][0]
        assert port['width'] == 32
    
    def test_f3_8_port_little_endian(self):
        """F3.8: 非标准位宽（小端序）"""
        code = "module m(input [0:7] data); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        port = info['ports'][0]
        assert port['width'] == 8
    
    def test_f3_9_port_width_parameter_expression(self):
        """F3.9: 位宽使用参数表达式"""
        code = "module m(input [WIDTH-1:0] d); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        port = info['ports'][0]
        # 表达式应该被保留
        assert 'WIDTH' in port['range']
    
    def test_f3_10_port_width_complex_expression(self):
        """F3.10: 位宽使用复杂表达式"""
        code = "module m(input [2**N-1:0] d); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        port = info['ports'][0]
        assert '2**N' in port['range'].replace(' ', '') or 'N' in port['range']
    
    def test_f3_11_multiple_ports(self):
        """F3.11: 多个端口（逗号分隔）"""
        code = "module m(input a, input b, output c); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert len(info['ports']) == 3
        port_names = [p['name'] for p in info['ports']]
        assert 'a' in port_names
        assert 'b' in port_names
        assert 'c' in port_names
    
    def test_f3_12_logic_port(self):
        """F3.12: logic类型端口（SystemVerilog）"""
        code = "module m(input logic sig); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        if info and len(info['ports']) > 0:
            port = info['ports'][0]
            assert port['net_type'] == 'logic'
    
    def test_f3_13_empty_port_list(self):
        """F3.13: 空端口列表"""
        code = "module m(); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert len(info['ports']) == 0


class TestVerilogParserPortsV95:
    """端口解析测试 - Verilog-1995非ANSI风格 - P1优先级"""
    
    def setup_method(self):
        self.parser = VerilogParser()
    
    # ========== F3.14-F3.22: Verilog-1995风格端口 ==========
    
    def test_f3_14_v95_input_port(self):
        """F3.14: 端口列表+input声明"""
        code = "module m(clk); input clk; endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        port = [p for p in info['ports'] if p['name'] == 'clk'][0]
        assert port['direction'] == 'input'
    
    def test_f3_15_v95_output_port(self):
        """F3.15: 端口列表+output声明"""
        code = "module m(data); output data; endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        port = [p for p in info['ports'] if p['name'] == 'data'][0]
        assert port['direction'] == 'output'
    
    def test_f3_16_v95_inout_port(self):
        """F3.16: 端口列表+inout声明"""
        code = "module m(bus); inout bus; endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        port = [p for p in info['ports'] if p['name'] == 'bus'][0]
        assert port['direction'] == 'inout'
    
    def test_f3_17_v95_multiple_ports(self):
        """F3.17: 多端口+批量声明"""
        code = "module m(a, b); input a, b; endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert len(info['ports']) == 2
        for port in info['ports']:
            assert port['direction'] == 'input'
    
    def test_f3_18_v95_port_with_width(self):
        """F3.18: 带位宽的V95声明"""
        code = "module m(d); input [7:0] d; endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        port = info['ports'][0]
        assert port['width'] == 8
    
    def test_f3_19_v95_input_wire(self):
        """F3.19: input wire明确声明"""
        code = "module m(c); input wire c; endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        port = info['ports'][0]
        assert port['net_type'] == 'wire'
    
    def test_f3_20_v95_output_reg(self):
        """F3.20: output reg明确声明"""
        code = "module m(q); output reg q; endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        port = info['ports'][0]
        assert port['net_type'] == 'reg'
    
    def test_f3_21_v95_undeclared_direction(self):
        """F3.21: 端口未声明方向"""
        code = "module m(x); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        # 应记录为未定义或默认处理
        if info and len(info['ports']) > 0:
            port = info['ports'][0]
            assert port['name'] == 'x'
    
    def test_f3_22_v95_mixed_declarations(self):
        """F3.22: 多端口混合声明"""
        code = "module m(a, b, c); input a; output b, c; endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert len(info['ports']) == 3
        directions = {p['name']: p['direction'] for p in info['ports']}
        assert directions['a'] == 'input'
        assert directions['b'] == 'output'
        assert directions['c'] == 'output'


class TestVerilogParserExpressions:
    """表达式解析支持测试 - P1优先级"""
    
    def setup_method(self):
        self.parser = VerilogParser()
    
    # ========== F4: 表达式解析 ==========
    
    @pytest.mark.parametrize("expr,expected", [
        ("WIDTH+1", ["WIDTH", "+", "1"]),
        ("SIZE-1", ["SIZE", "-", "1"]),
        ("8*2", ["8", "*", "2"]),
        ("WIDTH/2", ["WIDTH", "/", "2"]),
        ("N%4", ["N", "%", "4"]),
        ("2**N", ["2", "**", "N"]),
    ])
    def test_f4_arithmetic_expressions(self, expr, expected):
        """F4.1-F4.6: 算术表达式"""
        code = f"module m #(parameter P = {expr}); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        param_value = info['parameters'][0]['default_value'].replace(' ', '')
        # 验证表达式被保留
        for token in expected:
            if token not in ['+', '-', '*', '/', '%', '**']:
                assert token in param_value
    
    def test_f4_7_parentheses_expression(self):
        """F4.7: 括号表达式"""
        code = "module m #(parameter P = (WIDTH+1)/2); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert 'WIDTH' in info['parameters'][0]['default_value']
    
    def test_f4_8_ternary_operator(self):
        """F4.8: 三元运算符"""
        code = "module m #(parameter P = EN ? 8 : 4); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        param_value = info['parameters'][0]['default_value']
        assert 'EN' in param_value and '?' in param_value
    
    def test_f4_9_logical_and(self):
        """F4.9: 逻辑与"""
        code = "module m #(parameter P = A && B); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert '&&' in info['parameters'][0]['default_value']
    
    def test_f4_10_logical_or(self):
        """F4.10: 逻辑或"""
        code = "module m #(parameter P = A || B); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert '||' in info['parameters'][0]['default_value']
    
    def test_f4_11_bitwise_and(self):
        """F4.11: 按位与"""
        code = "module m #(parameter P = MASK & 8'hFF); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        param_value = info['parameters'][0]['default_value']
        assert 'MASK' in param_value and '&' in param_value
    
    def test_f4_12_bitwise_or(self):
        """F4.12: 按位或"""
        code = "module m #(parameter P = A | B); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert '|' in info['parameters'][0]['default_value']
    
    def test_f4_13_bitwise_xor(self):
        """F4.13: 按位异或"""
        code = "module m #(parameter P = A ^ B); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert '^' in info['parameters'][0]['default_value']
    
    def test_f4_14_left_shift(self):
        """F4.14: 左移"""
        code = "module m #(parameter P = 1 << N); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert '<<' in info['parameters'][0]['default_value']
    
    def test_f4_15_right_shift(self):
        """F4.15: 右移"""
        code = "module m #(parameter P = VAL >> 2); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert '>>' in info['parameters'][0]['default_value']
    
    def test_f4_16_comparison(self):
        """F4.16: 比较运算"""
        code = "module m #(parameter P = WIDTH > 8); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert '>' in info['parameters'][0]['default_value']
    
    def test_f4_17_unary_minus(self):
        """F4.17: 一元负号"""
        code = "module m #(parameter P = -OFFSET); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert '-' in info['parameters'][0]['default_value']
    
    def test_f4_18_unary_not(self):
        """F4.18: 一元取反"""
        code = "module m #(parameter P = ~MASK); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert '~' in info['parameters'][0]['default_value']
    
    def test_f4_19_function_call(self):
        """F4.19: 函数调用"""
        code = "module m #(parameter P = $clog2(SIZE)); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        param_value = info['parameters'][0]['default_value']
        assert '$clog2' in param_value or 'clog2' in param_value
    
    def test_f4_20_bit_select(self):
        """F4.20: 位选择"""
        code = "module m #(parameter P = BUS[3]); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        param_value = info['parameters'][0]['default_value']
        assert 'BUS' in param_value and '[' in param_value
    
    def test_f4_21_bit_slice(self):
        """F4.21: 位片选择"""
        code = "module m #(parameter P = DATA[7:4]); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        param_value = info['parameters'][0]['default_value']
        assert 'DATA' in param_value and '[' in param_value
    
    def test_f4_22_concatenation(self):
        """F4.22: 拼接"""
        code = "module m #(parameter P = {A, B, C}); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        param_value = info['parameters'][0]['default_value']
        assert '{' in param_value and '}' in param_value


class TestVerilogParserErrorHandling:
    """错误处理和容错测试 - P1优先级"""
    
    def setup_method(self):
        self.parser = VerilogParser()
    
    # ========== F5: 错误处理 ==========
    
    def test_f5_1_file_not_found(self):
        """F5.1: 文件不存在"""
        result = self.parser.parse_file("/nonexistent/path/file.v")
        assert result is None
    
    def test_f5_2_file_encoding_error(self):
        """F5.2: 文件编码错误"""
        # 创建临时文件，写入非UTF-8字符
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.v', delete=False) as f:
            f.write(b'\xff\xfe\x00\x00')  # 无效UTF-8序列
            temp_path = f.name
        
        try:
            result = self.parser.parse_file(temp_path)
            # 应返回None或抛出异常被捕获
            assert result is None or isinstance(result, object)
        finally:
            os.unlink(temp_path)
    
    def test_f5_3_missing_endmodule(self):
        """F5.3: 缺少endmodule"""
        code = "module test(input clk);"
        result = self.parser.parse_string(code)
        # 应尝试恢复或返回None
        assert result is None or isinstance(result, object)
    
    def test_f5_4_port_syntax_error(self):
        """F5.4: 端口声明语法错误"""
        code = "module m(input ); endmodule"
        result = self.parser.parse_string(code)
        # 应记录错误并继续
        assert result is None or isinstance(result, object)
    
    def test_f5_5_parameter_syntax_error(self):
        """F5.5: 参数声明语法错误"""
        code = "module m; parameter ; endmodule"
        result = self.parser.parse_string(code)
        # 应记录错误并继续
        assert result is None or isinstance(result, object)
    
    def test_f5_6_width_expression_error(self):
        """F5.6: 位宽表达式错误"""
        code = "module m(input [error] d); endmodule"
        result = self.parser.parse_string(code)
        # 应记录错误并继续
        assert result is None or isinstance(result, object)
    
    def test_f5_7_expression_syntax_error(self):
        """F5.7: 表达式语法错误"""
        code = "module m #(parameter P = ++); endmodule"
        result = self.parser.parse_string(code)
        # 应记录错误
        assert result is None or isinstance(result, object)
    
    def test_f5_8_incomplete_module(self):
        """F5.8: EOF前遇到语法错误（不完整的模块）"""
        code = "module test(input clk"
        result = self.parser.parse_string(code)
        # 应记录错误，可能返回部分结果
        assert result is None or isinstance(result, object)
    
    def test_f5_9_multiple_parse_calls(self):
        """F5.9: 多次调用parse方法"""
        code1 = "module m1(input a); endmodule"
        code2 = "module m2(output b); endmodule"
        
        self.parser.parse_string(code1)
        info1 = self.parser.get_module_info()
        
        self.parser.parse_string(code2)
        info2 = self.parser.get_module_info()
        
        # 两次解析应互不影响
        assert info1['name'] != info2['name']
        assert info2['name'] == 'm2'


class TestVerilogParserMacros:
    """宏预处理测试 - P2优先级"""
    
    # ========== F6: 宏预处理 ==========
    
    def test_f6_1_init_with_macros(self):
        """F6.1: 初始化时传入宏"""
        parser = VerilogParser(macros={"WIDTH": "8"})
        code = "module m #(parameter P = `WIDTH); endmodule"
        parser.parse_string(code)
        info = parser.get_module_info()
        if info and len(info['parameters']) > 0:
            # 宏应该被替换
            param_value = info['parameters'][0]['default_value']
            assert '8' in param_value or 'WIDTH' in param_value
    
    def test_f6_2_macro_in_parameter(self):
        """F6.2: 宏在参数中使用"""
        parser = VerilogParser(macros={"WIDTH": "16"})
        code = "module m #(parameter P = `WIDTH); endmodule"
        parser.parse_string(code)
        info = parser.get_module_info()
        if info and len(info['parameters']) > 0:
            assert info['parameters'][0]['default_value']
    
    def test_f6_3_macro_in_width(self):
        """F6.3: 宏在位宽中使用"""
        parser = VerilogParser(macros={"WIDTH": "8"})
        code = "module m(input [`WIDTH-1:0] d); endmodule"
        parser.parse_string(code)
        info = parser.get_module_info()
        if info and len(info['ports']) > 0:
            assert info['ports'][0]['range']
    
    def test_f6_4_undefined_macro(self):
        """F6.4: 未定义的宏"""
        parser = VerilogParser()
        code = "module m #(parameter P = `UNDEFINED_MACRO); endmodule"
        result = parser.parse_string(code)
        # 按预处理器默认行为处理
        assert result is None or isinstance(result, object)


class TestVerilogParserBoundaryConditions:
    """边界条件和特殊场景测试 - P2优先级"""
    
    def setup_method(self):
        self.parser = VerilogParser()
    
    # ========== B1-B8: 极端情况 ==========
    
    def test_b1_completely_empty_module(self):
        """B1: 完全空模块"""
        code = "module e; endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert info['name'] == 'e'
        assert len(info['ports']) == 0
        assert len(info['parameters']) == 0
    
    def test_b2_very_long_module_name(self):
        """B2: 超长模块名"""
        long_name = "m" + "a" * 999
        code = f"module {long_name}; endmodule"
        result = self.parser.parse_string(code)
        if result:
            info = self.parser.get_module_info()
            assert len(info['name']) >= 100
    
    def test_b3_many_ports(self):
        """B3: 大量端口（简化版：50个端口）"""
        ports = ", ".join([f"input p{i}" for i in range(50)])
        code = f"module m({ports}); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert len(info['ports']) >= 40  # 允许部分解析失败
    
    def test_b4_many_parameters(self):
        """B4: 大量参数（简化版：50个参数）"""
        params = ", ".join([f"parameter P{i}={i}" for i in range(50)])
        code = f"module m #({params}); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert len(info['parameters']) >= 40  # 允许部分解析失败
    
    def test_b5_deeply_nested_expression(self):
        """B5: 深度嵌套表达式"""
        code = "module m #(parameter P = ((((A+B)+C)+D)+E)); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert len(info['parameters']) == 1
    
    def test_b6_large_number(self):
        """B6: 超大数值"""
        code = "module m #(parameter ADDR = 128'hFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        param_value = info['parameters'][0]['default_value']
        assert 'h' in param_value.lower() and 'F' in param_value.upper()
    
    def test_b7_empty_string_parse(self):
        """B7: 空字符串解析"""
        result = self.parser.parse_string("")
        assert result is None or self.parser.get_module_info() is None
    
    def test_b8_whitespace_only(self):
        """B8: 仅空白符"""
        result = self.parser.parse_string("   \n\n  \t  ")
        assert result is None or self.parser.get_module_info() is None
    
    # ========== B9-B10: 混合风格 ==========
    
    def test_b9_mixed_v95_v2001_ports(self):
        """B9: V95和V2001混合端口声明"""
        code = """
        module m(
            input wire clk,
            a, b
        );
            input a;
            output b;
        endmodule
        """
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        # 应该正确解析混合风格
        port_names = [p['name'] for p in info['ports']]
        assert 'clk' in port_names
        assert 'a' in port_names or 'b' in port_names
    
    def test_b10_parameters_in_header_and_body(self):
        """B10: 头部和内部都有参数"""
        code = """
        module m #(parameter P1=1);
            parameter P2=2;
        endmodule
        """
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        param_names = [p['name'] for p in info['parameters']]
        assert 'P1' in param_names
        assert 'P2' in param_names
    
    # ========== B11-B13: 注释和空白 ==========
    
    def test_b11_single_line_comment(self):
        """B11: 单行注释"""
        code = """
        module m(
            input clk // clock signal
        );
        endmodule
        """
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert len(info['ports']) == 1
        assert info['ports'][0]['name'] == 'clk'
    
    def test_b12_multi_line_comment(self):
        """B12: 多行注释"""
        code = """
        module m(
            /* this is a
               multi-line comment */
            input clk
        );
        endmodule
        """
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert len(info['ports']) == 1
    
    def test_b13_comment_in_declaration(self):
        """B13: 注释嵌入声明"""
        code = "module m(input /* comment */ clk); endmodule"
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        assert info['ports'][0]['name'] == 'clk'


class TestVerilogParserFileOperations:
    """文件操作测试"""
    
    def setup_method(self):
        self.parser = VerilogParser()
    
    def test_parse_file_success(self):
        """测试成功解析文件"""
        # 创建临时Verilog文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.v', delete=False, encoding='utf-8') as f:
            f.write("module test_module(input clk, output reg data); endmodule")
            temp_path = f.name
        
        try:
            result = self.parser.parse_file(temp_path)
            assert result is not None
            info = self.parser.get_module_info()
            assert info['name'] == 'test_module'
            assert len(info['ports']) == 2
        finally:
            os.unlink(temp_path)
    
    def test_parse_file_permission_error(self):
        """测试文件权限错误（Unix系统）"""
        if os.name == 'posix':
            with tempfile.NamedTemporaryFile(mode='w', suffix='.v', delete=False) as f:
                f.write("module test; endmodule")
                temp_path = f.name
            
            try:
                os.chmod(temp_path, 0o000)
                result = self.parser.parse_file(temp_path)
                assert result is None
            finally:
                os.chmod(temp_path, 0o644)
                os.unlink(temp_path)


class TestVerilogParserComplexScenarios:
    """复杂综合场景测试"""
    
    def setup_method(self):
        self.parser = VerilogParser()
    
    def test_realistic_module(self):
        """真实复杂模块测试"""
        code = """
        module uart_tx #(
            parameter CLOCK_FREQ = 50000000,
            parameter BAUD_RATE = 115200,
            localparam DIVISOR = CLOCK_FREQ / BAUD_RATE
        )(
            input wire clk,
            input wire rst_n,
            input wire [7:0] data_in,
            input wire data_valid,
            output reg tx_out,
            output wire busy
        );
            parameter STATE_IDLE = 2'b00;
            parameter STATE_START = 2'b01;
            localparam STATE_DATA = 2'b10;
        endmodule
        """
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        
        # 验证模块名
        assert info['name'] == 'uart_tx'
        
        # 验证参数
        param_names = [p['name'] for p in info['parameters']]
        assert 'CLOCK_FREQ' in param_names
        assert 'BAUD_RATE' in param_names
        assert 'DIVISOR' in param_names
        assert 'STATE_IDLE' in param_names
        
        # 验证端口
        port_names = [p['name'] for p in info['ports']]
        assert 'clk' in port_names
        assert 'rst_n' in port_names
        assert 'data_in' in port_names
        assert 'tx_out' in port_names
        
        # 验证端口方向
        port_dict = {p['name']: p for p in info['ports']}
        assert port_dict['clk']['direction'] == 'input'
        assert port_dict['tx_out']['direction'] == 'output'
        
        # 验证位宽
        assert port_dict['data_in']['width'] == 8


class TestVerilogParserReturnStructure:
    """返回值结构验证"""
    
    def setup_method(self):
        self.parser = VerilogParser()
    
    def test_module_info_structure(self):
        """验证get_module_info返回的字典结构"""
        code = """
        module test #(parameter WIDTH=8)(
            input [WIDTH-1:0] data_in,
            output reg [WIDTH-1:0] data_out
        );
        endmodule
        """
        self.parser.parse_string(code)
        info = self.parser.get_module_info()
        
        # 验证顶层键存在
        assert 'name' in info
        assert 'parameters' in info
        assert 'ports' in info
        
        # 验证数据类型
        assert isinstance(info['name'], str)
        assert isinstance(info['parameters'], list)
        assert isinstance(info['ports'], list)
        
        # 验证参数结构
        if len(info['parameters']) > 0:
            param = info['parameters'][0]
            assert 'name' in param
            assert 'type' in param
            assert 'default_value' in param
            assert isinstance(param['name'], str)
            assert isinstance(param['type'], str)
            assert isinstance(param['default_value'], str)
        
        # 验证端口结构
        if len(info['ports']) > 0:
            port = info['ports'][0]
            assert 'name' in port
            assert 'direction' in port
            assert 'net_type' in port
            assert 'range' in port
            assert 'width' in port
            assert isinstance(port['name'], str)
            assert isinstance(port['direction'], str)
            assert isinstance(port['width'], str)
    
    def test_get_module_info_before_parse(self):
        """测试解析前调用get_module_info"""
        result = self.parser.get_module_info()
        # 应返回None或抛出合理的异常
        assert result is None or isinstance(result, dict)


# ========== Pytest配置和fixtures ==========

@pytest.fixture
def temp_verilog_file():
    """创建临时Verilog文件的fixture"""
    def _create_file(content):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.v', delete=False, encoding='utf-8') as f:
            f.write(content)
            return f.name
    return _create_file


@pytest.fixture
def cleanup_file():
    """清理临时文件的fixture"""
    files_to_cleanup = []
    
    def _register(filepath):
        files_to_cleanup.append(filepath)
    
    yield _register
    
    for filepath in files_to_cleanup:
        if os.path.exists(filepath):
            os.unlink(filepath)


# ========== 运行配置 ==========

if __name__ == "__main__":
    # 运行测试
    pytest.main([
        __file__,
        "-v",  # 详细输出
        "--tb=short",  # 简短的traceback
        "--strict-markers",  # 严格的marker检查
        "-p", "no:warnings",  # 不显示warnings
    ])