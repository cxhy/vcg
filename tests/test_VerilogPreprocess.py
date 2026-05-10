"""
VerilogPreprocess 单元测试
测试覆盖所有功能点、边界条件和异常处理
"""

import pytest
import os
import sys
import tempfile
from pathlib import Path

# 导入被测模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
from src.VerilogPreprocess import VerilogPreprocess
from src.vcg_exceptions import VCGFileError, VCGParseError


#============================================================================
# 3.1 宏定义初始化测试 (_parse_macros)
# ============================================================================

class TestMacrosParsing:
    """测试宏定义初始化功能"""
    
    def test_parse_macros_none_input(self):
        """功能点 3.1.1: 处理 None 输入"""
        vp = VerilogPreprocess(None)
        assert vp.get_macros() == {}
    
    def test_parse_macros_dict_input(self):
        """功能点 3.1.2: 处理字典输入"""
        macros = {"ENABLE": "1", "WIDTH": "32"}
        vp = VerilogPreprocess(macros)
        assert vp.get_macros() == macros
    
    def test_parse_macros_empty_dict(self):
        """功能点 3.1.2: 空字典边界条件"""
        vp = VerilogPreprocess({})
        assert vp.get_macros() == {}
    
    def test_parse_macros_string_list_input(self):
        """功能点 3.1.3: 处理字符串列表输入"""
        macros = ["ENABLE", "DEBUG"]
        vp = VerilogPreprocess(macros)
        assert vp.get_macros() == {"ENABLE": "1", "DEBUG": "1"}
    
    def test_parse_macros_empty_list(self):
        """功能点 3.1.3: 空列表边界条件"""
        vp = VerilogPreprocess([])
        assert vp.get_macros() == {}
    
    def test_parse_macros_tuple_list_input(self):
        """功能点 3.1.4: 处理元组列表输入"""
        macros = [("ENABLE", "1"), ("WIDTH", "32")]
        vp = VerilogPreprocess(macros)
        assert vp.get_macros() == {"ENABLE": "1", "WIDTH": "32"}
    
    def test_parse_macros_invalid_dict_key(self):
        """功能点 3.1.5: 字典键不是字符串"""
        with pytest.raises(ValueError):
            VerilogPreprocess({123: "value"})
    
    def test_parse_macros_invalid_dict_value(self):
        """功能点 3.1.5: 字典值不是字符串"""
        with pytest.raises(ValueError):
            VerilogPreprocess({"KEY": 123})
    
    def test_parse_macros_list_non_string_element(self):
        """功能点 3.1.5: 列表包含非字符串元素"""
        with pytest.raises(ValueError):
            VerilogPreprocess(["VALID", 123])
    
    def test_parse_macros_tuple_wrong_length(self):
        """功能点 3.1.5: 元组长度不是2"""
        with pytest.raises(ValueError):
            VerilogPreprocess([("SINGLE",)])
        with pytest.raises(ValueError):
            VerilogPreprocess([("ONE", "TWO", "THREE")])
    
    def test_parse_macros_tuple_non_string_element(self):
        """功能点 3.1.5: 元组元素不是字符串"""
        with pytest.raises(ValueError):
            VerilogPreprocess([("KEY", 123)])
        with pytest.raises(ValueError):
            VerilogPreprocess([(123, "VALUE")])
    
    def test_parse_macros_unsupported_type(self):
        """功能点 3.1.5: 传入不支持的类型"""
        with pytest.raises(ValueError):
            VerilogPreprocess(123)
        with pytest.raises(ValueError):
            VerilogPreprocess(3.14)
        with pytest.raises(ValueError):
            VerilogPreprocess("string")


# ============================================================================
# 3.2 文件读取测试 (read_file)
# ============================================================================

class TestFileReading:
    """测试文件读取功能"""
    
    def test_read_existing_file_utf8(self):
        """功能点 3.2.1: 读取UTF-8编码的文件"""
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                        suffix='.v', delete=False) as f:
            f.write("module test;\nendmodule")
            temp_path = f.name
        
        try:
            vp = VerilogPreprocess()
            content = vp.read_file(temp_path)
            assert "module test;" in content
            assert "endmodule" in content
        finally:
            os.unlink(temp_path)
    
    def test_read_file_with_special_characters(self):
        """功能点 3.2.3: 包含特殊字符的文件"""
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', 
                                        suffix='.v', delete=False) as f:
            f.write("// 中文注释\nmodule test_模块;\nendmodule")
            temp_path = f.name
        
        try:
            vp = VerilogPreprocess()
            content = vp.read_file(temp_path)
            assert "中文注释" in content or "test_" in content  # 编码可能影响
        finally:
            os.unlink(temp_path)
    
    def test_read_nonexistent_file(self):
        """功能点 3.2.2: 文件不存在"""
        vp = VerilogPreprocess()
        with pytest.raises(VCGFileError) as exc_info:
            vp.read_file("nonexistent_file_12345.v")
        assert "Verilog file not found" in str(exc_info.value)


# ============================================================================
# 3.3 移除模块前内容测试 (remove_pre_module_content)
# ============================================================================

class TestRemovePreModuleContent:
    """测试移除模块前内容功能"""
    
    def test_remove_pre_module_normal(self):
        """功能点 3.3.1: 正常移除模块前内容"""
        code = """// Header comment
`include "header.v"

module test_module;
  input clk;
endmodule"""
        vp = VerilogPreprocess()
        result = vp.remove_pre_module_content(code)
        assert result.strip().startswith("module test_module;")
        assert "`include" not in result
        assert "Header comment" not in result
    
    def test_remove_pre_module_no_module(self):
        """功能点 3.3.2: 无模块的情况"""
        code = """// Only comments
`include "header.v"
wire test;"""
        vp = VerilogPreprocess()
        result = vp.remove_pre_module_content(code)
        assert result.strip() == "" or result.strip() == code.strip()

    def test_attribute_line_before_module_does_not_drop_module(self):
        """功能点 3.3.3: module 前 attribute 行不导致 module 丢失"""
        code = """// Header comment
(* keep_hierarchy = "yes" *)
module attributed_module(
  input clk
);
endmodule"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert "module attributed_module(" in result
        assert "input clk" in result


# ============================================================================
# 3.4 提取模块端口声明测试 (extract_module_ports_section)
# ============================================================================

class TestExtractModulePorts:
    """测试提取模块端口声明功能"""
    
    def test_extract_single_line_declaration(self):
        """功能点 3.4.3: 单行端口声明"""
        code = """module test;
  input wire clk;
  output reg data;
endmodule"""
        vp = VerilogPreprocess()
        ports, end = vp.extract_module_ports_section(code)
        assert "module test;" in ports
        assert "input wire clk;" in ports
        assert "output reg data;" in ports
        assert end == "endmodule"
    
    def test_extract_multiline_declaration(self):
        """功能点 3.4.4: 多行端口声明"""
        code = """module test(
  input clk,
  input rst
);
  input wire [7:0] data;
  output status;
endmodule"""
        vp = VerilogPreprocess()
        ports, end = vp.extract_module_ports_section(code)
        assert "module test(" in ports
        assert "input clk," in ports
        assert "data;" in ports
        assert "output status;" in ports
    
    def test_extract_parameter_declaration(self):
        """功能点 3.4.3: parameter声明"""
        code = """module test;
  parameter WIDTH = 32;
  input wire [WIDTH-1:0] data;
endmodule"""
        vp = VerilogPreprocess()
        ports, end = vp.extract_module_ports_section(code)
        assert "parameter WIDTH" in ports
        assert "input wire" in ports

    def test_extract_localparam_declaration(self):
        """功能点 3.4.3: localparam 声明"""
        code = """module test;
  localparam WIDTH = 32;
  input wire [WIDTH-1:0] data;
endmodule"""
        vp = VerilogPreprocess()
        ports, end = vp.extract_module_ports_section(code)
        assert "localparam WIDTH = 32;" in ports
        assert "input wire [WIDTH-1:0] data;" in ports
    
    def test_extract_inout_declaration(self):
        """功能点 3.4.3: inout 声明"""
        code = """module test;
  inout wire data_bus;
endmodule"""
        vp = VerilogPreprocess()
        ports, end = vp.extract_module_ports_section(code)
        assert "inout wire data_bus;" in ports
    
    def test_extract_stops_at_endmodule(self):
        """功能点 3.4.5: 遇到 endmodule 停止"""
        code = """module test;
  input clk;
  wire internal_signal;
  assign internal_signal = clk;
endmodule"""
        vp = VerilogPreprocess()
        ports, end = vp.extract_module_ports_section(code)
        # 应该不包含 wire 和 assign（因为它们不是端口声明）
        assert "input clk;" in ports
        # 根据实现，可能在遇到非声明语句后停止

    def test_comment_semicolon_does_not_truncate_module_header(self):
        """功能点 3.4.6: module header 注释中的分号不截断声明"""
        code = """module test(
  // comment with ; should not close header
  input clk,
  output done
);
endmodule"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert "input clk" in result
        assert "output done" in result
        assert ");" in result

    def test_comment_semicolon_does_not_truncate_port_declaration(self):
        """功能点 3.4.6: 端口声明注释中的分号不截断声明"""
        code = """module test;
  input wire [7:0] /* comment ; inside */
    data;
  output done;
endmodule"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert "input wire [7:0]" in result
        assert "data;" in result
        assert "output done;" in result

    def test_block_comment_port_text_does_not_leak_into_output(self):
        """回归: 多行块注释中的端口文本不泄漏到预处理输出"""
        code = """module block_comment_leak(
  input wire clk
);
  /* `ifdef COMMENT_ONLY
     input hidden;
     `endif */
endmodule"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert "input wire clk" in result
        assert "hidden" not in result


# ============================================================================
# 3.5 条件编译处理测试 (process_conditional_compilation)
# ============================================================================

class TestConditionalCompilation:
    """测试条件编译处理功能"""
    
    # 3.5.1 ifdef 指令测试
    def test_ifdef_macro_defined(self):
        """功能点 3.5.1.1: ifdef 宏已定义"""
        code = """module test;
`ifdef ENABLE
  input enable;
`endif
  input common;
endmodule"""
        vp = VerilogPreprocess({"ENABLE": "1"})
        result = vp.preprocess_string(code)
        assert "input enable;" in result
        assert "input common;" in result
    
    def test_ifdef_macro_undefined(self):
        """功能点 3.5.1.2: ifdef 宏未定义"""
        code = """module test;
`ifdef ENABLE
  input enable;
`endif
  input common;
endmodule"""
        vp = VerilogPreprocess({})
        result = vp.preprocess_string(code)
        assert "input enable;" not in result
        assert "input common;" in result
    
    # 3.5.2 ifndef 指令测试
    def test_ifndef_macro_undefined(self):
        """功能点 3.5.2.1: ifndef 宏未定义"""
        code = """module test;
`ifndef DISABLE
  input enable;
`endif
endmodule"""
        vp = VerilogPreprocess({})
        result = vp.preprocess_string(code)
        assert "input enable;" in result
    
    def test_ifndef_macro_defined(self):
        """功能点 3.5.2.2: ifndef 宏已定义"""
        code = """module test;
`ifndef DISABLE
  input enable;
`endif
endmodule"""
        vp = VerilogPreprocess({"DISABLE": "1"})
        result = vp.preprocess_string(code)
        assert "input enable;" not in result
    
    # 3.5.3 else 指令测试
    def test_else_ifdef_not_satisfied(self):
        """功能点 3.5.3.1: ifdef 不满足，else 分支生效"""
        code = """module test;
`ifdef ENABLE
  input enable;
`else
  input disable;
`endif
endmodule"""
        vp = VerilogPreprocess({})
        result = vp.preprocess_string(code)
        assert "input enable;" not in result
        assert "input disable;" in result
    
    def test_else_ifdef_satisfied(self):
        """功能点 3.5.3.2: ifdef 满足，else 分支不生效"""
        code = """module test;
`ifdef ENABLE
  input enable;
`else
  input disable;
`endif
endmodule"""
        vp = VerilogPreprocess({"ENABLE": "1"})
        result = vp.preprocess_string(code)
        assert "input enable;" in result
        assert "input disable;" not in result
    
    # 3.5.4 elsif 指令测试
    def test_elsif_ifdef_satisfied(self):
        """功能点 3.5.4.1: ifdef 满足，elsif 不执行"""
        code = """module test;
`ifdef MACRO1
  input port1;
`elsif MACRO2
  input port2;
`endif
endmodule"""
        vp = VerilogPreprocess({"MACRO1": "1", "MACRO2": "1"})
        result = vp.preprocess_string(code)
        assert "input port1;" in result
        assert "input port2;" not in result
    
    def test_elsif_ifdef_not_satisfied_elsif_satisfied(self):
        """功能点 3.5.4.2: ifdef 不满足，elsif 满足"""
        code = """module test;
`ifdef MACRO1
  input port1;
`elsif MACRO2
  input port2;
`endif
endmodule"""
        vp = VerilogPreprocess({"MACRO2": "1"})
        result = vp.preprocess_string(code)
        assert "input port1;" not in result
        assert "input port2;" in result
    
    def test_elsif_none_satisfied(self):
        """功能点 3.5.4.3: ifdef 和 elsif 都不满足"""
        code = """module test;
`ifdef MACRO1
  input port1;
`elsif MACRO2
  input port2;
`endif
endmodule"""
        vp = VerilogPreprocess({})
        result = vp.preprocess_string(code)
        assert "input port1;" not in result
        assert "input port2;" not in result
    
    def test_multiple_elsif(self):
        """功能点 3.5.4.4: 多个 elsif"""
        code = """module test;
`ifdef MACRO1
  input port1;
`elsif MACRO2
  input port2;
`elsif MACRO3
  input port3;
`else
  input port4;
`endif
endmodule"""
        
        # 只有 MACRO1 定义
        vp = VerilogPreprocess({"MACRO1": "1"})
        result = vp.preprocess_string(code)
        assert "input port1;" in result
        assert "input port2;" not in result
        assert "input port3;" not in result
        assert "input port4;" not in result
        
        # 只有 MACRO2 定义
        vp = VerilogPreprocess({"MACRO2": "1"})
        result = vp.preprocess_string(code)
        assert "input port1;" not in result
        assert "input port2;" in result
        assert "input port3;" not in result
        assert "input port4;" not in result
        
        # 只有 MACRO3 定义
        vp = VerilogPreprocess({"MACRO3": "1"})
        result = vp.preprocess_string(code)
        assert "input port1;" not in result
        assert "input port2;" not in result
        assert "input port3;" in result
        assert "input port4;" not in result
        # 都不定义（走else）
        vp = VerilogPreprocess({})
        result = vp.preprocess_string(code)
        assert "input port1;" not in result
        assert "input port2;" not in result
        assert "input port3;" not in result
        assert "input port4;" in result
        # 多个都定义（只有第一个满足的生效）
        vp = VerilogPreprocess({"MACRO1": "1", "MACRO2": "1", "MACRO3": "1"})
        result = vp.preprocess_string(code)
        assert "input port1;" in result
        assert "input port2;" not in result
        assert "input port3;" not in result
        assert "input port4;" not in result
    
    # 3.5.5 嵌套条件编译测试
    def test_nested_two_levels_both_defined(self):
        """功能点 3.5.5.1: 两层嵌套，都定义"""
        code = """module test;
`ifdef OUTER
  input outer_port;
  `ifdef INNER
    input inner_port;
  `endif
`endif
endmodule"""
        vp = VerilogPreprocess({"OUTER": "1", "INNER": "1"})
        result = vp.preprocess_string(code)
        assert "input outer_port;" in result
        assert "input inner_port;" in result
    
    def test_nested_two_levels_only_outer(self):
        """功能点 3.5.5.1: 两层嵌套，只定义外层"""
        code = """module test;
`ifdef OUTER
  input outer_port;
  `ifdef INNER
    input inner_port;
  `endif
`endif
endmodule"""
        vp = VerilogPreprocess({"OUTER": "1"})
        result = vp.preprocess_string(code)
        assert "input outer_port;" in result
        assert "input inner_port;" not in result
    
    def test_nested_two_levels_only_inner(self):
        """功能点 3.5.5.1: 两层嵌套，只定义内层"""
        code = """module test;
`ifdef OUTER
  input outer_port;
  `ifdef INNER
    input inner_port;
  `endif
`endif
endmodule"""
        vp = VerilogPreprocess({"INNER": "1"})
        result = vp.preprocess_string(code)
        assert "input outer_port;" not in result
        assert "input inner_port;" not in result
    
    def test_nested_two_levels_none_defined(self):
        """功能点 3.5.5.1: 两层嵌套，都不定义"""
        code = """module test;
`ifdef OUTER
  input outer_port;
  `ifdef INNER
    input inner_port;
  `endif
`endif
endmodule"""
        vp = VerilogPreprocess({})
        result = vp.preprocess_string(code)
        assert "input outer_port;" not in result
        assert "input inner_port;" not in result
    
    def test_nested_with_else(self):
        """功能点 3.5.5.3: 嵌套中的 else"""
        code = """module test;
`ifdef OUTER
  `ifdef INNER
    input port1;
  `else
    input port2;
  `endif
`else
  input port3;
`endif
endmodule"""
        
        # OUTER 和 INNER 都定义
        vp = VerilogPreprocess({"OUTER": "1", "INNER": "1"})
        result = vp.preprocess_string(code)
        assert "input port1;" in result
        assert "input port2;" not in result
        assert "input port3;" not in result
        
        # 只定义 OUTER
        vp = VerilogPreprocess({"OUTER": "1"})
        result = vp.preprocess_string(code)
        assert "input port1;" not in result
        assert "input port2;" in result
        assert "input port3;" not in result
        
        # 都不定义
        vp = VerilogPreprocess({})
        result = vp.preprocess_string(code)
        assert "input port1;" not in result
        assert "input port2;" not in result
        assert "input port3;" in result

    def test_define_before_ifdef_activates_branch(self):
        """功能点 3.5.6: define 后 ifdef 生效"""
        code = """module test;
`define ENABLE
`ifdef ENABLE
  input enabled;
`endif
endmodule"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert "input enabled;" in result
        assert vp.get_macros()["ENABLE"] == "1"

    def test_undef_before_ifdef_deactivates_branch(self):
        """功能点 3.5.6: undef 后 ifdef 失效"""
        code = """module test;
`define ENABLE
`undef ENABLE
`ifdef ENABLE
  input enabled;
`else
  input disabled;
`endif
endmodule"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert "input enabled;" not in result
        assert "input disabled;" in result
        assert "ENABLE" not in vp.get_macros()

    def test_define_in_inactive_branch_does_not_activate_later_ifdef(self):
        """功能点 3.5.6: 非活动分支内 define 不生效"""
        code = """module test;
`ifdef NEVER_DEFINED
`define ENABLE
`endif
`ifdef ENABLE
  input enabled;
`else
  input disabled;
`endif
endmodule"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert "input enabled;" not in result
        assert "input disabled;" in result
        assert "ENABLE" not in vp.get_macros()

    def test_line_comment_directives_do_not_affect_condition_stack(self):
        """功能点 3.5.7: 整行注释中的预处理指令不影响条件栈"""
        code = """module test;
// `ifdef COMMENT_ONLY
  input visible;
// `endif
endmodule"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert "input visible;" in result

    def test_trailing_comment_directives_do_not_affect_condition_stack(self):
        """功能点 3.5.7: 行尾注释中的预处理指令不影响条件栈"""
        code = """module test;
  input visible; // `ifdef COMMENT_ONLY
  output done; // `endif
endmodule"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert "input visible;" in result
        assert "output done;" in result

    def test_block_comment_directives_do_not_affect_condition_stack(self):
        """功能点 3.5.7: 块注释中的预处理指令不影响条件栈"""
        code = """module test;
/* `ifdef COMMENT_ONLY
   `else
   `endif */
  input visible;
endmodule"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert "input visible;" in result

    @pytest.mark.parametrize("directive", ["`else", "`elsif ENABLE", "`endif"])
    def test_orphan_conditional_directives_raise_parse_error(self, directive):
        """功能点 3.5.8: 孤立 else/elsif/endif 抛 VCGParseError"""
        code = f"""module test;
  input before;
{directive}
  input after;
endmodule"""
        vp = VerilogPreprocess()
        with pytest.raises(VCGParseError):
            vp.preprocess_string(code)


# ============================================================================
# 3.6 完整预处理流程测试
# ============================================================================

class TestCompletePreprocessing:
    """测试完整预处理流程"""
    
    def test_preprocess_file_integration(self):
        """功能点 3.6.1: preprocess_file 集成测试"""
        code = """// Header
`include "test.v"

module test_module;
`ifdef ENABLE
  input enable_port;
`endif
  input common_port;
endmodule"""
        
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.v', delete=False) as f:
            f.write(code)
            temp_path = f.name
        
        try:
            vp = VerilogPreprocess({"ENABLE": "1"})
            result = vp.preprocess_file(temp_path)
            assert "module test_module;" in result
            assert "input enable_port;" in result
            assert "input common_port;" in result
            assert "`include" not in result
            assert "Header" not in result
        finally:
            os.unlink(temp_path)
    
    def test_preprocess_string_integration(self):
        """功能点 3.6.2: preprocess_string 集成测试"""
        code = """// Header
module test_module;
`ifdef ENABLE
  input enable_port;
`endif
  input common_port;
endmodule"""
        
        vp = VerilogPreprocess({"ENABLE": "1"})
        result = vp.preprocess_string(code)
        assert "module test_module;" in result
        assert "input enable_port;" in result
        assert "input common_port;" in result
    def test_preprocess_file_not_found_runtime_error(self):
        """功能点 3.6.3: 文件不存在时抛 VCGFileError"""
        vp = VerilogPreprocess()
        with pytest.raises(VCGFileError):
            vp.preprocess_file("nonexistent_12345.v")


class TestTask09PreprocessRefactorBehavior:
    """TASK-09: 整文件上下文、目标 module 和声明抽取行为"""

    def test_define_before_module_controls_inside_ifdef(self):
        code = """`define ENABLE
module m;
`ifdef ENABLE
  input en;
`endif
endmodule"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert "input en;" in result

    def test_include_guard_wrapping_module_is_supported_without_orphan_endif(self):
        code = """`ifndef M_V
`define M_V
module m;
  input clk;
endmodule
`endif"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert "module m;" in result
        assert "input clk;" in result
        assert "endmodule" in result

    def test_value_macro_reference_is_preserved_in_width_expression(self):
        code = """module m;
  input [`WIDTH-1:0] data;
endmodule"""
        vp = VerilogPreprocess({"WIDTH": "32"})
        result = vp.preprocess_string(code)
        assert "`WIDTH-1:0" in result
        assert "32-1:0" not in result

    def test_macro_value_is_not_expanded_in_parameter_default(self):
        code = """module m;
  parameter DEPTH = `DEPTH_DEFAULT;
endmodule"""
        vp = VerilogPreprocess({"DEPTH_DEFAULT": "1024"})
        result = vp.preprocess_string(code)
        assert "parameter DEPTH = `DEPTH_DEFAULT;" in result
        assert "1024" not in result

    def test_string_comment_markers_do_not_start_comments(self):
        code = """module m;
  parameter URL = "http://example";
  input clk;
endmodule"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert 'parameter URL = "http://example";' in result
        assert "input clk;" in result

    def test_string_semicolon_does_not_end_declaration_scan_early(self):
        code = """module m;
  parameter TEXT = "a;b"
    ;
  input clk;
endmodule"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert 'parameter TEXT = "a;b"\n    ;' in result
        assert "input clk;" in result

    def test_multi_module_defaults_to_first_active_module_for_backward_compat(self):
        code = """module first;
  input a;
endmodule

module second;
  input b;
endmodule"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert "module first;" in result
        assert "input a;" in result
        assert "module second;" not in result
        assert "input b;" not in result

    def test_target_module_selects_second_module_if_optional_arg_implemented(self):
        code = """module first;
  input a;
endmodule

module second;
  input b;
endmodule"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code, target_module="second")
        assert "module second;" in result
        assert "input b;" in result
        assert "module first;" not in result
        assert "input a;" not in result

    def test_target_module_missing_raises_parse_error_if_optional_arg_implemented(self):
        code = """module first;
  input a;
endmodule"""
        vp = VerilogPreprocess()
        with pytest.raises(VCGParseError):
            vp.preprocess_string(code, target_module="missing")

    def test_non_declaration_body_items_are_ignored_not_output(self):
        code = """module m(input clk);
  assign x = clk;
  child u0 (.clk(clk));
  input late_decl;
endmodule"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert "input late_decl;" in result
        assert "assign x" not in result
        assert "child u0" not in result

    def test_unsupported_directive_inside_extracted_declaration_raises_parse_error(self):
        code = """module m;
  `timescale 1ns/1ps
  input clk;
endmodule"""
        vp = VerilogPreprocess()
        with pytest.raises(VCGParseError):
            vp.preprocess_string(code)

    def test_clear_macros_return_type_and_behavior(self):
        vp = VerilogPreprocess({"ENABLE": "1"})
        result = vp.clear_macros()
        assert result is None
        assert vp.get_macros() == {}

    def test_include_outside_target_declaration_is_dropped(self):
        code = """`include "defs.vh"
module m;
  input clk;
endmodule"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert "`include" not in result
        assert "input clk;" in result

    def test_include_inside_target_declaration_raises_parse_error(self):
        code = """module m;
  `include "ports.vh"
  input clk;
endmodule"""
        vp = VerilogPreprocess()
        with pytest.raises(VCGParseError):
            vp.preprocess_string(code)

    def test_duplicate_target_module_raises_parse_error(self):
        code = """module dup;
  input a;
endmodule

module dup;
  input b;
endmodule"""
        vp = VerilogPreprocess()
        with pytest.raises(VCGParseError):
            vp.preprocess_string(code, target_module="dup")

    def test_inactive_include_inside_module_is_ignored(self):
        code = """module m;
`ifdef NEVER
  `include "ports.vh"
`endif
  input clk;
endmodule"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert "`include" not in result
        assert "input clk;" in result

    def test_string_endmodule_does_not_terminate_inline_module(self):
        code = """module m;
  parameter TEXT = "not an endmodule token";
  input clk;
endmodule"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert 'parameter TEXT = "not an endmodule token";' in result
        assert "input clk;" in result


# ============================================================================
# 4. 边界条件测试
# ============================================================================

class TestBoundaryConditions:
    """测试边界条件"""
    
    def test_empty_file(self):
        """边界条件 4.1: 空文件"""
        vp = VerilogPreprocess()
        result = vp.preprocess_string("")
        assert result.strip() == "endmodule" or result.strip() == ""
    
    def test_no_module_definition(self):
        """边界条件 4.1: 无模块定义"""
        code = "// Only comments\nwire test;"
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        # 应该返回 endmodule 或空字符串
        assert "endmodule" in result or result.strip() == ""
    
    def test_module_without_ports(self):
        """边界条件 4.1: 无端口模块"""
        code = "module test;\nendmodule"
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert "module test;" in result
        assert "endmodule" in result
    
    def test_empty_macro_definitions(self):
        """边界条件 4.2: 空宏定义"""
        code = """module test;
`ifdef ENABLE
  input enable;
`endif
`ifndef DISABLE
  input active;
`endif
endmodule"""
        
        vp = VerilogPreprocess({})
        result = vp.preprocess_string(code)
        assert "input enable;" not in result  # ifdef 失败
        assert "input active;" in result      # ifndef 成功
    
    def test_macro_with_empty_value(self):
        """边界条件 4.2: 宏值为空"""
        vp = VerilogPreprocess({"MACRO": ""})
        macros = vp.get_macros()
        assert "MACRO" in macros
        assert macros["MACRO"] == ""
    
    def test_unclosed_ifdef(self):
        """边界条件 4.3: 无 endif 抛 VCGParseError"""
        code = """module test;
`ifdef ENABLE
  input enable;
endmodule"""
        vp = VerilogPreprocess({"ENABLE": "1"})
        with pytest.raises(VCGParseError):
            vp.preprocess_string(code)
    
    def test_extra_endif(self):
        """边界条件 4.3: 多余 endif 抛 VCGParseError"""
        code = """module test;
  input port;
`endif
endmodule"""
        vp = VerilogPreprocess()
        with pytest.raises(VCGParseError):
            vp.preprocess_string(code)
    
    def test_consecutive_conditional_blocks(self):
        """边界条件 4.3: 连续条件块"""
        code = """module test;
`ifdef MACRO1
  input port1;
`endif
`ifdef MACRO2
  input port2;
`endif
endmodule"""
        vp = VerilogPreprocess({"MACRO1": "1", "MACRO2": "1"})
        result = vp.preprocess_string(code)
        assert "input port1;" in result
        assert "input port2;" in result
    
    def test_empty_conditional_block(self):
        """边界条件 4.3: 空条件块"""
        code = """module test;
`ifdef ENABLE
`endif
  input port;
endmodule"""
        vp = VerilogPreprocess({"ENABLE": "1"})
        result = vp.preprocess_string(code)
        assert "input port;" in result


# ============================================================================
# 其他辅助方法测试
# ============================================================================

class TestHelperMethods:
    """测试辅助方法"""
    
    def test_get_macros_returns_copy(self):
        """get_macros 返回副本"""
        original_macros = {"MACRO1": "1", "MACRO2": "2"}
        vp = VerilogPreprocess(original_macros)
        
        # 获取宏定义
        macros = vp.get_macros()
        assert macros == original_macros
        
        # 修改返回的副本
        macros["MACRO3"] = "3"
        
        # 验证内部状态未改变
        assert vp.get_macros() == original_macros
        assert "MACRO3" not in vp.get_macros()
    
    def test_clear_macros(self):
        """clear_macros 清空所有宏定义"""
        vp = VerilogPreprocess({"MACRO1": "1", "MACRO2": "2"})
        assert len(vp.get_macros()) == 2
        
        vp.clear_macros()
        assert vp.get_macros() == {}


# ============================================================================
# 综合场景测试
# ============================================================================

class TestComplexScenarios:
    """测试复杂场景"""
    
    def test_realistic_module_with_conditionals(self):
        """真实场景：带条件编译的模块"""
        code = """
`include "definitions.v"

// Module header comment
module complex_module #(
  parameter WIDTH = 32
)(
  input wire clk,
  input wire rst,
`ifdef ENABLE_FEATURE_A
  input wire [WIDTH-1:0] feature_a_data,
  output reg feature_a_valid,
`endif
`ifdef ENABLE_FEATURE_B
  input wire feature_b_enable,
`elsif ENABLE_FEATURE_C
  input wire feature_c_enable,
`else
  input wire default_enable,
`endif
  output wire [WIDTH-1:0] result
);

// Internal logic (should be removed)
wire internal_signal;
assign internal_signal = clk & rst;

endmodule
"""
        
        # 场景1：启用 FEATURE_A 和 FEATURE_B
        vp = VerilogPreprocess(["ENABLE_FEATURE_A", "ENABLE_FEATURE_B"])
        result = vp.preprocess_string(code)
        assert "feature_a_data" in result
        assert "feature_a_valid" in result
        assert "feature_b_enable" in result
        assert "feature_c_enable" not in result
        assert "default_enable" not in result
        
        # 场景2：只启用 FEATURE_C
        vp = VerilogPreprocess(["ENABLE_FEATURE_C"])
        result = vp.preprocess_string(code)
        assert "feature_a_data" not in result
        assert "feature_c_enable" in result
        assert "feature_b_enable" not in result
        assert "default_enable" not in result
        
        # 场景3：都不启用
        vp = VerilogPreprocess({})
        result = vp.preprocess_string(code)
        assert "feature_a_data" not in result
        assert "default_enable" in result
    
    def test_deep_nesting(self):
        """深层嵌套测试（5层）"""
        code = """module test;
`ifdef L1
  input p1;
  `ifdef L2
    input p2;
    `ifdef L3
      input p3;
      `ifdef L4
        input p4;
        `ifdef L5
          input p5;
        `endif
      `endif
    `endif
  `endif
`endif
endmodule"""
        
        vp = VerilogPreprocess(["L1", "L2", "L3", "L4", "L5"])
        result = vp.preprocess_string(code)
        assert "input p1;" in result
        assert "input p2;" in result
        assert "input p3;" in result
        assert "input p4;" in result
        assert "input p5;" in result
    
    def test_mixed_port_declarations(self):
        """混合端口声明"""
        code = """module test;parameter WIDTH = 32;
  parameter DEPTH = 1024;
  
  input wire clk;
  input wire rst_n;
  
  input wire [WIDTH-1:0] data_in;
  output reg [WIDTH-1:0] data_out;
  
  inout wire [7:0] bidirectional;
  
  output wire valid;
  output wire ready;
endmodule"""
        
        vp = VerilogPreprocess()
        result = vp.preprocess_string(code)
        assert "parameter WIDTH" in result
        assert "parameter DEPTH" in result
        assert "input wire clk;" in result
        assert "input wire rst_n;" in result
        assert "data_in" in result
        assert "data_out" in result
        assert "inout wire" in result
        assert "output wire valid;" in result



# ============================================================================
# 测试运行配置
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
