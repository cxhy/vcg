"""
VerilogPreprocess.py 单元测试
测试目标：VerilogLexer 词法分析器
测试框架：pytest
"""

import pytest
import os
import sys
from io import StringIO

# 导入被测试模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
from src.VerilogLexer import VerilogLexer


class TestVerilogLexerBasic:
    """基础功能测试"""
    
    def test_lexer_instantiation(self):
        """测试词法分析器实例化"""
        lexer = VerilogLexer()
        assert lexer is not None
    
    def test_lexer_build(self):
        """测试词法分析器构建"""
        lexer = VerilogLexer()
        lexer.build()
        # 构建成功，无异常即通过
    
    def test_input_without_build(self):
        """构造后 lexer 已自动 build，input() 可直接调用，不抛异常"""
        lexer = VerilogLexer()
        lexer.input("module test;")  # 应该不抛任何异常

    def test_token_without_build(self):
        """构造后 lexer 已自动 build，token() 可直接调用，不抛异常"""
        lexer = VerilogLexer()
        lexer.input("module test;")
        tok = lexer.token()
        assert tok is not None
        assert tok.type == "MODULE"


class TestTask10LexerDiagnostics:
    """TASK-10: lexer diagnostics and current-subset unsupported tokens."""

    def test_at_is_recognized_unsupported_not_invalid(self):
        lexer = VerilogLexer()
        lexer.input("@")

        assert lexer.token() is None
        diagnostic = lexer.get_diagnostics()[0]
        assert diagnostic.kind == "recognized_unsupported"
        assert diagnostic.spelling == "@"
        assert "current parser subset" in diagnostic.message

    def test_generate_keyword_is_recognized_unsupported(self):
        lexer = VerilogLexer()
        lexer.input("generate")

        assert lexer.token() is None
        diagnostic = lexer.get_diagnostics()[0]
        assert diagnostic.code == "VLEX_UNSUPPORTED_KEYWORD"
        assert diagnostic.kind == "recognized_unsupported"
        assert diagnostic.spelling == "generate"

    def test_unknown_control_character_is_invalid(self):
        lexer = VerilogLexer()
        lexer.input("\x01")

        assert lexer.token() is None
        diagnostic = lexer.get_diagnostics()[0]
        assert diagnostic.kind == "invalid"
        assert diagnostic.spelling == "\x01"


class TestKeywords:
    """关键字测试（14个）"""
    
    @pytest.fixture
    def lexer(self):
        """创建并构建词法分析器"""
        lex = VerilogLexer()
        lex.build()
        return lex
    
    @pytest.mark.parametrize("keyword,expected_type", [
        ("module", "MODULE"),
        ("MODULE", "MODULE"),
        ("Module", "MODULE"),
        ("endmodule", "ENDMODULE"),
        ("ENDMODULE", "ENDMODULE"),
        ("EndModule", "ENDMODULE"),
        ("input", "INPUT"),
        ("INPUT", "INPUT"),
        ("Input", "INPUT"),
        ("inout", "INOUT"),
        ("INOUT", "INOUT"),
        ("Inout", "INOUT"),
        ("output", "OUTPUT"),
        ("OUTPUT", "OUTPUT"),
        ("Output", "OUTPUT"),
        ("reg", "REG"),
        ("REG", "REG"),
        ("Reg", "REG"),
        ("logic", "LOGIC"),
        ("LOGIC", "LOGIC"),
        ("Logic", "LOGIC"),
        ("wire", "WIRE"),
        ("WIRE", "WIRE"),
        ("Wire", "WIRE"),
        ("parameter", "PARAMETER"),
        ("PARAMETER", "PARAMETER"),
        ("Parameter", "PARAMETER"),
        ("localparam", "LOCALPARAM"),
        ("LOCALPARAM", "LOCALPARAM"),
        ("LocalParam", "LOCALPARAM"),
        ("assign", "ASSIGN"),
        ("ASSIGN", "ASSIGN"),
        ("Assign", "ASSIGN"),
    ])
    def test_keywords(self, lexer, keyword, expected_type):
        """测试关键字识别（包括大小写变体）"""
        lexer.input(keyword)
        tok = lexer.token()
        assert tok is not None
        assert tok.type == expected_type
        assert tok.value.lower() == keyword.lower()


class TestArithmeticOperators:
    """算术运算符测试（6个）"""
    
    @pytest.fixture
    def lexer(self):
        lex = VerilogLexer()
        lex.build()
        return lex
    
    @pytest.mark.parametrize("operator,expected_type", [
        ("+", "PLUS"),
        ("-", "MINUS"),
        ("*", "TIMES"),
        ("/", "DIVIDE"),
        ("%", "MOD"),
        ("**", "POWER"),
    ])
    def test_arithmetic_operators(self, lexer, operator, expected_type):
        """测试算术运算符"""
        lexer.input(operator)
        tok = lexer.token()
        assert tok is not None
        assert tok.type == expected_type
        assert tok.value == operator


class TestBitwiseOperators:
    """位运算符测试（5个）"""
    
    @pytest.fixture
    def lexer(self):
        lex = VerilogLexer()
        lex.build()
        return lex
    
    @pytest.mark.parametrize("operator,expected_type", [
        ("~", "NOT"),
        ("|", "OR"),
        ("&", "AND"),
        ("^", "XOR"),
        ("^~", "XNOR"),
        ("~^", "XNOR"),
    ])
    def test_bitwise_operators(self, lexer, operator, expected_type):
        """测试位运算符"""
        lexer.input(operator)
        tok = lexer.token()
        assert tok is not None
        assert tok.type == expected_type


class TestLogicalOperators:
    """逻辑运算符测试（3个）"""
    
    @pytest.fixture
    def lexer(self):
        lex = VerilogLexer()
        lex.build()
        return lex
    
    @pytest.mark.parametrize("operator,expected_type", [
        ("&&", "LAND"),
        ("||", "LOR"),
        ("!", "LNOT"),
    ])
    def test_logical_operators(self, lexer, operator, expected_type):
        """测试逻辑运算符"""
        lexer.input(operator)
        tok = lexer.token()
        assert tok is not None
        assert tok.type == expected_type


class TestShiftOperators:
    """移位运算符测试（2个）"""
    
    @pytest.fixture
    def lexer(self):
        lex = VerilogLexer()
        lex.build()
        return lex
    
    @pytest.mark.parametrize("operator,expected_type", [
        ("<<", "LSHIFT"),
        (">>", "RSHIFT"),
    ])
    def test_shift_operators(self, lexer, operator, expected_type):
        """测试移位运算符"""
        lexer.input(operator)
        tok = lexer.token()
        assert tok is not None
        assert tok.type == expected_type


class TestComparisonOperators:
    """比较运算符测试（6个）"""
    
    @pytest.fixture
    def lexer(self):
        lex = VerilogLexer()
        lex.build()
        return lex
    
    @pytest.mark.parametrize("operator,expected_type", [
        ("<", "LT"),
        (">", "GT"),
        ("<=", "LE"),
        (">=", "GE"),
        ("==", "EQ"),
        ("!=", "NE"),
    ])
    def test_comparison_operators(self, lexer, operator, expected_type):
        """测试比较运算符"""
        lexer.input(operator)
        tok = lexer.token()
        assert tok is not None
        assert tok.type == expected_type


class TestOtherOperators:
    """其他运算符测试（3个）"""
    
    @pytest.fixture
    def lexer(self):
        lex = VerilogLexer()
        lex.build()
        return lex
    
    @pytest.mark.parametrize("operator,expected_type", [
        ("=", "EQUALS"),
        ("?", "COND"),
        ("#", "HASH"),
    ])
    def test_other_operators(self, lexer, operator, expected_type):
        """测试其他运算符"""
        lexer.input(operator)
        tok = lexer.token()
        assert tok is not None
        assert tok.type == expected_type


class TestDelimiters:
    """分隔符与括号测试（9个）"""
    
    @pytest.fixture
    def lexer(self):
        lex = VerilogLexer()
        lex.build()
        return lex
    
    @pytest.mark.parametrize("delimiter,expected_type", [
        ("(", "LPAREN"),
        (")", "RPAREN"),
        ("[", "LBRACKET"),
        ("]", "RBRACKET"),
        ("{", "LBRACE"),
        ("}", "RBRACE"),
        (",", "COMMA"),
        (";", "SEMICOLON"),
        (":", "COLON"),
    ])
    def test_delimiters(self, lexer, delimiter, expected_type):
        """测试分隔符和括号"""
        lexer.input(delimiter)
        tok = lexer.token()
        assert tok is not None
        assert tok.type == expected_type


class TestNumberLiterals:
    """数字字面量测试（4种进制）"""
    
    @pytest.fixture
    def lexer(self):
        lex = VerilogLexer()
        lex.build()
        return lex
    
    @pytest.mark.parametrize("number,expected_type,expected_value", [
        # 十进制
        ("123", "INTNUMBER_DEC", "123"),
        ("8'd255", "INTNUMBER_DEC", "8'd255"),
        ("'d100", "INTNUMBER_DEC", "'d100"),
        ("1_000_000", "INTNUMBER_DEC", "1000000"),
        ("32'd1_000_000", "INTNUMBER_DEC", "32'd1000000"),
        # 十六进制
        ("8'hFF", "INTNUMBER_HEX", "8'hFF"),
        ("'hAB", "INTNUMBER_HEX", "'hAB"),
        ("32'hDEAD_BEEF", "INTNUMBER_HEX", "32'hDEADBEEF"),
        ("16'haBcD", "INTNUMBER_HEX", "16'haBcD"),
        # 八进制
        ("8'o377", "INTNUMBER_OCT", "8'o377"),
        ("'o77", "INTNUMBER_OCT", "'o77"),
        ("16'o1_234", "INTNUMBER_OCT", "16'o1234"),
        # 二进制
        ("8'b11111111", "INTNUMBER_BIN", "8'b11111111"),
        ("'b1010", "INTNUMBER_BIN", "'b1010"),
        ("4'b10_11", "INTNUMBER_BIN", "4'b1011"),
    ])
    def test_number_literals(self, lexer, number, expected_type, expected_value):
        """测试各种进制的数字字面量"""
        lexer.input(number)
        tok = lexer.token()
        assert tok is not None
        assert tok.type == expected_type
        assert tok.value == expected_value


class TestStringLiterals:
    """字符串字面量测试"""
    
    @pytest.fixture
    def lexer(self):
        lex = VerilogLexer()
        lex.build()
        return lex
    
    @pytest.mark.parametrize("string_input,expected_value", [
        ('"Hello"', 'Hello'),
        ('""', ''),
        ('"Line1\\nLine2"', 'Line1\nLine2'),
        ('"Tab\\there"', 'Tab\there'),
        ('"Quote: \\"text\\""', 'Quote: "text"'),
        ('"Backslash: \\\\"', 'Backslash: \\'),
        # Regression (task 04): escaped backslash followed by n must remain
        # literal "\n" (backslash+n), NOT be further interpreted as newline.
        ('"a\\\\nb"', 'a\\nb'),
        # Regression (task 04): pure `\\` -> single backslash.
        ('"a\\\\b"', 'a\\b'),
    ])
    def test_string_literals(self, lexer, string_input, expected_value):
        """测试字符串字面量（包括转义字符）"""
        lexer.input(string_input)
        tok = lexer.token()
        assert tok is not None
        assert tok.type == "STRING_LITERAL"
        assert tok.value == expected_value


class TestIdentifiers:
    """标识符测试"""
    
    @pytest.fixture
    def lexer(self):
        lex = VerilogLexer()
        lex.build()
        return lex
    
    @pytest.mark.parametrize("identifier", [
        "clk",
        "_reset",
        "`define",
        "$display",
        "data123",
        "a_b_c",
        "CLK",
    ])
    def test_identifiers(self, lexer, identifier):
        """测试各种格式的标识符"""
        lexer.input(identifier)
        tok = lexer.token()
        assert tok is not None
        assert tok.type == "ID"
        assert tok.value == identifier


class TestComments:
    """注释测试"""
    
    @pytest.fixture
    def lexer(self):
        lex = VerilogLexer()
        lex.build()
        return lex
    
    def test_single_line_comment(self, lexer):
        """测试单行注释"""
        lexer.input("// comment")
        tok = lexer.token()
        assert tok is None
    
    def test_multi_line_comment(self, lexer):
        """测试多行注释"""
        lexer.input("/* comment */")
        tok = lexer.token()
        assert tok is None
    
    def test_multi_line_comment_with_newline(self, lexer):
        """测试包含换行的多行注释"""
        lexer.input("/* line1\nline2 */")
        tok = lexer.token()
        assert tok is None
    
    def test_comment_between_tokens(self, lexer):
        """测试token之间的注释"""
        lexer.input("a // comment\nb")
        tok1 = lexer.token()
        assert tok1 is not None
        assert tok1.type == "ID"
        assert tok1.value == "a"
        
        tok2 = lexer.token()
        assert tok2 is not None
        assert tok2.type == "ID"
        assert tok2.value == "b"


class TestWhitespace:
    """空白字符测试"""
    
    @pytest.fixture
    def lexer(self):
        lex = VerilogLexer()
        lex.build()
        return lex
    
    def test_spaces(self, lexer):
        """测试空格"""
        lexer.input("   ")
        tok = lexer.token()
        assert tok is None
    
    def test_tabs(self, lexer):
        """测试制表符"""
        lexer.input("\t")
        tok = lexer.token()
        assert tok is None
    
    def test_newlines(self, lexer):
        """测试换行符"""
        lexer.input("\n")
        tok = lexer.token()
        assert tok is None
    
    def test_whitespace_between_tokens(self, lexer):
        """测试token之间的空白"""
        lexer.input("a   b")
        tok1 = lexer.token()
        assert tok1 is not None
        assert tok1.type == "ID"
        assert tok1.value == "a"
        
        tok2 = lexer.token()
        assert tok2 is not None
        assert tok2.type == "ID"
        assert tok2.value == "b"


class TestBoundaryConditions:
    """边界条件测试"""
    
    @pytest.fixture
    def lexer(self):
        lex = VerilogLexer()
        lex.build()
        return lex
    
    def test_empty_input(self, lexer):
        """测试空输入"""
        lexer.input("")
        tok = lexer.token()
        assert tok is None
    
    def test_only_comments(self, lexer):
        """测试仅包含注释的输入"""
        lexer.input("// only comment")
        tok = lexer.token()
        assert tok is None
    
    def test_only_whitespace(self, lexer):
        """测试仅包含空白字符的输入"""
        lexer.input("   \t\n   ")
        tok = lexer.token()
        assert tok is None


class TestOperatorAmbiguity:
    """运算符歧义测试"""
    
    @pytest.fixture
    def lexer(self):
        lex = VerilogLexer()
        lex.build()
        return lex
    
    def test_power_not_double_times(self, lexer):
        """测试**识别为POWER而非两个TIMES"""
        lexer.input("**")
        tok = lexer.token()
        assert tok is not None
        assert tok.type == "POWER"
        # 确保没有第二个token
        tok2 = lexer.token()
        assert tok2 is None
    
    def test_lshift_not_double_lt(self, lexer):
        """测试<<识别为LSHIFT而非两个LT"""
        lexer.input("<<")
        tok = lexer.token()
        assert tok is not None
        assert tok.type == "LSHIFT"
        tok2 = lexer.token()
        assert tok2 is None
    
    def test_rshift_not_double_gt(self, lexer):
        """测试>>识别为RSHIFT而非两个GT"""
        lexer.input(">>")
        tok = lexer.token()
        assert tok is not None
        assert tok.type == "RSHIFT"
        tok2 = lexer.token()
        assert tok2 is None
    
    def test_le_not_lt_equals(self, lexer):
        """测试<=识别为LE而非LT+EQUALS"""
        lexer.input("<=")
        tok = lexer.token()
        assert tok is not None
        assert tok.type == "LE"
        tok2 = lexer.token()
        assert tok2 is None
    
    def test_ge_not_gt_equals(self, lexer):
        """测试>=识别为GE而非GT+EQUALS"""
        lexer.input(">=")
        tok = lexer.token()
        assert tok is not None
        assert tok.type == "GE"
        tok2 = lexer.token()
        assert tok2 is None
    
    def test_eq_not_double_equals(self, lexer):
        """测试==识别为EQ而非两个EQUALS"""
        lexer.input("==")
        tok = lexer.token()
        assert tok is not None
        assert tok.type == "EQ"
        tok2 = lexer.token()
        assert tok2 is None
    
    def test_ne_not_lnot_equals(self, lexer):
        """测试!=识别为NE而非LNOT+EQUALS"""
        lexer.input("!=")
        tok = lexer.token()
        assert tok is not None
        assert tok.type == "NE"
        tok2 = lexer.token()
        assert tok2 is None
    
    def test_land_not_double_and(self, lexer):
        """测试&&识别为LAND而非两个AND"""
        lexer.input("&&")
        tok = lexer.token()
        assert tok is not None
        assert tok.type == "LAND"
        tok2 = lexer.token()
        assert tok2 is None
    
    def test_lor_not_double_or(self, lexer):
        """测试||识别为LOR而非两个OR"""
        lexer.input("||")
        tok = lexer.token()
        assert tok is not None
        assert tok.type == "LOR"
        tok2 = lexer.token()
        assert tok2 is None
    
    def test_xnor_caret_tilde(self, lexer):
        """测试^~识别为XNOR"""
        lexer.input("^~")
        tok = lexer.token()
        assert tok is not None
        assert tok.type == "XNOR"
        tok2 = lexer.token()
        assert tok2 is None
    
    def test_xnor_tilde_caret(self, lexer):
        """测试~^识别为XNOR"""
        lexer.input("~^")
        tok = lexer.token()
        assert tok is not None
        assert tok.type == "XNOR"
        tok2 = lexer.token()
        assert tok2 is None


class TestErrorHandling:
    """错误处理测试"""
    
    @pytest.fixture
    def lexer(self):
        lex = VerilogLexer()
        lex.build()
        return lex
    
    def test_illegal_character(self, lexer, caplog):
        """测试当前子集不支持字符的诊断记录"""
        lexer.input("module @test;")

        # 获取第一个token（module）
        tok1 = lexer.token()
        assert tok1 is not None
        assert tok1.type == "MODULE"

        # @被诊断并消费以继续扫描，下一个是test
        tok2 = lexer.token()
        assert tok2 is not None
        assert tok2.type == "ID"
        assert tok2.value == "test"

        diagnostic = lexer.get_diagnostics()[0]
        assert diagnostic.kind == "recognized_unsupported"
        assert diagnostic.spelling == "@"
        assert "current parser subset" in diagnostic.message


class TestComplexExpressions:
    """复杂表达式测试"""
    
    @pytest.fixture
    def lexer(self):
        lex = VerilogLexer()
        lex.build()
        return lex
    
    def test_module_declaration(self, lexer):
        """测试完整模块声明"""
        lexer.input("module test; endmodule")
        
        tokens = []
        while True:
            tok = lexer.token()
            if not tok:
                break
            tokens.append((tok.type, tok.value))
        
        expected = [
            ("MODULE", "module"),
            ("ID", "test"),
            ("SEMICOLON", ";"),
            ("ENDMODULE", "endmodule")
        ]
        assert tokens == expected
    
    def test_port_declaration(self, lexer):
        """测试端口声明"""
        lexer.input("input [7:0] data")
        
        tokens = []
        while True:
            tok = lexer.token()
            if not tok:
                break
            tokens.append((tok.type, tok.value))
        
        expected = [
            ("INPUT", "input"),
            ("LBRACKET", "["),
            ("INTNUMBER_DEC", "7"),
            ("COLON", ":"),
            ("INTNUMBER_DEC", "0"),
            ("RBRACKET", "]"),
            ("ID", "data")
        ]
        assert tokens == expected
    
    def test_assign_statement(self, lexer):
        """测试赋值语句"""
        lexer.input("assign a = b + c")
        
        tokens = []
        while True:
            tok = lexer.token()
            if not tok:
                break
            tokens.append((tok.type, tok.value))
        
        expected = [
            ("ASSIGN", "assign"),
            ("ID", "a"),
            ("EQUALS", "="),
            ("ID", "b"),
            ("PLUS", "+"),
            ("ID", "c")
        ]
        assert tokens == expected
    
    def test_conditional_expression(self, lexer):
        """测试条件表达式"""
        lexer.input("a ? b : c")
        
        tokens = []
        while True:
            tok = lexer.token()
            if not tok:
                break
            tokens.append((tok.type, tok.value))
        
        expected = [
            ("ID", "a"),
            ("COND", "?"),
            ("ID", "b"),
            ("COLON", ":"),
            ("ID", "c")
        ]
        assert tokens == expected
    
    def test_complex_logical_expression(self, lexer):
        """测试复杂逻辑表达式"""
        lexer.input("(a && b) || c")
        
        tokens = []
        while True:
            tok = lexer.token()
            if not tok:
                break
            tokens.append((tok.type, tok.value))
        
        expected = [
            ("LPAREN", "("),
            ("ID", "a"),
            ("LAND", "&&"),
            ("ID", "b"),
            ("RPAREN", ")"),
            ("LOR", "||"),
            ("ID", "c")
        ]
        assert tokens == expected
    
    def test_parameter_declaration(self, lexer):
        """测试参数声明"""
        lexer.input("parameter SIZE = 8")
        
        tokens = []
        while True:
            tok = lexer.token()
            if not tok:
                break
            tokens.append((tok.type, tok.value))
        
        expected = [
            ("PARAMETER", "parameter"),
            ("ID", "SIZE"),
            ("EQUALS", "="),
            ("INTNUMBER_DEC", "8")
        ]
        assert tokens == expected


class TestTokenAttributes:
    """Token属性测试"""
    
    @pytest.fixture
    def lexer(self):
        lex = VerilogLexer()
        lex.build()
        return lex
    
    def test_token_has_type(self, lexer):
        """测试Token具有type属性"""
        lexer.input("module")
        tok = lexer.token()
        assert hasattr(tok, 'type')
        assert tok.type == "MODULE"
    
    def test_token_has_value(self, lexer):
        """测试Token具有value属性"""
        lexer.input("module")
        tok = lexer.token()
        assert hasattr(tok, 'value')
        assert tok.value == "module"
    
    def test_token_has_lineno(self, lexer):
        """测试Token具有lineno属性"""
        lexer.input("module")
        tok = lexer.token()
        assert hasattr(tok, 'lineno')
        assert tok.lineno == 1
    
    def test_token_has_lexpos(self, lexer):
        """测试Token具有lexpos属性"""
        lexer.input("module")
        tok = lexer.token()
        assert hasattr(tok, 'lexpos')
        assert tok.lexpos == 0
    
    def test_lineno_increment(self, lexer):
        """测试行号递增"""
        lexer.input("module\ntest")
        tok1 = lexer.token()
        assert tok1.lineno == 1
        
        tok2 = lexer.token()
        assert tok2.lineno == 2


class TestRealWorldVerilog:
    """真实Verilog代码测试"""
    
    @pytest.fixture
    def lexer(self):
        lex = VerilogLexer()
        lex.build()
        return lex
    
    def test_simple_adder_module(self, lexer):
        """测试简单加法器模块"""
        code = """module adder(
    input [7:0] a,
    input [7:0] b,
    output [8:0] sum
);
    assign sum = a + b;
endmodule"""
        
        lexer.input(code)
        
        tokens = []
        while True:
            tok = lexer.token()
            if not tok:
                break
            tokens.append(tok.type)
        
        # 验证关键token存在
        assert "MODULE" in tokens
        assert "ENDMODULE" in tokens
        assert "INPUT" in tokens
        assert "OUTPUT" in tokens
        assert "ASSIGN" in tokens
        assert tokens.count("ID") >= 3  # a, b, sum
    
    def test_parameter_usage(self, lexer):
        """测试参数使用"""
        code = "parameter WIDTH = 32'd8"
        lexer.input(code)
        
        tokens = []
        while True:
            tok = lexer.token()
            if not tok:
                break
            tokens.append((tok.type, tok.value))
        
        expected = [
            ("PARAMETER", "parameter"),
            ("ID", "WIDTH"),
            ("EQUALS", "="),
            ("INTNUMBER_DEC", "32'd8")
        ]
        assert tokens == expected
    
    def test_wire_declaration(self, lexer):
        """测试线网声明"""
        code = "wire [15:0] data_bus"
        lexer.input(code)
        
        tokens = []
        while True:
            tok = lexer.token()
            if not tok:
                break
            tokens.append(tok.type)
        
        assert tokens[0] == "WIRE"
        assert "LBRACKET" in tokens
        assert "RBRACKET" in tokens
        assert "ID" in tokens


class TestEdgeCases:
    """边缘情况测试"""
    
    @pytest.fixture
    def lexer(self):
        lex = VerilogLexer()
        lex.build()
        return lex
    
    def test_number_followed_by_identifier(self, lexer):
        """测试数字后跟标识符的情况"""
        lexer.input("123abc")
        
        tok1 = lexer.token()
        assert tok1 is not None
        assert tok1.type == "INTNUMBER_DEC"
        assert tok1.value == "123"
        
        tok2 = lexer.token()
        assert tok2 is not None
        assert tok2.type == "ID"
        assert tok2.value == "abc"
    
    def test_consecutive_operators(self, lexer):
        """测试连续运算符"""
        lexer.input("a++b")
        
        tokens = []
        while True:
            tok = lexer.token()
            if not tok:
                break
            tokens.append((tok.type, tok.value))
        
        # 应识别为 ID, PLUS, PLUS, ID
        assert len(tokens) == 4
        assert tokens[0] == ("ID", "a")
        assert tokens[1] == ("PLUS", "+")
        assert tokens[2] == ("PLUS", "+")
        assert tokens[3] == ("ID", "b")
    
    def test_empty_string(self, lexer):
        """测试空字符串字面量"""
        lexer.input('""')
        tok = lexer.token()
        assert tok is not None
        assert tok.type == "STRING_LITERAL"
        assert tok.value == ""
    
    def test_multiline_code(self, lexer):
        """测试多行代码的行号追踪"""
        code = "module\ntest\n;"
        lexer.input(code)
        
        tok1 = lexer.token()
        assert tok1.lineno == 1
        
        tok2 = lexer.token()
        assert tok2.lineno == 2
        
        tok3 = lexer.token()
        assert tok3.lineno == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
