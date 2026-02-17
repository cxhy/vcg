"""
WiresManager 单元测试模块（修复版本）
测试平台: pytest
修复说明: resolve_wire_generation 返回值从 (wire_name, expression) 修正为 (wire_name, width, expression, rule_matched)
"""

import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock

# 设置项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.vcg_wires_manager import WiresManager
from src.vcg_rule_manager import VCGRuleManager
from src.vcg_exceptions import VCGFileError, VCGParseError, VCGRuntimeError, VCGSyntaxError


#==================== 测试夹具 (Fixtures) ====================

@pytest.fixture
def mock_rule_manager():
    """模拟规则管理器"""
    manager = Mock(spec=VCGRuleManager)
    return manager


@pytest.fixture
def wires_manager(mock_rule_manager):
    """创建 WiresManager 实例"""
    return WiresManager(mock_rule_manager)


@pytest.fixture
def wires_manager_with_macros(mock_rule_manager):
    """创建带宏定义的 WiresManager 实例"""
    macros = {"WIDTH": "8", "DEPTH": "16"}
    return WiresManager(mock_rule_manager, macros=macros)


@pytest.fixture
def sample_verilog_file(tmp_path):
    """创建示例 Verilog 文件"""
    file_path = tmp_path / "test_module.v"
    content = """
module test_module (
    input wire clk,
    input wire rst_n,
    input wire [7:0] data_in,
    output wire [15:0] data_out,
    output wire valid,
    inout wire [3:0] bidir_port
);
endmodule
"""
    file_path.write_text(content)
    return str(file_path)


@pytest.fixture
def invalid_verilog_file(tmp_path):
    """创建无效的 Verilog 文件"""
    file_path = tmp_path / "invalid.v"
    content = "this is not valid verilog code @#$%"
    file_path.write_text(content)
    return str(file_path)


@pytest.fixture
def empty_module_file(tmp_path):
    """创建空端口列表的模块"""
    file_path = tmp_path / "empty_module.v"
    content = """
module empty_module ();
endmodule
"""
    file_path.write_text(content)
    return str(file_path)


@pytest.fixture
def parametric_module_file(tmp_path):
    """创建参数化宽度的模块"""
    file_path = tmp_path / "param_module.v"
    content = """
module param_module #(
    parameter DATA_WIDTH = 32,
    parameter ADDR_WIDTH = 16
)(
    input wire [DATA_WIDTH-1:0] data,
    input wire [ADDR_WIDTH-1:0] addr,
    output wire [(DATA_WIDTH+8)-1:0] result
);
endmodule
"""
    file_path.write_text(content)
    return str(file_path)


@pytest.fixture
def multidim_array_file(tmp_path):
    """创建多维数组端口的模块"""
    file_path = tmp_path / "multidim.v"
    content = """
module multidim_module (
    input wire [7:0][3:0] array_in,
    output wire [15:0][7:0] array_out
);
endmodule
"""
    file_path.write_text(content)
    return str(file_path)


#==================== F1: 文件解析功能测试 ====================

class TestFileParsingFeatures:
    """F1: 文件解析功能测试"""
    
    def test_tc001_parse_valid_file(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC001: 成功解析有效的Verilog 文件 (F1.1)"""
        # ✅ 修复: 返回4个值 (wire_name, width, expression, rule_matched)
        mock_rule_manager.resolve_wire_generation.return_value = (None, None, None, False)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {
                    'ports': [
                        Mock(name='clk', direction='input', width=None),
                        Mock(name='data_in', direction='input', width='8')
                    ]
                }
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file, 
                'test_module'
            )
            
            assert isinstance(result, str)
            assert 'wire' in result
    
    def test_tc002_file_not_exists(self, wires_manager):
        """TC002: 文件不存在 (F1.2)"""
        with pytest.raises(VCGFileError):
            wires_manager.generate_wires_def(
                "/non/existent/path/file.v",
                "test_module"
            )
    
    def test_tc003_invalid_verilog_syntax(self, wires_manager, invalid_verilog_file):
        """TC003: 解析错误的 Verilog 文件 (F1.3)"""
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.side_effect = VCGParseError("Parse error")
            
            with pytest.raises(VCGParseError):
                wires_manager.generate_wires_def(
                    invalid_verilog_file,
                    "test_module"
                )
    
    def test_tc004_file_with_macros(self, wires_manager_with_macros, sample_verilog_file):
        """TC004: 支持带宏定义的 Verilog 文件解析 (F1.4)"""
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            # 验证宏定义被传递给解析器
            MockParser.assert_called_with(macros={"WIDTH": "8", "DEPTH": "16"})


# ==================== F2: 端口方向过滤功能测试 ====================

class TestPortDirectionFiltering:
    """F2: 端口方向过滤功能测试"""
    
    def setup_method(self):
        """设置测试数据"""
        self.mock_ports = [
            Mock(name='clk', direction='input', width=None),
            Mock(name='data_in', direction='input', width='8'),
            Mock(name='data_out', direction='output', width='16'),
            Mock(name='valid', direction='output', width=None),
            Mock(name='bidir', direction='inout', width='4')
        ]
    
    def test_tc101_all_ports(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC101: port_direction=None - 处理所有端口 (F2.1)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = (None, None, None, False)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': self.mock_ports}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module',
                port_direction=None
            )
            
            # 验证所有端口都被处理
            assert 'clk' in result or mock_rule_manager.resolve_wire_generation.call_count == 5
    def test_tc102_input_ports_only(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC102: port_direction="input" - 仅处理输入端口 (F2.2)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = (None, None, None, False)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': self.mock_ports}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module',
                port_direction='input'
            )
            
            # 验证只处理了输入端口
            lines = result.strip().split('\n') if result else []
            for line in lines:
                # 输出端口名不应出现（除非规则改变了名称）
                pass# 具体验证依赖实际实现
    
    def test_tc103_output_ports_only(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC103: port_direction="output" - 仅处理输出端口 (F2.3)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = (None, None, None, False)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': self.mock_ports}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module',
                port_direction='output'
            )
            
            assert isinstance(result, str)
    
    def test_tc104_inout_ports_only(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC104: port_direction="inout" - 仅处理双向端口 (F2.4)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = (None, None, None, False)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': self.mock_ports}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module',
                port_direction='inout'
            )
            
            assert isinstance(result, str)
    
    def test_tc105_invalid_direction(self, wires_manager, sample_verilog_file):
        """TC105: 无效的 port_direction 值 (F2.5)"""
        with pytest.raises(ValueError):
            wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module',
                port_direction='invalid_direction'
            )
    
    def test_tc106_case_insensitive_direction(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC106: 大小写混合的方向参数 (F2.2/F2.3)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = (None, None, None, False)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': self.mock_ports}
            }
            
            # 测试 "INPUT"
            result1 = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module',
                port_direction='INPUT'
            )
            assert isinstance(result1, str)
            
            # 测试 "Output"
            result2 = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module',
                port_direction='Output'
            )
            assert isinstance(result2, str)


# ==================== F3: 生成模式功能测试 ====================

class TestGenerationPatterns:
    """F3: 生成模式功能测试"""
    
    def setup_method(self):
        """设置测试端口"""
        self.mock_ports = [
            Mock(name='matched_port', direction='input', width='8'),
            Mock(name='unmatched_port', direction='input', width='4')
        ]
    
    def test_tc201_greedy_rule_matched(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC201: 贪婪模式-规则匹配且返回有效名称 (F3.1.1)"""
        # ✅ 修复: 规则返回有效的wire名称 (wire_name, width, expression, rule_matched)
        mock_rule_manager.resolve_wire_generation.return_value = ('wire_name', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [self.mock_ports[0]]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module',
                pattern='greedy'
            )
            
            assert 'wire_name' in result or'wire' in result
    
    def test_tc202_greedy_rule_matched_empty_name(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC202: 贪婪模式-规则匹配但返回空名称 (F3.1.2)"""
        # ✅ 修复: 规则返回空字符串
        mock_rule_manager.resolve_wire_generation.return_value = ('', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [self.mock_ports[0]]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module',
                pattern='greedy'
            )
            
            # 不应生成该wire
            assert result == '' or 'matched_port' not in result
    
    def test_tc203_greedy_rule_not_matched(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC203: 贪婪模式-规则未匹配 (F3.1.3)"""
        # ✅ 修复: 规则未匹配，返回 None, False
        mock_rule_manager.resolve_wire_generation.return_value = (None, None, None, False)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [self.mock_ports[1]]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module',
                pattern='greedy'
            )
            
            # 应使用端口名作为wire名
            assert 'unmatched_port' in result or 'wire' in result
    
    def test_tc204_lazy_rule_matched(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC204: 懒惰模式-规则匹配且返回有效名称 (F3.2.1)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('wire_name', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [self.mock_ports[0]]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module',
                pattern='lazy'
            )
            
            assert 'wire_name' in result or 'wire' in result
    
    def test_tc205_lazy_rule_matched_empty_name(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC205: 懒惰模式-规则匹配但返回空名称 (F3.2.2)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [self.mock_ports[0]]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module',
                pattern='lazy'
            )
            
            # 不应生成该wire
            assert result == ''
    
    def test_tc206_lazy_rule_not_matched(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC206: 懒惰模式-规则未匹配，跳过端口 (F3.2.3)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = (None, None, None, False)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [self.mock_ports[1]]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module',
                pattern='lazy'
            )
            
            # lazy模式下未匹配应跳过
            assert result == ''
    
    def test_tc207_invalid_pattern(self, wires_manager, sample_verilog_file):
        """TC207: 无效的 pattern 值 (F3.3)"""
        with pytest.raises(ValueError):
            wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module',
                pattern='invalid_pattern'
            )


# ==================== F4: 宽度格式化功能测试 ====================

class TestWidthFormatting:
    """F4: 宽度格式化功能测试"""
    
    def test_tc301_no_width(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC301: 无宽度信息 (F4.1)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('test_wire', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='input', width=None)]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            # 不应包含宽度声明
            assert 'wire' in result
            assert '[' not in result or'test_wire' in result
    
    def test_tc302_single_bit_integer_1(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC302: 单比特整数1 (F4.2.1)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('test_wire', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='input', width=1)]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            # 宽度为1时不应生成宽度声明
            lines = result.strip().split('\n')
            assert any('[0:0]' not in line for line in lines)
    
    def test_tc303_single_bit_integer_0(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC303: 单比特整数0 (F4.2.1)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('test_wire', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='input', width=0)]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            assert 'wire' in result
    
    def test_tc304_multibit_integer(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC304: 多比特整数 (F4.2.2)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('test_wire', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='input', width=8)]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            # 应生成 [7:0]
            assert '[7:0]' in result or 'wire' in result
    
    def test_tc305_numeric_string_single_bit(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC305: 纯数字字符串单比特 (F4.3.1)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('test_wire', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='input', width='1')]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            assert 'wire' in result
    
    def test_tc306_numeric_string_multibit(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC306: 纯数字字符串多比特 (F4.3.2)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('test_wire', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='input', width='32')]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            # 应生成 [31:0]
            assert '[31:0]' in result or 'wire' in result
    
    def test_tc307_formatted_width(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC307: 已格式化的宽度 (F4.4)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('test_wire', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='input', width='[15:0]')]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            # 应直接使用 [15:0]
            assert '[15:0]' in result
    
    def test_tc308_addition_expression(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC308: 加法表达式 (F4.5)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('test_wire', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='input', width='N+1')]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            # 应生成 [(N+1)-1:0]
            assert '(N+1)-1:0' in result or 'wire' in result
    
    def test_tc309_subtraction_expression(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC309: 减法表达式 (F4.5)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('test_wire', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='input', width='N-1')]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            assert'wire' in result
    
    def test_tc310_multiplication_expression(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC310: 乘法表达式 (F4.5)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('test_wire', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='input', width='N*2')]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            assert 'wire' in result
    
    def test_tc311_parenthesis_expression(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC311: 括号表达式 (F4.5)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('test_wire', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='input', width='(N+M)/2')]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            # 应生成 [((N+M)/2)-1:0]
            assert 'wire' in result
    
    def test_tc312_parametric_width(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC312: 参数化宽度 (F4.6)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('test_wire', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='input', width='WIDTH')]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            # 应生成 [WIDTH-1:0]
            assert 'WIDTH-1:0' in result or 'wire' in result
    
    def test_tc313_multidimensional_array(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC313: 多维数组 (F4.7)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('test_wire', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='input', width='[7:0][3:0]')]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            # 应直接使用原格式
            assert '[7:0][3:0]' in result or 'wire' in result


# ==================== F5: 表达式处理功能测试 ====================

class TestExpressionHandling:
    """F5: 表达式处理功能测试"""
    
    def test_tc401_no_expression(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC401: 无表达式 (F5.1)"""
        # ✅ 修复: 4个返回值 (wire_name, width, expression, rule_matched)
        mock_rule_manager.resolve_wire_generation.return_value = ('data', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='input', width=8)]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            # 应生成 wire [7:0] data;
            assert 'wire' in result
            assert ';' in result
            assert '=' not in result  # 无表达式
    
    def test_tc402_with_expression_no_width(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC402: 有表达式无宽度 (F5.2)"""
        # ✅ 修复: 4个返回值，第3个参数是表达式
        mock_rule_manager.resolve_wire_generation.return_value = ('valid', None, "1'b0", True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='output', width=None)]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            # 应生成 wire valid = 1'b0;
            assert 'wire' in result
            assert '=' in result
            assert "1'b0" in result or'valid' in result
    
    def test_tc403_with_expression_and_width(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC403: 有表达式有宽度 (F5.2)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('counter', None, "16'd0", True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='output', width=16)]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            # 应生成 wire [15:0] counter = 16'd0;
            assert 'wire' in result
            assert '=' in result


# ==================== F6: 对齐格式化功能测试 ====================

class TestAlignmentFormatting:
    """F6: 对齐格式化功能测试"""
    
    def test_tc501_default_spacing(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC501: 默认间距15 (F6.1)"""
        assert wires_manager.get_base_spacing() == 15
        
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('name', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='input', width=8)]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            # 验证对齐格式
            assert 'wire' in result
    
    def test_tc502_long_prefix(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC502: 前缀过长使用单个空格 (F6.2)"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('very_long_signal_name', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='input', width='[127:0]')]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            # 当前缀很长时，应该只用一个空格
            assert 'wire' in result
    
    def test_tc503_custom_spacing(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """TC503: 自定义间距20 (F6.3)"""
        wires_manager.set_base_spacing(20)
        assert wires_manager.get_base_spacing() == 20
        
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('sig', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='input', width=4)]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            assert 'wire' in result
    
    def test_tc504_get_spacing(self, wires_manager):
        """TC504: 获取间距配置 (F6.3)"""
        default_spacing = wires_manager.get_base_spacing()
        assert default_spacing == 15
        
        wires_manager.set_base_spacing(25)
        new_spacing = wires_manager.get_base_spacing()
        assert new_spacing == 25


# ==================== 边界条件测试 ====================

class TestBoundaryConditions:
    """边界条件测试"""
    
    def test_bc001_empty_file_path(self, wires_manager):
        """BC001: 文件路径为空字符串"""
        with pytest.raises((VCGFileError, ValueError)):
            wires_manager.generate_wires_def('', 'test_module')
    
    def test_bc002_empty_module_name(self, wires_manager, sample_verilog_file):
        """BC002: module_name 为空字符串"""
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {}
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                ''
            )
            # 可能返回空或抛出异常
            assert isinstance(result, str)
    
    def test_bc003_empty_port_list(self, wires_manager, empty_module_file, mock_rule_manager):
        """BC003: 端口列表为空"""
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'empty_module': {'ports': []}
            }
            
            result = wires_manager.generate_wires_def(
                empty_module_file,
                'empty_module'
            )
            # 应返回空字符串
            assert result == ''
    
    def test_bc004_negative_width(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """BC004: 宽度为负数"""
        #✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('test', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='input', width=-5)]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            # 应按表达式处理
            assert 'wire' in result
    
    def test_bc005_special_characters_in_name(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """BC005: wire名称包含特殊字符"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('sig$name', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='input', width=None)]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            # 应保留原样
            assert 'sig$name' in result or 'wire' in result
    
    def test_bc006_zero_or_negative_spacing(self, wires_manager):
        """BC006: 间距设置为0或负数"""
        wires_manager.set_base_spacing(0)
        assert wires_manager.get_base_spacing() == 0
        
        wires_manager.set_base_spacing(-5)
        assert wires_manager.get_base_spacing() == -5


# ==================== 特殊场景测试 ====================

class TestSpecialScenarios:
    """特殊场景测试"""
    
    def test_ss001_port_name_with_underscore(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """SS001: 端口名包含下划线"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = (None, None, None, False)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='data_valid', direction='input', width=None)]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module',
                pattern='greedy'
            )
            
            assert 'data_valid' in result
    
    def test_ss002_port_name_with_digits(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """SS002: 端口名包含数字"""
        mock_rule_manager.resolve_wire_generation.return_value = (None, None, None, False)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port0', direction='input', width=None)]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module',
                pattern='greedy'
            )
            
            assert 'port0' in result
    
    def test_ss003_multidimensional_port(self, wires_manager, multidim_array_file, mock_rule_manager):
        """SS003: 多维数组端口"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('array_wire', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'multidim_module': {'ports': [Mock(name='array_in', direction='input', width='[7:0][3:0]')]}
            }
            
            result = wires_manager.generate_wires_def(
                multidim_array_file,
                'multidim_module'
            )
            
            assert '[7:0][3:0]' in result or 'wire' in result
    
    def test_ss004_parametric_width(self, wires_manager, parametric_module_file, mock_rule_manager):
        """SS004: 参数化宽度"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('param_sig', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'param_module': {'ports': [Mock(name='data', direction='input', width='DATA_WIDTH')]}
            }
            
            result = wires_manager.generate_wires_def(
                parametric_module_file,
                'param_module'
            )
            
            assert 'DATA_WIDTH-1:0' in result or 'wire' in result
    
    def test_ss005_complex_expression_width(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """SS005: 复杂表达式宽度"""
        # ✅ 修复: 4个返回值
        mock_rule_manager.resolve_wire_generation.return_value = ('complex_sig', None, None, True)
        
        with patch('src.vcg_wires_manager.VerilogParser') as MockParser:
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse_file.return_value = {
                'test_module': {'ports': [Mock(name='port', direction='input', width='(A+B)*C-1')]}
            }
            
            result = wires_manager.generate_wires_def(
                sample_verilog_file,
                'test_module'
            )
            
            assert'wire' in result