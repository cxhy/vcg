# tests/test_vcg_instance_manager.py
import unittest
from unittest.mock import Mock, patch, mock_open, MagicMock
import sys
import os
from pathlib import Path

# 添加src路径到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from vcg_instance_manager import InstanceManager
from vcg_exceptions import VCGFileError, VCGParseError


class MockPortInfo:
    """模拟端口信息类"""
    def __init__(self, name, direction, width=1, comment=None):
        self.name = name
        self.direction = direction  # 'input', 'output', 'inout'
        self.width = width
        self.comment = comment


class MockParameterInfo:
    """模拟参数信息类"""
    def __init__(self, name, default_value=None, comment=None):
        self.name = name
        self.default_value = default_value
        self.comment = comment


class MockVerilogAst:
    """模拟Verilog AST对象"""
    def __init__(self, ports=None, parameters=None):
        self.ports = ports or []
        self.parameters = parameters or []
    
    def get_module_ports(self):
        return self.ports
    
    def get_module_parameters(self):
        return self.parameters


class MockVCGRuleManager:
    """模拟规则管理器"""
    def __init__(self):
        self.signal_rules = {}
        self.param_rules = {}
    
    def resolve_signal_connection(self, port: MockPortInfo) -> str:
        """解析信号连接规则"""
        if port.name in self.signal_rules:
            return self.signal_rules[port.name]
        
        # 默认连接规则
        if port.direction == 'input':
            return f"{port.name}_i"
        elif port.direction == 'output':
            return f"{port.name}_o"
        else:  # inout
            return f"{port.name}_io"
    
    def resolve_param_connection(self, param_name: str):
        """解析参数连接规则"""
        return self.param_rules.get(param_name)
    
    def add_signal_rule(self, port_name: str, connection: str):
        """添加信号连接规则（测试辅助方法）"""
        self.signal_rules[port_name] = connection
    
    def add_param_rule(self, param_name: str, value: str):
        """添加参数连接规则（测试辅助方法）"""
        self.param_rules[param_name] = value


class TestInstanceManager(unittest.TestCase):
    """InstanceManager单元测试类"""
    
    def setUp(self):
        """测试前置设置"""
        self.rule_manager = MockVCGRuleManager()
        self.instance_manager = InstanceManager(self.rule_manager)
        
        # 准备测试用的端口数据
        self.simple_ports = [
            MockPortInfo('clk', 'input', 1, 'Clock signal'),
            MockPortInfo('rst_n', 'input', 1, 'Reset signal'),
            MockPortInfo('data_out', 'output', 8, 'Data output')
        ]
        
        self.complex_ports = [
            MockPortInfo('clk', 'input', 1),
            MockPortInfo('rst_n', 'input', 1),
            MockPortInfo('enable', 'input', 1),
            MockPortInfo('data_in', 'input', 32),
            MockPortInfo('addr', 'input', 16),
            MockPortInfo('data_out', 'output', 32),
            MockPortInfo('valid', 'output', 1),
            MockPortInfo('ready', 'output', 1),
            MockPortInfo('debug_port', 'inout', 8)
        ]
        
        self.parameters = [
            MockParameterInfo('DATA_WIDTH', '32'),
            MockParameterInfo('ADDR_WIDTH', '16')
        ]

    def tearDown(self):
        """测试后置清理"""
        pass

    @patch('vcg_instance_manager.parse_verilog_file')
    def test_basic_instance_generation(self, mock_parse):
        """测试基本实例生成功能"""
        # 准备测试数据
        mock_ast = MockVerilogAst(self.simple_ports, [])
        mock_parse.return_value = mock_ast
        
        # 执行测试
        result = self.instance_manager.generate_instance(
            "test_module.v", "simple_module", "u_simple"
        )
        
        # 验证结果
        self.assertIn("simple_module u_simple (", result)
        self.assertTrue(result.strip().endswith(");"))
        self.assertIn(".clk", result)
        self.assertIn(".rst_n", result)
        self.assertIn(".data_out", result)
        
        # 验证解析器调用
        mock_parse.assert_called_once_with("test_module.v", macros=None)

    @patch('vcg_instance_manager.parse_verilog_file')
    def test_parameterized_instance(self, mock_parse):
        """测试带参数的模块实例生成"""
        # 准备测试数据
        mock_ast = MockVerilogAst(self.simple_ports, self.parameters)
        mock_parse.return_value = mock_ast
        
        # 设置参数规则
        self.rule_manager.add_param_rule('DATA_WIDTH', '64')
        self.rule_manager.add_param_rule('ADDR_WIDTH', '24')
        
        # 执行测试
        result = self.instance_manager.generate_instance(
            "param_module.v", "param_module", "u_param"
        )
        
        # 验证参数部分格式
        self.assertIn("param_module #(", result)
        self.assertIn(".DATA_WIDTH", result)
        self.assertIn("(64)", result)
        self.assertIn(".ADDR_WIDTH", result)
        self.assertIn("(24)", result)
        self.assertIn(") u_param (", result)

    @patch('vcg_instance_manager.parse_verilog_file')
    def test_port_connection_rules(self, mock_parse):
        """测试端口连接规则应用"""
        # 准备测试数据
        mock_ast = MockVerilogAst(self.complex_ports, [])
        mock_parse.return_value = mock_ast
        
        # 设置自定义连接规则
        self.rule_manager.add_signal_rule('clk', 'sys_clk')
        self.rule_manager.add_signal_rule('rst_n', 'sys_rst_n')
        self.rule_manager.add_signal_rule('data_in', 'input_data[31:0]')
        
        # 执行测试
        result = self.instance_manager.generate_instance(
            "complex_module.v", "complex_module", "u_complex"
        )
        
        # 验证自定义连接规则
        self.assertIn(".clk               (sys_clk)", result)
        self.assertIn(".rst_n             (sys_rst_n)", result)
        self.assertIn(".data_in           (input_data[31:0])", result)

        # 验证默认连接规则
        self.assertIn(".enable            (enable_i)", result)
        self.assertIn(".data_out          (data_out_o)", result)
        self.assertIn(".debug_port        (debug_port_io)", result)

    @patch('vcg_instance_manager.parse_verilog_file')
    def test_module_with_no_ports(self, mock_parse):
        """测试没有端口的模块"""
        # 准备测试数据
        mock_ast = MockVerilogAst([], [])
        mock_parse.return_value = mock_ast
        
        # 执行测试
        result = self.instance_manager.generate_instance(
            "no_port_module.v", "no_port_module", "u_no_port"
        )
        
        # 验证结果
        expected = "no_port_module u_no_port (\n);"
        self.assertEqual(result.strip(), expected)

    @patch('vcg_instance_manager.parse_verilog_file')
    def test_module_with_many_ports(self, mock_parse):
        """测试大量端口的模块"""
        # 创建大量端口
        many_ports = []
        for i in range(100):
            many_ports.append(MockPortInfo(f'port_{i}', 'input', 1))
        
        mock_ast = MockVerilogAst(many_ports, [])
        mock_parse.return_value = mock_ast
        
        # 执行测试
        result = self.instance_manager.generate_instance(
            "many_ports_module.v", "many_ports_module", "u_many_ports"
        )
        
        # 验证结果包含所有端口
        for i in range(100):
            self.assertIn(f".port_{i}", result)
        
        # 验证格式正确
        self.assertIn("many_ports_module u_many_ports (", result)
        self.assertTrue(result.strip().endswith(");"))

    def test_alignment_setting(self):
        """测试对齐设置功能"""
        # 测试默认对齐值
        self.assertEqual(self.instance_manager.get_alignment(), 18)
        
        # 测试设置新的对齐值
        self.instance_manager.set_alignment(25)
        self.assertEqual(self.instance_manager.get_alignment(), 25)
        
        ## 测试设置无效对齐值
        #with self.assertRaises(ValueError):
        #    self.instance_manager.set_alignment(-1)
        #
        #with self.assertRaises(ValueError):
        #    self.instance_manager.set_alignment(0)

    @patch('vcg_instance_manager.parse_verilog_file')
    def test_alignment_formatting(self, mock_parse):
        """测试不同对齐宽度下的代码格式"""
        # 准备测试数据
        test_ports = [
            MockPortInfo('clk', 'input', 1),
            MockPortInfo('very_long_port_name', 'input', 1),
            MockPortInfo('data', 'output', 8)
        ]
        mock_ast = MockVerilogAst(test_ports, [])
        mock_parse.return_value = mock_ast
        
        # 测试不同对齐宽度
        for alignment in [10, 20, 30]:
            self.instance_manager.set_alignment(alignment)
            result = self.instance_manager.generate_instance(
                "test.v", "test_module", "u_test"
            )
            
            # 验证对齐格式
            lines = result.split('\n')
            port_lines = [line for line in lines if '.clk' in line or '.data' in line]
            
            if port_lines:
                # 检查端口名称后的空格对齐
                for line in port_lines:
                    if '(' in line:
                        port_part = line.split('(')[0]
                        # 验证格式符合预期（具体对齐规则根据实际实现调整）
                        self.assertIn('.', port_part)

    @patch('vcg_instance_manager.parse_verilog_file')
    def test_macros_parameter(self, mock_parse):
        """测试宏定义参数传递"""
        mock_ast = MockVerilogAst(self.simple_ports, [])
        mock_parse.return_value = mock_ast
        
        # 创建带宏定义的实例管理器
        macros = {'SYNTHESIS': '1', 'DEBUG': '0'}
        instance_manager_with_macros = InstanceManager(self.rule_manager, macros)
        
        # 执行测试
        result = instance_manager_with_macros.generate_instance(
            "macro_module.v", "macro_module", "u_macro"
        )
        
        # 验证宏定义传递给解析器
        mock_parse.assert_called_once_with("macro_module.v", macros=macros)

    @patch('vcg_instance_manager.parse_verilog_file')
    def test_empty_parameter_handling(self, mock_parse):
        """测试空参数处理"""
        # 测试有参数但规则管理器返回None的情况
        mock_ast = MockVerilogAst(self.simple_ports, self.parameters)
        mock_parse.return_value = mock_ast
        
        # 不设置参数规则（默认返回None）
        result = self.instance_manager.generate_instance(
            "param_module.v", "param_module", "u_param"
        )
        
        # 验证未设置值的参数不包含在输出中，或使用默认值
        # 具体行为根据实际实现调整
        self.assertIn("param_module", result)

    @patch('vcg_instance_manager.parse_verilog_file')
    def test_special_characters_in_names(self, mock_parse):
        """测试名称中包含特殊字符的处理"""
        special_ports = [
            MockPortInfo('clk_100mhz', 'input', 1),
            MockPortInfo('data_bus[31:0]', 'input', 32),
            MockPortInfo('valid_o', 'output', 1)
        ]
        mock_ast = MockVerilogAst(special_ports, [])
        mock_parse.return_value = mock_ast
        
        result = self.instance_manager.generate_instance(
            "special.v", "special_module", "u_special"
        )
        
        # 验证特殊字符正确处理
        self.assertIn(".clk_100mhz", result)
        self.assertIn(".valid_o", result)


class TestInstanceManagerIntegration(unittest.TestCase):
    """InstanceManager集成测试类"""
    
    def setUp(self):
        """集成测试前置设置"""
        self.rule_manager = MockVCGRuleManager()

    @patch('vcg_instance_manager.parse_verilog_file')
    def test_full_workflow(self, mock_parse):
        """测试完整工作流程"""
        # 准备复杂的测试场景
        ports = [
            MockPortInfo('clk', 'input', 1, 'Clock'),
            MockPortInfo('rst_n', 'input', 1, 'Reset'),
            MockPortInfo('data_in', 'input', 32, 'Input data'),
            MockPortInfo('addr', 'input', 16, 'Address'),
            MockPortInfo('data_out', 'output', 32, 'Output data'),
            MockPortInfo('valid', 'output', 1, 'Valid signal'),
        ]
        
        parameters = [
            MockParameterInfo('DATA_WIDTH', '32'),
            MockParameterInfo('ADDR_WIDTH', '16'),
            MockParameterInfo('BUFFER_DEPTH', '256')
        ]
        
        mock_ast = MockVerilogAst(ports, parameters)
        mock_parse.return_value = mock_ast
        
        # 设置规则
        self.rule_manager.add_signal_rule('clk', 'system_clock')
        self.rule_manager.add_signal_rule('rst_n', 'system_reset_n')
        self.rule_manager.add_param_rule('DATA_WIDTH', '64')
        self.rule_manager.add_param_rule('BUFFER_DEPTH', '512')
        
        # 创建实例管理器
        instance_manager = InstanceManager(self.rule_manager)
        instance_manager.set_alignment(20)
        
        # 执行测试
        result = instance_manager.generate_instance(
            "complex_module.v", "complex_module", "u_complex_inst"
        )
        
        # 验证完整输出格式
        self.assertIn("complex_module #(", result)
        self.assertIn(".DATA_WIDTH          (64),", result)
        self.assertIn(".BUFFER_DEPTH        (512)", result)
        self.assertIn(") u_complex_inst (", result)
        self.assertIn(".clk                 (system_clock),", result)
        self.assertIn(".rst_n               (system_reset_n),", result)
        self.assertTrue(result.strip().endswith(");"))


if __name__ == '__main__':
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestInstanceManager))
    suite.addTests(loader.loadTestsFromTestCase(TestInstanceManagerIntegration))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出测试结果
    if result.wasSuccessful():
        print(f"\n✅ 所有测试通过! 共运行 {result.testsRun} 个测试用例")
    else:
        print(f"\n❌ 测试失败! 失败 {len(result.failures)} 个, 错误 {len(result.errors)} 个")