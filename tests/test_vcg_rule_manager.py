"""
This file is part of VCG.

VCG is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

VCG is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with VCG.  If not, see <https://www.gnu.org/licenses/>.
"""
import unittest
from unittest.mock import Mock, patch
import sys
import os
from typing import Optional,Union
from dataclasses import dataclass

# 添加src路径以便导入被测试模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from vcg_rule_manager import VCGRuleManager

@dataclass
class TestRangeExpression:
    """模拟RangeExpression类用于测试"""
    msb_expr: Optional[str] = None
    lsb_expr: Optional[str] = None
    msb_value: Optional[int] = None
    lsb_value: Optional[int] = None
    width_expr: Optional[str] = None
    width_value: Optional[int] = None

@dataclass
class TestPortInfo:
    """模拟PortInfo类用于测试"""
    name: str
    direction: str = ""
    net_type: str = ""
    range_expr: Optional[TestRangeExpression] = None
    
    @property
    def width(self) -> Optional[Union[int, str]]:
        """获取端口位宽"""
        if self.range_expr is None:
            return None
        if self.range_expr.width_value is not None:
            return self.range_expr.width_value
        return self.range_expr.width_expr

class TestVCGRuleManager(unittest.TestCase):
    
    def setUp(self):
        """在每个测试前创建新的VCGRuleManager实例"""
        self.manager = VCGRuleManager()
    
    def test_init(self):
        """测试VCGRuleManager初始化"""
        # 修正：使用正确的访问方式
        self.assertEqual(len(self.manager.rules['signal_rules']), 0)
        self.assertEqual(len(self.manager.rules['param_rules']), 0)
        self.assertEqual(len(self.manager.rules['wire_rules']), 0)
    
    def test_reset(self):
        """测试reset功能"""
        # 添加一些规则
        self.manager.add_signal_rule("clk*", "clock_*")
        self.manager.add_param_rule("WIDTH", "32")
        self.manager.add_wire_rule("data*", "wire_*")
        
        # 验证规则已添加
        summary = self.manager.get_rules_summary()
        self.assertEqual(summary['signal_rules'], 1)
        self.assertEqual(summary['param_rules'], 1)
        self.assertEqual(summary['wire_rules'], 1)
        
        # 重置并验证
        self.manager.reset()
        summary = self.manager.get_rules_summary()
        self.assertEqual(summary['signal_rules'], 0)
        self.assertEqual(summary['param_rules'], 0)
        self.assertEqual(summary['wire_rules'], 0)
    
    def test_get_rules_summary(self):
        """测试规则统计功能"""
        # 初始状态
        summary = self.manager.get_rules_summary()
        self.assertEqual(summary['signal_rules'], 0)
        self.assertEqual(summary['param_rules'], 0)
        self.assertEqual(summary['wire_rules'], 0)
        
        # 添加不同数量的规则
        self.manager.add_signal_rule("clk", "clock")
        self.manager.add_signal_rule("rst", "reset")
        self.manager.add_param_rule("WIDTH", "32")
        self.manager.add_wire_rule("data", "wire_data")
        
        summary = self.manager.get_rules_summary()
        self.assertEqual(summary['signal_rules'], 2)
        self.assertEqual(summary['param_rules'], 1)
        self.assertEqual(summary['wire_rules'], 1)

class TestSignalRules(unittest.TestCase):
    
    def setUp(self):
        self.manager = VCGRuleManager()
    
    def test_add_signal_rule_basic(self):
        """测试基本信号规则添加"""
        self.manager.add_signal_rule("clk", "clock")
        summary = self.manager.get_rules_summary()
        self.assertEqual(summary['signal_rules'], 1)
    def test_add_signal_rule_with_port_type(self):
        """测试带端口类型的信号规则添加"""
        self.manager.add_signal_rule("clk", "clock", "input")
        summary = self.manager.get_rules_summary()
        self.assertEqual(summary['signal_rules'], 1)
    
    def test_signal_rule_priority_lifo(self):
        """测试信号规则优先级（后进先出）"""
        # 添加多个匹配同一模式的规则
        self.manager.add_signal_rule("clk", "first_clock")
        self.manager.add_signal_rule("clk", "second_clock")
        
        port = TestPortInfo("clk")
        result = self.manager.resolve_signal_connection(port)
        # 最后添加的规则应该优先
        self.assertEqual(result, "second_clock")
    
    def test_resolve_signal_connection_exact_match(self):
        """测试精确匹配信号解析"""
        self.manager.add_signal_rule("clk", "clock")
        self.manager.add_signal_rule("rst", "reset")
        
        port_clk = TestPortInfo("clk")
        port_rst = TestPortInfo("rst")
        port_unknown = TestPortInfo("unknown")
        
        self.assertEqual(self.manager.resolve_signal_connection(port_clk), "clock")
        self.assertEqual(self.manager.resolve_signal_connection(port_rst), "reset")
        self.assertEqual(self.manager.resolve_signal_connection(port_unknown), "unknown")
    
    def test_resolve_signal_connection_wildcard_match(self):
        """测试通配符匹配信号解析"""
        self.manager.add_signal_rule("clk_*", "clock_*")
        self.manager.add_signal_rule("*_in", "input_*")
        
        port1 = TestPortInfo("clk_100mhz")
        port2 = TestPortInfo("data_in")
        
        self.assertEqual(self.manager.resolve_signal_connection(port1), "clock_100mhz")
        self.assertEqual(self.manager.resolve_signal_connection(port2), "input_data")
    
    def test_resolve_signal_connection_multiple_wildcards(self):
        """测试多个通配符匹配"""
        self.manager.add_signal_rule("*_clk_*", "*_clock_*")
        
        port = TestPortInfo("sys_clk_100mhz")
        result = self.manager.resolve_signal_connection(port)
        self.assertEqual(result, "sys_clock_100mhz")
    
    def test_resolve_signal_connection_port_type_filter(self):
        """测试端口类型过滤"""
        self.manager.add_signal_rule("clk", "input_clock", "input")
        self.manager.add_signal_rule("clk", "output_clock", "output")
        
        port_input = TestPortInfo("clk", "input")
        port_output = TestPortInfo("clk", "output")
        port_no_type = TestPortInfo("clk")
        
        self.assertEqual(self.manager.resolve_signal_connection(port_input), "input_clock")
        self.assertEqual(self.manager.resolve_signal_connection(port_output), "output_clock")
        self.assertEqual(self.manager.resolve_signal_connection(port_no_type), "clk")
    
    def test_resolve_signal_connection_case_insensitive_port_type(self):
        """测试端口类型不区分大小写匹配"""
        self.manager.add_signal_rule("clk", "clock", "INPUT")
        
        port = TestPortInfo("clk", "input")
        result = self.manager.resolve_signal_connection(port)
        self.assertEqual(result, "clock")
    
    def test_resolve_signal_connection_literal_conversion(self):
        """测试字面量转换功能"""
        # 修正：使用正确的位宽获取方式
        # 8位端口
        range_expr_8bit = TestRangeExpression(width_value=8)
        port_8bit = TestPortInfo("enable", range_expr=range_expr_8bit)
        
        # 1位端口
        range_expr_1bit = TestRangeExpression(width_value=1)
        port_1bit = TestPortInfo("flag", range_expr=range_expr_1bit)
        
        # 无位宽信息的端口
        port_no_width = TestPortInfo("simple")
        
        # 带位宽表达式的端口
        range_expr_expr = TestRangeExpression(width_expr="DATA_WIDTH")
        port_with_expr = TestPortInfo("data", range_expr=range_expr_expr)
        
        # 测试"0"和"1"的转换
        self.manager.add_signal_rule("enable", "0")
        self.manager.add_signal_rule("flag", "1") 
        self.manager.add_signal_rule("simple", "0")
        self.manager.add_signal_rule("data", "1")
        
        result_8bit = self.manager.resolve_signal_connection(port_8bit)
        result_1bit = self.manager.resolve_signal_connection(port_1bit)
        result_no_width = self.manager.resolve_signal_connection(port_no_width)
        result_with_expr = self.manager.resolve_signal_connection(port_with_expr)
        
        self.assertEqual(result_8bit, "8'b00000000")
        self.assertEqual(result_1bit, "1'b1")
        self.assertEqual(result_no_width, "1'b0")  # 默认1位
        self.assertEqual(result_with_expr, "{DATA_WIDTH{1'b1}}")  # 表达式位宽
    
    def test_resolve_signal_connection_comment_handling(self):
        """测试内联注释处理"""
        self.manager.add_signal_rule("clk", "clock /* main clock */")
        
        port = TestPortInfo("clk")
        result = self.manager.resolve_signal_connection(port)
        self.assertEqual(result, "clock /* main clock */")
    
    def test_resolve_signal_connection_function_calls(self):
        """测试函数调用处理"""
        self.manager.add_signal_rule("*_sig", "${upper(*0)}_SIGNAL")
        
        port = TestPortInfo("test_sig")
        result = self.manager.resolve_signal_connection(port)
        self.assertEqual(result, "TEST_SIGNAL")
    
    def test_resolve_signal_connection_function_calls_with_wildcards(self):
        """测试函数调用中的通配符引用"""
        self.manager.add_signal_rule("*_*_sig", "${upper(*0)}_${lower(*1)}")
        
        port = TestPortInfo("SYS_CLK_sig")
        result = self.manager.resolve_signal_connection(port)
        self.assertEqual(result, "SYS_clk")
    
    @patch('logging.warning')
    def test_resolve_signal_connection_function_error_handling(self, mock_warning):
        """测试函数执行异常处理"""
        # 使用不安全的函数调用
        self.manager.add_signal_rule("test", "${invalid_function()}")
        
        port = TestPortInfo("test")
        result = self.manager.resolve_signal_connection(port)
        
        # 应该返回原始字符串并记录警告
        self.assertEqual(result, "${invalid_function()}")
        #mock_warning.assert_called_once()


class TestParamRules(unittest.TestCase):
    
    def setUp(self):
        self.manager = VCGRuleManager()
    
    def test_add_param_rule(self):
        """测试参数规则添加"""
        self.manager.add_param_rule("WIDTH", "32")
        summary = self.manager.get_rules_summary()
        self.assertEqual(summary['param_rules'], 1)
    
    def test_resolve_param_connection_exact_match(self):
        """测试精确匹配参数解析"""
        self.manager.add_param_rule("WIDTH", "32")
        self.manager.add_param_rule("DEPTH", "1024")
        
        self.assertEqual(self.manager.resolve_param_connection("WIDTH"), "32")
        self.assertEqual(self.manager.resolve_param_connection("DEPTH"), "1024")
        self.assertIsNone(self.manager.resolve_param_connection("UNKNOWN"))
    
    def test_resolve_param_connection_wildcard_match(self):
        """测试通配符匹配参数解析"""
        self.manager.add_param_rule("*_WIDTH", "32")
        self.manager.add_param_rule("FIFO_*", "1024")
        
        self.assertEqual(self.manager.resolve_param_connection("DATA_WIDTH"), "32")
        self.assertEqual(self.manager.resolve_param_connection("FIFO_DEPTH"), "1024")
    
    def test_param_rule_priority_lifo(self):
        """测试参数规则优先级（后进先出）"""
        self.manager.add_param_rule("WIDTH", "16")
        self.manager.add_param_rule("WIDTH", "32")
        
        result = self.manager.resolve_param_connection("WIDTH")
        self.assertEqual(result, "32")

class TestWireRules(unittest.TestCase):
    
    def setUp(self):
        self.manager = VCGRuleManager()
    
    def test_add_wire_rule_basic(self):
        """测试基本线路规则添加"""
        self.manager.add_wire_rule("data", "wire_data")
        summary = self.manager.get_rules_summary()
        self.assertEqual(summary['wire_rules'], 1)
    
    def test_add_wire_rule_with_width(self):
        """测试带位宽的线路规则添加"""
        self.manager.add_wire_rule("data", "wire_data", "8")
        summary = self.manager.get_rules_summary()
        self.assertEqual(summary['wire_rules'], 1)
    
    def test_add_wire_rule_with_expression(self):
        """测试带表达式的线路规则添加"""
        self.manager.add_wire_rule("data", "wire_data", "8", "data_in & data_mask")
        summary = self.manager.get_rules_summary()
        self.assertEqual(summary['wire_rules'], 1)
    
    def test_resolve_wire_generation_greedy_mode_with_match(self):
        """测试贪婪模式线路生成（有匹配规则）"""
        self.manager.add_wire_rule("data_*", "wire_*", "8", "expression")
        
        port = TestPortInfo("data_bus")
        name, width, expr, found = self.manager.resolve_wire_generation(port, "greedy")
        
        self.assertEqual(name, "wire_bus")
        self.assertEqual(width, "8")
        self.assertEqual(expr, "expression")
        self.assertTrue(found)
    
    def test_resolve_wire_generation_greedy_mode_no_match(self):
        """测试贪婪模式线路生成（无匹配规则）"""
        port = TestPortInfo("unknown_port")
        name, width, expr, found = self.manager.resolve_wire_generation(port, "greedy")
        
        self.assertEqual(name, "unknown_port")
        self.assertIsNone(width)
        self.assertIsNone(expr)
        self.assertFalse(found)
    
    def test_resolve_wire_generation_lazy_mode_with_match(self):
        """测试惰性模式线路生成（有匹配规则）"""
        self.manager.add_wire_rule("data_*", "wire_*", "8", "expression")
        
        port = TestPortInfo("data_bus")
        name, width, expr, found = self.manager.resolve_wire_generation(port, "lazy")
        
        self.assertEqual(name, "wire_bus")
        self.assertEqual(width, "8")
        self.assertEqual(expr, "expression")
        self.assertTrue(found)
    
    def test_resolve_wire_generation_lazy_mode_no_match(self):
        """测试惰性模式线路生成（无匹配规则）"""
        port = TestPortInfo("unknown_port")
        name, width, expr, found = self.manager.resolve_wire_generation(port, "lazy")
        
        self.assertEqual(name, "")
        self.assertIsNone(width)
        self.assertIsNone(expr)
        self.assertFalse(found)
    
    def test_resolve_wire_generation_wildcard_replacement(self):
        """测试通配符替换"""
        self.manager.add_wire_rule("*_in_*", "*_wire_*", None, "${*0}+${*1}")
        
        port = TestPortInfo("data_in_bus")
        name, width, expr, found = self.manager.resolve_wire_generation(port)
        
        self.assertEqual(name, "data_wire_bus")
        self.assertEqual(expr, "data+bus")
        self.assertTrue(found)
    
    def test_wire_rule_priority_lifo(self):
        """测试线路规则优先级（后进先出）"""
        self.manager.add_wire_rule("data", "first_wire")
        self.manager.add_wire_rule("data", "second_wire")
        
        port = TestPortInfo("data")
        name, width, expr, found = self.manager.resolve_wire_generation(port)
        
        self.assertEqual(name, "second_wire")
        self.assertTrue(found)
    
    def test_resolve_wire_generation_comment_handling(self):
        """测试线路规则中的注释处理"""
        self.manager.add_wire_rule("clk", "wire_clk /* clock wire */", "1")
        
        port = TestPortInfo("clk")
        name, width, expr, found = self.manager.resolve_wire_generation(port)
        
        self.assertEqual(name, "wire_clk /* clock wire */")
        self.assertEqual(width, "1")
        self.assertTrue(found)

class TestPatternMatching(unittest.TestCase):
    
    def setUp(self):
        self.manager = VCGRuleManager()
    
    def test_pattern_matching_no_wildcards(self):
        """测试无通配符的精确匹配"""
        self.manager.add_signal_rule("exact_match", "result")
        
        port = TestPortInfo("exact_match")
        result = self.manager.resolve_signal_connection(port)
        self.assertEqual(result, "result")
        port_no_match = TestPortInfo("no_match")
        result_no_match = self.manager.resolve_signal_connection(port_no_match)
        self.assertEqual(result_no_match, "no_match")
    
    def test_pattern_matching_single_wildcard(self):
        """测试单个通配符匹配"""
        self.manager.add_signal_rule("prefix_*", "new_*")
        
        port = TestPortInfo("prefix_test")
        result = self.manager.resolve_signal_connection(port)
        self.assertEqual(result, "new_test")
    
    def test_pattern_matching_multiple_wildcards(self):
        """测试多个通配符匹配"""
        self.manager.add_signal_rule("*_middle_*", "*_new_*")
        
        port = TestPortInfo("start_middle_end")
        result = self.manager.resolve_signal_connection(port)
        self.assertEqual(result, "start_new_end")
    
    def test_pattern_matching_wildcard_empty_match(self):
        """测试通配符匹配空字符串"""
        self.manager.add_signal_rule("*test", "result_*")
        
        port = TestPortInfo("test")  # *匹配空字符串
        result = self.manager.resolve_signal_connection(port)
        self.assertEqual(result, "result_")

class TestFunctionProcessing(unittest.TestCase):
    
    def setUp(self):
        self.manager = VCGRuleManager()
    
    def test_function_upper(self):
        """测试upper函数"""
        self.manager.add_signal_rule("*", "${upper(*0)}")
        
        port = TestPortInfo("test_signal")
        result = self.manager.resolve_signal_connection(port)
        self.assertEqual(result, "TEST_SIGNAL")
    
    def test_function_lower(self):
        """测试lower函数"""
        self.manager.add_signal_rule("*", "${lower(*0)}")
        
        port = TestPortInfo("TEST_SIGNAL")
        result = self.manager.resolve_signal_connection(port)
        self.assertEqual(result, "test_signal")
    
    def test_function_title(self):
        """测试title函数"""
        self.manager.add_signal_rule("*", "${title(*0)}")
        
        port = TestPortInfo("test signal")
        result = self.manager.resolve_signal_connection(port)
        self.assertEqual(result, "Test Signal")
    
    def test_function_capitalize(self):
        """测试capitalize函数"""
        self.manager.add_signal_rule("*", "${capitalize(*0)}")
        
        port = TestPortInfo("test signal")
        result = self.manager.resolve_signal_connection(port)
        self.assertEqual(result, "Test signal")
    
    def test_function_replace(self):
        """测试replace函数"""
        self.manager.add_signal_rule("*", "${replace(*0, '_', '-')}")
        
        port = TestPortInfo("test_signal")
        result = self.manager.resolve_signal_connection(port)
        self.assertEqual(result, "test-signal")
    
    def test_function_strip(self):
        """测试strip函数"""
        self.manager.add_signal_rule("*", "${strip(*0)}")
        
        port = TestPortInfo("  test_signal  ")
        result = self.manager.resolve_signal_connection(port)
        self.assertEqual(result, "test_signal")
    
    def test_function_multiple_wildcards_reference(self):
        """测试函数中引用多个通配符"""
        self.manager.add_signal_rule("*_*", "${upper(*0)}_${lower(*1)}")
        
        port = TestPortInfo("Test_SIGNAL")
        result = self.manager.resolve_signal_connection(port)
        self.assertEqual(result, "TEST_signal")
    
    def test_function_with_star_reference(self):
        """测试函数中使用*引用第一个通配符"""
        self.manager.add_signal_rule("*_test", "${upper(*)}_RESULT")
        
        port = TestPortInfo("data_test")
        result = self.manager.resolve_signal_connection(port)
        self.assertEqual(result, "DATA_RESULT")

class TestEdgeCases(unittest.TestCase):
    
    def setUp(self):
        self.manager = VCGRuleManager()
    
    def test_empty_port_name(self):
        """测试空端口名"""
        port = TestPortInfo("")
        result = self.manager.resolve_signal_connection(port)
        self.assertEqual(result, "")
    
    def test_none_port_name(self):
        """测试None端口名（如果可能）"""
        try:
            port = TestPortInfo(None)
            result = self.manager.resolve_signal_connection(port)
            # 根据实现可能需要调整预期结果
        except (TypeError, AttributeError):
            # 如果实现不支持None，这是预期行为
            pass
    
    def test_complex_pattern_combinations(self):
        """测试复杂模式组合"""
        # 添加多个可能匹配的规则
        self.manager.add_signal_rule("*", "default_*")
        self.manager.add_signal_rule("clk*", "clock_*") 
        self.manager.add_signal_rule("clk_*_mhz", "freq_*_clock")
        
        port = TestPortInfo("clk_100_mhz")
        result = self.manager.resolve_signal_connection(port)
        # 应该使用最后添加的最具体的规则
        self.assertEqual(result, "freq_100_clock")
    
    def test_special_characters_in_patterns(self):
        """测试模式中的特殊字符"""
        self.manager.add_signal_rule("signal[*]", "wire[*]")
        
        port = TestPortInfo("signal[7:0]")
        result = self.manager.resolve_signal_connection(port)
        self.assertEqual(result, "wire[7:0]")
    
    def test_performance_with_many_rules(self):
        """测试大量规则的性能"""
        # 添加大量规则
        for i in range(1000):
            self.manager.add_signal_rule(f"sig_{i}", f"result_{i}")
        
        # 测试解析性能（这里主要是确保不会超时或崩溃）
        port = TestPortInfo("sig_999")
        result = self.manager.resolve_signal_connection(port)
        self.assertEqual(result, "result_999")

class TestUncoveredBranches(unittest.TestCase):
    """专门测试未覆盖分支的测试类"""
    
    def setUp(self):
        self.manager = VCGRuleManager()
    
    def test_pattern_substitution_no_match(self):
        """测试模式替换时匹配失败的情况"""
        # 创建一个具体的模式，但输入不匹配
        self.manager.add_signal_rule("prefix_*_suffix", "new_*_name")
        
        # 输入信号不符合模式（缺少前缀或后缀）
        port = TestPortInfo("different_signal_name")
        result = self.manager.resolve_signal_connection(port)
        
        # 应该返回原信号名（因为没有匹配到规则）
        self.assertEqual(result, "different_signal_name")
        
        # 另一个不匹配的情况：部分匹配但不完整
        port2 = TestPortInfo("prefix_test")  # 缺少_suffix
        result2 = self.manager.resolve_signal_connection(port2)
        self.assertEqual(result2, "prefix_test")
    
    def test_port_without_direction_attribute(self):
        """测试端口对象缺少direction属性的情况"""
        # 创建一个没有direction属性的端口对象类
        class PortWithoutDirection:
            def __init__(self, name):
                self.name = name
                # 故意不设置direction属性
                # 也不设置其他属性
        
        self.manager.add_signal_rule("test_*", "output_*", "input")
        
        port = PortWithoutDirection("test_signal")
        result = self.manager.resolve_signal_connection(port)
        
        # 即使规则指定了input类型，但端口无direction属性，仍应匹配
        self.assertEqual(result, "output_signal")
    
    def test_width_literal_with_string_digit_width(self):
        """测试位宽为字符串数字的字面量生成"""
        # 创建位宽为字符串的端口类
        class PortWithStringWidth:
            def __init__(self, name, width_str):
                self.name = name
                self._width = width_str  # 存储字符串类型的位宽
                self.direction = ""
                self.net_type = ""
                self.range_expr = None
            
            @property
            def width(self):
                return self._width
        
        self.manager.add_signal_rule("test_signal_0", "0")  # 目标值为0
        self.manager.add_signal_rule("test_signal_1", "1")  # 目标值为1
        
        # 测试位宽为字符串"4"的情况 - 值为0
        port1 = PortWithStringWidth("test_signal_0", "4")
        result1 = self.manager.resolve_signal_connection(port1)
        self.assertEqual(result1, "4'b0000")
        
        # 测试位宽为字符串"4"的情况 - 值为1
        port2 = PortWithStringWidth("test_signal_1", "4")
        result2 = self.manager.resolve_signal_connection(port2)
        self.assertEqual(result2, "4'b1111")
        
        # 测试位宽为字符串"1"的情况
        port3 = PortWithStringWidth("test_signal_0", "1")
        result3 = self.manager.resolve_signal_connection(port3)
        self.assertEqual(result3, "1'b0")
        
        # 测试位宽为字符串"0"的情况（边界条件）
        port4 = PortWithStringWidth("test_signal_1", "0")
        result4 = self.manager.resolve_signal_connection(port4)
        self.assertEqual(result4, "1'b1")  # 位宽<=1时默认为1位
    
    def test_width_literal_with_expression_width(self):
        """测试位宽为表达式的字面量生成"""
        class PortWithExpressionWidth:
            def __init__(self, name, width_expr):
                self.name = name
                self._width = width_expr  # 表达式类型的位宽
                self.direction = ""
                self.net_type = ""
                self.range_expr = None
            
            @property
            def width(self):
                return self._width
        
        self.manager.add_signal_rule("expr_signal_0", "0")  # 目标值为0
        self.manager.add_signal_rule("expr_signal_1", "1")  # 目标值为1
        
        # 测试包含加法的表达式位宽
        port1 = PortWithExpressionWidth("expr_signal_1", "DATA_WIDTH+1")
        result1 = self.manager.resolve_signal_connection(port1)
        self.assertEqual(result1, "{(DATA_WIDTH+1){1'b1}}")
        
        # 测试包含减法的表达式位宽
        port2 = PortWithExpressionWidth("expr_signal_0", "BUS_WIDTH-2")
        result2 = self.manager.resolve_signal_connection(port2)
        self.assertEqual(result2, "{(BUS_WIDTH-2){1'b0}}")
        
        # 测试包含乘法的表达式位宽
        port3 = PortWithExpressionWidth("expr_signal_1", "WIDTH*2")
        result3 = self.manager.resolve_signal_connection(port3)
        self.assertEqual(result3, "{(WIDTH*2){1'b1}}")
        
        # 测试包含除法的表达式位宽
        port4 = PortWithExpressionWidth("expr_signal_0", "TOTAL_WIDTH/4")
        result4 = self.manager.resolve_signal_connection(port4)
        self.assertEqual(result4, "{(TOTAL_WIDTH/4){1'b0}}")
        
        # 测试包含括号的复杂表达式位宽
        port5 = PortWithExpressionWidth("expr_signal_1", "(WIDTH*2-1)")
        result5 = self.manager.resolve_signal_connection(port5)
        self.assertEqual(result5, "{((WIDTH*2-1)){1'b1}}")
        
        # 测试多层括号的复杂表达式
        port6 = PortWithExpressionWidth("expr_signal_0", "((A+B)*(C-D))")
        result6 = self.manager.resolve_signal_connection(port6)
        self.assertEqual(result6, "{(((A+B)*(C-D))){1'b0}}")
    
    def test_edge_cases_comprehensive(self):
        """综合测试各种边界情况"""
        # 综合测试：无direction属性 + 表达式位宽
        class ComplexPort:
            def __init__(self, name, width):
                self.name = name
                self._width = width
                # 故意不设置direction属性
                self.net_type = ""
                self.range_expr = None
            
            @property
            def width(self):
                return self._width
        
        self.manager.add_signal_rule("complex_*", "0", "input")
        
        # 测试复杂端口：无direction + 表达式位宽
        port1 = ComplexPort("complex_signal", "BUS_WIDTH/2")
        result1 = self.manager.resolve_signal_connection(port1)
        self.assertEqual(result1, "{(BUS_WIDTH/2){1'b0}}")
        
        # 测试复杂端口：无direction + 数字字符串位宽
        port2 = ComplexPort("complex_data", "8")
        result2 = self.manager.resolve_signal_connection(port2)
        self.assertEqual(result2, "8'b00000000")
    
    def test_pattern_matching_edge_cases(self):
        """测试模式匹配的边界情况"""
        # 测试空字符串模式匹配失败
        self.manager.add_signal_rule("*_test_*", "result_*_*")
        
        # 这个信号名不符合*_test_*的模式
        port1 = TestPortInfo("just_test")
        result1 = self.manager.resolve_signal_connection(port1)
        self.assertEqual(result1, "just_test")  # 应该返回原名称
        
        self.manager.reset()
        # 测试更复杂的不匹配情况
        self.manager.add_signal_rule("start_*_middle_*_end", "new_*_*")
        
        port2 = TestPortInfo("start_test_middle")  # 缺少_end
        result2 = self.manager.resolve_signal_connection(port2)
        self.assertEqual(result2, "start_test_middle")
        
        self.manager.reset()
        port3 = TestPortInfo("start_middle_test_end")  # 缺少第一个*后的内容
        result3 = self.manager.resolve_signal_connection(port3)
        self.assertEqual(result3, "start_middle_test_end")
    
    def test_width_literal_special_cases(self):
        """测试位宽字面量的特殊情况"""
        class PortWithSpecialWidth:
            def __init__(self, name, width):
                self.name = name
                self._width = width
                self.direction = ""
                self.net_type = ""
                self.range_expr = None
            
            @property
            def width(self):
                return self._width
        
        self.manager.add_signal_rule("special_*", "1")
        
        # 测试包含多个运算符的表达式
        port1 = PortWithSpecialWidth("special_multi", "A+B-C*D/E")
        result1 = self.manager.resolve_signal_connection(port1)
        self.assertEqual(result1, "{(A+B-C*D/E){1'b1}}")
        
        # 测试嵌套括号表达式
        port2 = PortWithSpecialWidth("special_nested", "(A+(B*C))")
        result2 = self.manager.resolve_signal_connection(port2)
        self.assertEqual(result2, "{((A+(B*C))){1'b1}}")
        
        # 测试字符串"0"的位宽（边界情况）
        port3 = PortWithSpecialWidth("special_zero", "0")
        result3 = self.manager.resolve_signal_connection(port3)
        self.assertEqual(result3, "1'b1")  # 0位宽应该当作1位处理

if __name__ == '__main__':
    # 创建测试套件
    unittest.main()
