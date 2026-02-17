"""
test_vcg_instance_manager.py
InstanceManager模块的单元测试
"""

import os
import sys
import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import List, Optional

# 导入被测试模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
from src.vcg_instance_manager import InstanceManager


# ============================================================================
# Mock对象定义
# ============================================================================

class MockPortInfo:
    """Mock端口信息对象"""
    def __init__(self, name: str, direction: str = 'input', 
                 net_type: str = None, range_string: str = None,
                 port_type: str = 'NORMAL', interface_type: str = None):
        self.name = name
        self.direction = direction
        self.net_type = net_type
        self.range_string = range_string
        self.port_type = port_type
        self.interface_type = interface_type


class MockParameterInfo:
    """Mock参数信息对象"""
    def __init__(self, name: str):
        self.name = name


class MockAST:
    """Mock AST对象"""
    def __init__(self, ports: List[MockPortInfo] = None, 
                 parameters: List[MockParameterInfo] = None):
        self._ports = ports or []
        self._parameters = parameters or []
    
    def get_port_info(self) -> List[MockPortInfo]:
        return self._ports
    
    def get_parameter_info(self) -> List[MockParameterInfo]:
        return self._parameters


class MockVCGRuleManager:
    """Mock规则管理器"""
    def __init__(self, signal_map: dict = None, param_map: dict = None):
        self.signal_map = signal_map or {}
        self.param_map = param_map or {}
    
    def resolve_signal_connection(self, port) -> str:
        return self.signal_map.get(port.name, port.name + '_signal')
    
    def resolve_param_connection(self, param_name: str) -> Optional[str]:
        return self.param_map.get(param_name, None)


# ============================================================================
# Fixture定义
# ============================================================================

@pytest.fixture
def mock_rule_manager():
    """默认的Mock规则管理器"""
    return MockVCGRuleManager()


@pytest.fixture
def instance_manager(mock_rule_manager):
    """默认的InstanceManager实例"""
    return InstanceManager(mock_rule_manager)


@pytest.fixture
def mock_verilog_parser():
    """Mock Verilog解析器"""
    with patch('src.vcg_instance_manager.VerilogParser') as mock:
        yield mock


# ============================================================================
# 测试类：初始化和配置
# ============================================================================

class TestInitialization:
    """测试InstanceManager的初始化"""
    
    def test_init_with_rule_manager(self, mock_rule_manager):
        """TC-INIT-001: 测试使用规则管理器初始化"""
        im = InstanceManager(mock_rule_manager)
        assert im is not None
        assert im.get_alignment() == 18# 默认对齐宽度
    
    def test_init_with_macros(self, mock_rule_manager):
        """TC-INIT-002: 测试使用宏定义初始化"""
        macros = {'DEFINE1': '1', 'DEFINE2': '2'}
        im = InstanceManager(mock_rule_manager, macros=macros)
        assert im is not None
    
    def test_set_alignment(self, instance_manager):
        """TC-INIT-003: 测试设置对齐宽度"""
        instance_manager.set_alignment(25)
        assert instance_manager.get_alignment() == 25
    
    def test_get_default_alignment(self, instance_manager):
        """TC-INIT-004: 测试获取默认对齐宽度"""
        assert instance_manager.get_alignment() == 18


# ============================================================================
# 测试类：文件解析功能
# ============================================================================

class TestFileParsingFeatures:
    """测试文件解析功能"""
    
    def test_file_not_exist_error(self, mock_rule_manager, mock_verilog_parser):
        """TC-001: 功能点3.1.2- 文件不存在时抛出VCGFileError"""
        from src.vcg_instance_manager import VCGFileError
        
        non_exist_file = '/path/to/nonexistent/file.v'
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.side_effect = FileNotFoundError(
            f"[Errno 2] No such file or directory: '{non_exist_file}'"
        )
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        with pytest.raises(VCGFileError) as exc_info:
            im.generate_instance(non_exist_file, 'test_module', 'u_test')
        
        error_msg = str(exc_info.value)
        assert (non_exist_file in error_msg or 
                'cannot find' in error_msg.lower() or
                'not found' in error_msg.lower())
    
    def test_parse_error_handling(self, mock_rule_manager, mock_verilog_parser):
        """TC-002: 功能点3.1.3 - 文件格式错误处理"""
        from src.vcg_instance_manager import VCGParseError
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = None
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        
        with pytest.raises(VCGParseError):
            im.generate_instance('invalid_file.v', 'test_module', 'u_test')
    
    def test_normal_file_parsing(self, mock_rule_manager, mock_verilog_parser):
        """TC-003: 功能点3.1.1 - 正常文件解析"""
        ports = [MockPortInfo('clk', 'input')]
        mock_ast = MockAST(ports=ports)

        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast  #✅ 直接返回AST
        mock_verilog_parser.return_value = mock_parser_instance

        im = InstanceManager(mock_rule_manager)
        result = im.generate_instance('valid_file.v', 'test_module', 'u_test')

        assert result is not None
        assert 'test_module' in result
        assert 'u_test' in result


# ============================================================================
# 测试类：端口连接生成功能
# ============================================================================

class TestPortConnectionGeneration:
    """测试端口连接生成功能"""
    
    def test_basic_port_connection(self, mock_rule_manager, mock_verilog_parser):
        """TC-004: 功能点3.2.1 - 基本端口连接"""
        ports = [
            MockPortInfo('clk', 'input'),
            MockPortInfo('rst_n', 'input'),
            MockPortInfo('data_out', 'output')
        ]
        mock_ast = MockAST(ports=ports)
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        result = im.generate_instance('test.v', 'test_module', 'u_test')
        
        assert '.clk' in result
        assert '.rst_n' in result
        assert '.data_out' in result
    
    def test_empty_connection_handling(self, mock_verilog_parser):
        """TC-005: 功能点3.2.2 - 空连接处理"""
        signal_map = {'clk': ''}
        rule_manager = MockVCGRuleManager(signal_map=signal_map)
        
        ports = [MockPortInfo('clk', 'input')]
        mock_ast = MockAST(ports=ports)
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(rule_manager)
        result = im.generate_instance('test.v', 'test_module', 'u_test')
        
        assert '.clk' in result
        assert '()' in result
    
    def test_multiple_port_types(self, mock_rule_manager, mock_verilog_parser):
        """TC-006: 功能点3.2.3 - 多类型端口处理"""
        ports = [
            MockPortInfo('clk', 'input'),
            MockPortInfo('data_out', 'output'),
            MockPortInfo('data_io', 'inout')
        ]
        mock_ast = MockAST(ports=ports)
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        result = im.generate_instance('test.v', 'test_module', 'u_test')
        
        assert '// input' in result
        assert '// output' in result
        assert '// inout' in result


# ============================================================================
# 测试类：参数连接生成功能
# ============================================================================

class TestParameterConnectionGeneration:
    """测试参数连接生成功能"""
    
    def test_module_with_parameters(self, mock_verilog_parser):
        """TC-007: 功能点3.3.1 - 有参数模块实例化"""
        param_map = {'WIDTH': '32', 'DEPTH': '16'}
        rule_manager = MockVCGRuleManager(param_map=param_map)
        
        ports = [MockPortInfo('data', 'input')]
        params = [MockParameterInfo('WIDTH'), MockParameterInfo('DEPTH')]
        mock_ast = MockAST(ports=ports, parameters=params)
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(rule_manager)
        result = im.generate_instance('test.v', 'test_module', 'u_test')
        
        assert '#(' in result
        assert '.WIDTH' in result
        assert '.DEPTH' in result
        assert '32' in result
        assert '16' in result
    
    def test_module_without_parameters(self, mock_rule_manager, mock_verilog_parser):
        """TC-008: 功能点3.3.2 - 无参数模块实例化"""
        ports = [MockPortInfo('clk', 'input')]
        mock_ast = MockAST(ports=ports, parameters=[])
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        result = im.generate_instance('test.v', 'test_module', 'u_test')
        
        assert '#(' not in result
    
    def test_partial_parameter_override(self, mock_verilog_parser):
        """TC-009: 功能点3.3.3 - 部分参数覆盖"""
        param_map = {'WIDTH': '32'}
        rule_manager = MockVCGRuleManager(param_map=param_map)
        
        ports = [MockPortInfo('data', 'input')]
        params = [MockParameterInfo('WIDTH'), MockParameterInfo('DEPTH')]
        mock_ast = MockAST(ports=ports, parameters=params)
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(rule_manager)
        result = im.generate_instance('test.v', 'test_module', 'u_test')
        
        assert '.WIDTH' in result
        assert '.DEPTH' not in result


# ============================================================================
# 测试类：代码格式化功能
# ============================================================================

class TestCodeFormatting:
    """测试代码格式化功能"""
    
    def test_alignment_width_setting(self, mock_rule_manager, mock_verilog_parser):
        """TC-010: 功能点3.4.1 - 对齐宽度设置"""
        ports = [MockPortInfo('clk', 'input')]
        mock_ast = MockAST(ports=ports)
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        for align_width in [10, 20, 30]:
            im = InstanceManager(mock_rule_manager)
            im.set_alignment(align_width)
            result = im.generate_instance('test.v', 'test_module', 'u_test')
            
            assert '.clk' in result
            assert im.get_alignment() == align_width
    
    def test_comma_separator_handling(self, mock_rule_manager, mock_verilog_parser):
        """TC-011: 功能点3.4.2 - 逗号分隔符处理"""
        ports = [
            MockPortInfo('port1', 'input'),
            MockPortInfo('port2', 'input'),
            MockPortInfo('port3', 'output')
        ]
        mock_ast = MockAST(ports=ports)
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        result = im.generate_instance('test.v', 'test_module', 'u_test')
        
        lines = result.split('\n')
        port_lines = [l for l in lines if '.port' in l]
        assert len(port_lines) >= 2
    def test_indentation_handling(self, mock_rule_manager, mock_verilog_parser):
        """TC-012: 功能点3.4.3 - 缩进处理"""
        ports = [MockPortInfo('clk', 'input')]
        params = [MockParameterInfo('WIDTH')]
        mock_ast = MockAST(ports=ports, parameters=params)
        
        param_map = {'WIDTH': '8'}
        rule_manager = MockVCGRuleManager(param_map=param_map)
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(rule_manager)
        result = im.generate_instance('test.v', 'test_module', 'u_test')
        
        lines = result.split('\n')
        for line in lines:
            if '.WIDTH' in line or '.clk' in line:
                assert line.startswith('    ')


# ============================================================================
# 测试类：端口注释生成功能
# ============================================================================

class TestPortCommentGeneration:
    """测试端口注释生成功能"""
    
    def test_basic_direction_comment(self, mock_rule_manager, mock_verilog_parser):
        """TC-013: 功能点3.5.1 - 基本方向注释"""
        ports = [
            MockPortInfo('clk', 'input'),
            MockPortInfo('data_out', 'output')
        ]
        mock_ast = MockAST(ports=ports)
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        result = im.generate_instance('test.v', 'test_module', 'u_test')
        
        assert '// input' in result
        assert '// output' in result
    
    def test_no_direction_port(self, mock_rule_manager, mock_verilog_parser):
        """TC-014: 功能点3.5.2 - 无方向端口"""
        ports = [MockPortInfo('signal', direction='')]
        mock_ast = MockAST(ports=ports)
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        result = im.generate_instance('test.v', 'test_module', 'u_test')
        
        lines = result.split('\n')
        signal_line = [l for l in lines if '.signal' in l]
        assert len(signal_line) > 0
    
    def test_net_type_comment(self, mock_rule_manager, mock_verilog_parser):
        """TC-015: 功能点3.5.3 - net_type注释"""
        ports = [
            MockPortInfo('reg_signal', 'input', net_type='reg'),
            MockPortInfo('wire_signal', 'input', net_type='wire'),
            MockPortInfo('normal_signal', 'input', net_type=None)
        ]
        mock_ast = MockAST(ports=ports)
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        result = im.generate_instance('test.v', 'test_module', 'u_test')
        
        assert'reg' in result.lower()
    
    def test_range_string_comment(self, mock_rule_manager, mock_verilog_parser):
        """TC-016: 功能点3.5.4 - range_string注释"""
        ports = [
            MockPortInfo('data', 'input', range_string='[7:0]'),
            MockPortInfo('addr', 'input', range_string='[31:0]')
        ]
        mock_ast = MockAST(ports=ports)
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        result = im.generate_instance('test.v', 'test_module', 'u_test')
        
        assert '[7:0]' in result
        assert '[31:0]' in result
    
    #def test_interface_type_port(self, mock_rule_manager, mock_verilog_parser):
    #    """TC-017: 功能点3.5.5 - INTERFACE类型端口"""
    #    ports = [
    #        MockPortInfo('axi_if', 'input', port_type='INTERFACE',
    #                    interface_type='axi4_lite')
    #    ]
    #    mock_ast = MockAST(ports=ports)
    #    
    #    mock_parser_instance = Mock()
    #    mock_parser_instance.parse_file.return_value = mock_ast
    #    mock_verilog_parser.return_value = mock_parser_instance
    #    
    #    im = InstanceManager(mock_rule_manager)
    #    result = im.generate_instance('test.v', 'test_module', 'u_test')
    #    
    #    assert '<' in result and '>' in result
    #    assert 'axi4_lite' in result
    #
    #def test_array_port_comment(self, mock_rule_manager, mock_verilog_parser):
    #    """TC-018: 功能点3.5.6 - 数组端口注释"""
    #    ports = [
    #        MockPortInfo('array_2d', 'input', port_type='ARRAY_2D'),
    #        MockPortInfo('array_3d', 'input', port_type='ARRAY_3D'),
    #        MockPortInfo('normal', 'input', port_type='NORMAL')
    #    ]
    #    mock_ast = MockAST(ports=ports)
    #    
    #    mock_parser_instance = Mock()
    #    mock_parser_instance.parse_file.return_value = mock_ast
    #    mock_verilog_parser.return_value = mock_parser_instance
    #    
    #    im = InstanceManager(mock_rule_manager)
    #    result = im.generate_instance('test.v', 'test_module', 'u_test')
    #    
    #    lines = result.split('\n')
    #    array_2d_lines = [l for l in lines if'array_2d' in l]
    #    array_3d_lines = [l for l in lines if 'array_3d' in l]
    #    if array_2d_lines:
    #        assert '[ARRAY]' in array_2d_lines[0]
    #    if array_3d_lines:
    #        assert '[ARRAY]' in array_3d_lines[0]
    #
    #def test_combined_comment(self, mock_rule_manager, mock_verilog_parser):
    #    """TC-019: 功能点3.5.7 - 组合注释"""
    #    ports = [
    #        MockPortInfo('complex_port', 'input', net_type='reg',
    #                    range_string='[15:0]', port_type='ARRAY_2D')
    #    ]
    #    mock_ast = MockAST(ports=ports)
    #    
    #    mock_parser_instance = Mock()
    #    mock_parser_instance.parse_file.return_value = mock_ast
    #    mock_verilog_parser.return_value = mock_parser_instance
    #    
    #    im = InstanceManager(mock_rule_manager)
    #    result = im.generate_instance('test.v', 'test_module', 'u_test')
    #    
    #    lines = result.split('\n')
    #    complex_line = [l for l in lines if 'complex_port' in l][0]
    #    
    #    assert '// input' in complex_line
    #    assert 'reg' in complex_line
    #    assert '[15:0]' in complex_line
    #    assert '[ARRAY]' in complex_line


# ============================================================================
# 测试类：边界条件测试
# ============================================================================

class TestBoundaryConditions:
    """测试边界条件"""
    
    def test_empty_module(self, mock_rule_manager, mock_verilog_parser):
        """TC-020: 空模块（无端口无参数）"""
        mock_ast = MockAST(ports=[], parameters=[])
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        result = im.generate_instance('test.v', 'empty_module', 'u_empty')
        
        assert 'empty_module' in result
        assert 'u_empty' in result
    
    def test_single_port_module(self, mock_rule_manager, mock_verilog_parser):
        """TC-021: 单端口模块"""
        ports = [MockPortInfo('single_port', 'input')]
        mock_ast = MockAST(ports=ports)
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        result = im.generate_instance('test.v', 'test_module', 'u_test')
        
        assert '.single_port' in result
    
    def test_large_module(self, mock_rule_manager, mock_verilog_parser):
        """TC-022: 大型模块（100+端口）"""
        ports = [MockPortInfo(f'port_{i}', 'input') for i in range(100)]
        mock_ast = MockAST(ports=ports)
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        result = im.generate_instance('test.v', 'large_module', 'u_large')
        
        for i in range(100):
            assert f'.port_{i}' in result
    
    def test_alignment_boundary_values(self, mock_rule_manager, mock_verilog_parser):
        """TC-023: 对齐宽度边界值"""
        ports = [MockPortInfo('test', 'input')]
        mock_ast = MockAST(ports=ports)
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        
        for align_val in [1, 0, 100]:
            im.set_alignment(align_val)
            try:
                result = im.generate_instance('test.v', 'test_module', 'u_test')
                assert result is not None
            except Exception as e:
                if align_val <= 0:
                    pass
                else:
                    raise
    
    def test_long_module_name(self, mock_rule_manager, mock_verilog_parser):
        """TC-024: 超长模块名"""
        long_name = 'a' * 100
        ports = [MockPortInfo('clk', 'input')]
        mock_ast = MockAST(ports=ports)
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        result = im.generate_instance('test.v', long_name, 'u_test')
        
        assert long_name in result
    
    def test_empty_string_parameters(self, mock_rule_manager, mock_verilog_parser):
        """TC-025: 空字符串参数"""
        from src.vcg_instance_manager import VCGParseError
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = None
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        
        with pytest.raises((VCGParseError, Exception)):
            im.generate_instance('', 'module', 'inst')


# ============================================================================
# 测试类：异常处理测试
# ============================================================================

class TestExceptionHandling:
    """测试异常处理"""
    
    def test_vcg_file_error_exception(self, mock_rule_manager, mock_verilog_parser):
        """TC-026: VCGFileError异常"""
        from src.vcg_instance_manager import VCGFileError
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.side_effect = FileNotFoundError("File not found")
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        
        with pytest.raises(VCGFileError) as exc_info:
            im.generate_instance('missing.v', 'test', 'u_test')
        
        assert 'not found' in str(exc_info.value).lower() or 'missing.v' in str(exc_info.value)
    
    def test_vcg_parse_error_exception(self, mock_rule_manager, mock_verilog_parser):
        """TC-027: VCGParseError异常"""
        from src.vcg_instance_manager import VCGParseError
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = None
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        
        with pytest.raises(VCGParseError):
            im.generate_instance('bad.v', 'test', 'u_test')
    
    def test_unexpected_exception_handling(self, mock_rule_manager, mock_verilog_parser):
        """TC-028: 未预期错误转换"""
        from src.vcg_instance_manager import VCGParseError
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.side_effect = RuntimeError("Unexpected error")
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        
        with pytest.raises((VCGParseError, RuntimeError)):
            im.generate_instance('test.v', 'test', 'u_test')


# ============================================================================
# 测试类：完整场景测试
# ============================================================================

class TestCompleteScenarios:
    """测试完整场景"""
    
    def test_simple_module_scenario(self, mock_rule_manager, mock_verilog_parser):
        """TC-029: 简单模块完整场景"""
        ports = [
            MockPortInfo('clk', 'input'),
            MockPortInfo('rst_n', 'input'),
            MockPortInfo('data_in', 'input', range_string='[7:0]'),
            MockPortInfo('data_out', 'output', range_string='[7:0]')
        ]
        mock_ast = MockAST(ports=ports, parameters=[])
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        result = im.generate_instance('simple.v', 'simple_module', 'u_simple')
        
        assert 'simple_module' in result
        assert 'u_simple' in result
        assert '.clk' in result
        assert '.rst_n' in result
        assert '.data_in' in result
        assert '.data_out' in result
        assert '// input' in result
        assert '// output' in result
        assert '[7:0]' in result
    def test_parameterized_module_scenario(self, mock_verilog_parser):
        """TC-030: 带参数模块完整场景"""
        param_map = {'WIDTH': '16', 'DEPTH': '256'}
        signal_map = {'clk': 'sys_clk', 'data': 'bus_data'}
        rule_manager = MockVCGRuleManager(signal_map=signal_map, param_map=param_map)
        
        ports = [
            MockPortInfo('clk', 'input'),
            MockPortInfo('data', 'input', range_string='[WIDTH-1:0]')
        ]
        params = [
            MockParameterInfo('WIDTH'),
            MockParameterInfo('DEPTH')
        ]
        mock_ast = MockAST(ports=ports, parameters=params)
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(rule_manager)
        result = im.generate_instance('param.v', 'param_module', 'u_param')
        
        assert '#(' in result
        assert '.WIDTH' in result
        assert '.DEPTH' in result
        assert '16' in result
        assert '256' in result
        assert 'sys_clk' in result
        assert 'bus_data' in result
    
    def test_complex_module_scenario(self, mock_rule_manager, mock_verilog_parser):
        """TC-031: 复杂模块完整场景"""
        ports = [
            MockPortInfo('clk', 'input'),
            MockPortInfo('data', 'input', range_string='[31:0]', net_type='reg'),
            MockPortInfo('valid', 'input'),
            MockPortInfo('ready', 'output'),
            MockPortInfo('addr', 'output', range_string='[15:0]'),
            MockPortInfo('error', 'output', net_type='reg')
        ]
        params = [MockParameterInfo('BUS_WIDTH')]
        mock_ast = MockAST(ports=ports, parameters=params)

        param_map = {'BUS_WIDTH': '64'}
        rule_manager = MockVCGRuleManager(param_map=param_map)

        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance

        im = InstanceManager(rule_manager)
        im.set_alignment(25)
        result = im.generate_instance('complex.v', 'complex_module', 'u_complex')

        # 验证参数
        assert '#(' in result
        assert '.BUS_WIDTH' in result
        assert '64' in result

        # 验证所有端口
        assert '.clk' in result
        assert '.data' in result
        assert '.valid' in result
        assert '.ready' in result
        assert '.addr' in result
        assert '.error' in result

        # 验证位宽信息
        assert '[31:0]' in result
        assert '[15:0]' in result
        # 验证net_type
        assert 'reg' in result

        # 验证方向注释
        assert '// input' in result
        assert '// output' in result


# ============================================================================
# 测试类：输出格式验证
# ============================================================================

class TestOutputFormat:
    """测试输出格式规范"""
    
    def test_output_format_without_parameters(self, mock_rule_manager, mock_verilog_parser):
        """TC-032: 验证无参数模块输出格式"""
        ports = [
            MockPortInfo('port1', 'input', range_string='[7:0]'),
            MockPortInfo('port2', 'output')
        ]
        mock_ast = MockAST(ports=ports, parameters=[])
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(mock_rule_manager)
        result = im.generate_instance('test.v', 'test_module', 'inst_name')
        
        assert 'test_module' in result
        assert 'inst_name' in result
        assert '.port1' in result
        assert '.port2' in result
        assert ');' in result
    
    def test_output_format_with_parameters(self, mock_verilog_parser):
        """TC-033: 验证有参数模块输出格式"""
        param_map = {'PARAM1': 'value1', 'PARAM2': 'value2'}
        rule_manager = MockVCGRuleManager(param_map=param_map)
        
        ports = [MockPortInfo('port1', 'input')]
        params = [MockParameterInfo('PARAM1'), MockParameterInfo('PARAM2')]
        mock_ast = MockAST(ports=ports, parameters=params)
        
        mock_parser_instance = Mock()
        mock_parser_instance.parse_file.return_value = mock_ast
        mock_verilog_parser.return_value = mock_parser_instance
        
        im = InstanceManager(rule_manager)
        result = im.generate_instance('test.v', 'test_module', 'inst_name')
        
        assert 'test_module #(' in result
        assert '.PARAM1' in result
        assert '.PARAM2' in result
        assert ') inst_name (' in result


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])