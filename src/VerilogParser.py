#!/usr/bin/env python3
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

# Copyright (C) 2025 cxhy <cxhy1981@gmail.com>
#
# Author: cxhy
# Created: 2025-07-31
# Description: 
import ply.yacc as yacc
from typing import Optional, List, Any, Union, Dict, Tuple
import sys

from VerilogLexer import VerilogLexer
from VerilogAst import (
    DesignUnit, ModuleDeclaration, ParameterDeclaration, PortDeclaration,
    Identifier, NumericLiteral, StringLiteral, ErrorNode, RangeExpression,
    ASTBuilder, VerilogAST, VerilogASTError, ExpressionSimplifier
)
from VerilogPreprocess import VerilogPreprocess

MacrosType = Union[Dict[str, str], List[str], List[Tuple[str, str]], None]

class VerilogParser:
    
    def __init__(self, lexer: Optional[VerilogLexer] = None, debug: bool = False):
        self.lexer = lexer or VerilogLexer()
        self.debug = debug
        self.tokens = self.lexer.tokens
        self.ast_builder = ASTBuilder()
        self.parser = None
        self.error_count = 0
        
        self._build_parser()
    
    def _build_parser(self):
        self.parser = yacc.yacc(
            module=self,
            debug=self.debug,
            write_tables=False
        )
    
    precedence = (
        ('right', 'COND', 'COLON'),

        ('left', 'LOR'),
        ('left', 'LAND'),

        ('left', 'OR'),
        ('left', 'XOR', 'XNOR'),
        ('left', 'AND'),
        
        #('left', 'EQ', 'NE', 'EQL', 'NEL'),
        ('left', 'EQ', 'NE' ),
        ('left', 'LT', 'GT', 'LE', 'GE'),
        
        #('left', 'LSHIFT', 'RSHIFT', 'LSHIFTA', 'RSHIFTA'),
        ('left', 'LSHIFT', 'RSHIFT'),
        
        ('left', 'PLUS', 'MINUS'),
        ('left', 'TIMES', 'DIVIDE', 'MOD'),
        ('right', 'POWER'),
        
        ('right', 'UMINUS', 'UPLUS', 'UNOT'),
    )
    
    
    def p_design_unit(self, p):
        """design_unit : module_declaration"""
        design_unit = self.ast_builder.create_design_unit()
        if p[1] is not None:
            design_unit.add_module(p[1])
        p[0] = design_unit
    
    def p_design_unit_empty(self, p):
        """design_unit : empty"""
        p[0] = self.ast_builder.create_design_unit()
    
    def p_module_declaration(self, p):
        """module_declaration : MODULE module_name opt_parameter_list opt_port_list SEMICOLON module_item_list ENDMODULE"""
        module = self.ast_builder.create_module_declaration(p[2])
        
        if p[3]:
            for param in p[3]:
                self.ast_builder.add_parameter(module, param)

        complete_ports = self.ast_builder.get_module_ports(p[2])

        port_errors = self.ast_builder.validate_module_ports(p[2])
        if port_errors:
            for error in port_errors:
                print(f"Warning Ports decl: {error}")
        
        for port_info in complete_ports:
            if port_info._is_fully_defined():
                port_decl = PortDeclaration(
                    identifier=port_info.name,
                    direction=port_info.direction,
                    net_type=port_info.net_type,
                    range_expr=port_info.range_expr
                )
                self.ast_builder.add_port(module, port_decl)

        self.ast_builder.pop_module_context()
        p[0] = module
    
    def p_module_declaration_error(self, p):
        """module_declaration : MODULE module_name error ENDMODULE"""
        self._syntax_error(p, "Invalid module declaration")
        module = self.ast_builder.create_module_declaration(p[2])
        self.ast_builder.set_body_ignored(module)
        self.ast_builder.pop_module_context()
        p[0] = module
    
    def p_module_name(self, p):
        """module_name : ID"""
        self.ast_builder.push_module_context(p[1])
        p[0] = p[1]
    
    def p_opt_parameter_list(self, p):
        """opt_parameter_list : HASH LPAREN parameter_declaration_list RPAREN"""
        p[0] = p[3]
    
    def p_opt_parameter_list_empty(self, p):
        """opt_parameter_list : empty"""
        p[0] = []
    
    def p_opt_parameter_list_error(self, p):
        """opt_parameter_list : HASH LPAREN error RPAREN"""
        self._syntax_error(p, "Invalid parameter list")
        p[0] = []
    
    def p_parameter_declaration_list(self, p):
        """parameter_declaration_list : parameter_declaration"""
        if p[1] is not None:
            p[0] = [p[1]]
        else:
            p[0] = []
    
    def p_parameter_declaration_list_multiple(self, p):
        """parameter_declaration_list : parameter_declaration_list COMMA parameter_declaration"""
        param_list = p[1] or []
        if p[3] is not None:
            param_list.append(p[3])
        p[0] = param_list
    
    def p_parameter_declaration(self, p):
        """parameter_declaration : PARAMETER param_assignment
                                 | LOCALPARAM param_assignment"""
        param_type = p[1].lower()
        if p[2] is not None:
            identifier, default_value = p[2]
            param = self.ast_builder.create_parameter(
                identifier=identifier,
                parameter_type=param_type,
                default_value=default_value
            )
            p[0] = param
        else:
            p[0] = None
    
    def p_parameter_declaration_error(self, p):
        """parameter_declaration : PARAMETER error
                                 | LOCALPARAM error"""
        self._syntax_error(p, f"Invalid {p[1]} declaration")
        p[0] = None
    
    def p_param_assignment(self, p):
        """param_assignment : ID EQUALS expression"""
        p[0] = (p[1], p[3])
    
    def p_param_assignment_error(self, p):
        """param_assignment : ID EQUALS error"""
        self._syntax_error(p, "Invalid parameter assignment")
        p[0] = None
    
    def p_opt_port_list(self, p):
        """opt_port_list : LPAREN port_list RPAREN"""
        p[0] = p[2]
    
    def p_opt_port_list_empty_parens(self, p):
        """opt_port_list : LPAREN RPAREN"""
        p[0] = []
    
    def p_opt_port_list_empty(self, p):
        """opt_port_list : empty"""
        p[0] = []
    
    def p_opt_port_list_error(self, p):
        """opt_port_list : LPAREN error RPAREN"""
        self._syntax_error(p, "Invalid port list")
        p[0] = []
    
    def p_port_list(self, p):
        """port_list : port_declaration"""
        if p[1] is not None:
            p[0] = [p[1]]
        else:
            p[0] = []
    
    def p_port_list_multiple(self, p):
        """port_list : port_list COMMA port_declaration"""
        port_list = p[1] or []
        if p[3] is not None:
            port_list.append(p[3])
        p[0] = port_list
    
    def p_port_declaration(self, p):
        """port_declaration : opt_port_direction opt_net_or_reg_type opt_packed_dimension port_identifier"""
        direction = p[1] 
        net_type = p[2] 
        range_info = p[3]  
        identifier = p[4]
        
        if identifier and self.ast_builder.current_parsing_module:
            msb_expr = range_info[0] if range_info else None
            lsb_expr = range_info[1] if range_info else None

            self.ast_builder.register_port_from_list(
                self.ast_builder.current_parsing_module,
                identifier,
                direction,
                net_type or "wire",  
                msb_expr,
                lsb_expr
            )
        p[0] = {
            'name': identifier,
            'direction': direction,
            'net_type': net_type,
            'msb_expr': range_info[0] if range_info else None,
            'lsb_expr': range_info[1] if range_info else None
        }
    
    def p_port_declaration_error(self, p):
        """port_declaration : error"""
        self._syntax_error(p, "Invalid port declaration")
        p[0] = None
    
    def p_opt_port_direction(self, p):
        """opt_port_direction : INPUT
                              | OUTPUT
                              | INOUT"""
        p[0] = p[1].lower()
    
    def p_opt_port_direction_empty(self, p):
        """opt_port_direction : empty"""
        p[0] = None
    
    def p_opt_net_or_reg_type(self, p):
        """opt_net_or_reg_type : WIRE
                               | REG
                               | LOGIC"""
        p[0] = p[1].lower()
    
    def p_opt_net_or_reg_type_empty(self, p):
        """opt_net_or_reg_type : empty"""
        p[0] = None
    
    def p_opt_packed_dimension(self, p):
        """opt_packed_dimension : LBRACKET expression COLON expression RBRACKET"""
        msb_expr = str(p[2])
        lsb_expr = str(p[4])
        p[0] = (msb_expr, lsb_expr)
    
    def p_opt_packed_dimension_empty(self, p):
        """opt_packed_dimension : empty"""
        p[0] = None
    
    def p_opt_packed_dimension_error(self, p):
        """opt_packed_dimension : LBRACKET error RBRACKET"""
        self._syntax_error(p, "Invalid packed dimension")
        p[0] = None
    
    def p_port_identifier(self, p):
        """port_identifier : ID"""
        p[0] = p[1]
     
    def p_module_item_list_empty(self, p):
        """module_item_list : empty"""
        p[0] = None
    
    def p_module_item_list_error(self, p):
        """module_item_list : module_item_list error SEMICOLON"""
        p[0] = None
    
    def p_module_item_list_single(self, p):
        """module_item_list : module_item"""
        if p[1] is not None:
            p[0] = [p[1]]
        else:
            p[0] = []
            
    def p_module_item_list_multiple(self, p):
        """module_item_list : module_item_list module_item"""
        items = p[1] or []
        if p[2] is not None:
            items.append(p[2])
        p[0] = items


    def p_module_item(self, p):
        """module_item : module_item_declaration
                       | module_item_assignment
                       | module_item_always
                       | module_item_instance"""
        p[0] = p[1]

    def p_module_item_declaration(self, p):
        """module_item_declaration : INPUT opt_net_or_reg_type opt_packed_dimension port_identifier SEMICOLON
                                   | OUTPUT opt_net_or_reg_type opt_packed_dimension port_identifier SEMICOLON
                                   | INOUT opt_net_or_reg_type opt_packed_dimension port_identifier SEMICOLON
                                   | WIRE opt_packed_dimension port_identifier SEMICOLON
                                   | REG opt_packed_dimension port_identifier SEMICOLON
                                   | LOGIC opt_packed_dimension port_identifier SEMICOLON
                                   | PARAMETER module_parameter_assignment_list SEMICOLON
                                   | LOCALPARAM module_parameter_assignment_list SEMICOLON"""

        if p[1] in ['input', 'output', 'inout']:
            direction = p[1].lower()
            net_type = p[2] or "wire"
            range_info = p[3]
            identifier = p[4]

            if identifier and self.ast_builder.current_parsing_module:
                msb_expr = range_info[0] if range_info else None
                lsb_expr = range_info[1] if range_info else None

                self.ast_builder.register_port_from_body(
                    self.ast_builder.current_parsing_module,
                    identifier,
                    direction,
                    net_type,
                    msb_expr,
                    lsb_expr
                )

        elif p[1] in ['wire', 'reg', 'logic']:
            pass
        
        elif p[1] in ['parameter', 'localparam']:
            param_type = p[1].lower()
            param_list = p[2] or []

            for param_info in param_list:
                param = self.ast_builder.create_parameter(
                    identifier=param_info['identifier'],
                    parameter_type=param_type,
                    default_value=str(param_info['default_value']) if param_info['default_value'] else ""
                )
                self.ast_builder.add_parameter_to_current_or_pending(param)

        p[0] = None
    
    def p_module_parameter_assignment_list(self, p):
        """module_parameter_assignment_list : param_assignment"""
        if p[1] is not None:
            identifier, default_value = p[1]
            param_info = {
                'identifier': identifier,
                'default_value': default_value
            }
            p[0] = [param_info]
        else:
            p[0] = []
    
    def p_module_parameter_assignment_list_multiple(self, p):
        """module_parameter_assignment_list : module_parameter_assignment_list COMMA param_assignment"""
        param_list = p[1] or []
        if p[3] is not None:
            identifier, default_value = p[3]
            param_info = {
                'identifier': identifier,
                'default_value': default_value
            }
            param_list.append(param_info)
        p[0] = param_list


    def p_module_item_assignment(self, p):
        """module_item_assignment : ASSIGN expression EQUALS expression SEMICOLON"""
        p[0] = None
    
    def p_module_item_always(self, p):
        """module_item_always : ALWAYS expression BEGIN expression_list END"""
        p[0] = None
    
    def p_module_item_instance(self, p):
        """module_item_instance : ID ID LPAREN expression_list RPAREN SEMICOLON"""
        p[0] = None

    def p_expression_primary(self, p):
        """expression : primary"""
        p[0] = p[1]
    
    def p_expression_unary(self, p):
        """expression : PLUS expression %prec UPLUS
                      | MINUS expression %prec UMINUS
                      | NOT expression %prec UNOT
                      | LNOT expression %prec UNOT"""
        p[0] = f"{p[1]}{p[2]}"
    
    def p_expression_binary(self, p):
        """expression : expression PLUS expression
                      | expression MINUS expression
                      | expression TIMES expression
                      | expression DIVIDE expression
                      | expression MOD expression
                      | expression POWER expression
                      | expression LT expression
                      | expression GT expression
                      | expression LE expression
                      | expression GE expression
                      | expression EQ expression
                      | expression NE expression
                      | expression LAND expression
                      | expression LOR expression
                      | expression AND expression
                      | expression OR expression
                      | expression XOR expression
                      | expression XNOR expression
                      | expression LSHIFT expression
                      | expression RSHIFT expression"""
        left = str(p[1])
        op = str(p[2])
        right = str(p[3])
        
        if op == '-':
            p[0] = f"{left}-{right}"
        else:
            p[0] = f"{left}{op}{right}"
    
    def p_expression_conditional(self, p):
        """expression : expression COND expression COLON expression"""
        p[0] = f"({p[1]} ? {p[3]} : {p[5]})"
    
    def p_expression_parentheses(self, p):
        """expression : LPAREN expression RPAREN"""
        p[0] = str(p[2]) 
    
    def p_expression_concatenation(self, p):
        """expression : concatenation"""
        p[0] = p[1]
    
    def p_primary_number(self, p):
        """primary : INTNUMBER_DEC
                   | INTNUMBER_HEX
                   | INTNUMBER_OCT
                   | INTNUMBER_BIN"""
        p[0] = str(p[1])
    
    def p_primary_identifier(self, p):
        """primary : ID"""
        p[0] = str(p[1])
    
    def p_primary_string(self, p):
        """primary : STRING_LITERAL"""
        p[0] = f'"{p[1]}"'
    
    def p_primary_bit_select(self, p):
        """primary : ID LBRACKET expression RBRACKET"""
        p[0] = f"{p[1]}[{p[3]}]"
    
    def p_primary_bit_select_error(self, p):
        """primary : ID LBRACKET error RBRACKET"""
        self._syntax_error(p, "Invalid bit selection")
        p[0] = f"{p[1]}[ERROR]"
    
    def p_primary_part_select(self, p):
        """primary : ID LBRACKET expression COLON expression RBRACKET"""
        p[0] = f"{p[1]}[{p[3]}:{p[5]}]"
    
    def p_primary_part_select_error(self, p):
        """primary : ID LBRACKET error COLON error RBRACKET"""
        self._syntax_error(p, "Invalid part selection")
        p[0] = f"{p[1]}[ERROR:ERROR]"
    
    def p_primary_signed_number(self, p):
        """primary : PLUS INTNUMBER_DEC %prec UPLUS
                   | PLUS INTNUMBER_HEX %prec UPLUS
                   | PLUS INTNUMBER_OCT %prec UPLUS  
                   | PLUS INTNUMBER_BIN %prec UPLUS
                   | MINUS INTNUMBER_DEC %prec UMINUS
                   | MINUS INTNUMBER_HEX %prec UMINUS
                   | MINUS INTNUMBER_OCT %prec UMINUS
                   | MINUS INTNUMBER_BIN %prec UMINUS"""
        p[0] = f"{p[1]}{p[2]}"
    
    def p_primary_function_call(self, p):
        """primary : ID LPAREN expression_list RPAREN"""
        p[0] = f"{p[1]}({p[3]})"

    def p_concatenation(self, p):
        """concatenation : LBRACE expression_list RBRACE"""
        p[0] = f"{{{p[2]}}}"
    
    def p_concatenation_error(self, p):
        """concatenation : LBRACE error RBRACE"""
        self._syntax_error(p, "Invalid concatenation")
        p[0] = "{ERROR}"
    
    def p_expression_list(self, p):
        """expression_list : expression"""
        p[0] = str(p[1])
    
    def p_expression_list_multiple(self, p):
        """expression_list : expression_list COMMA expression"""
        p[0] = f"{p[1]}, {p[3]}"
    
    def p_empty(self, p):
        """empty :"""
        pass
    
    def p_error(self, p):
        if p:
            error_msg = f"Syntax error at token {p.type}('{p.value}') at line {p.lineno}"
            print(f"Parser Error: {error_msg}")
            self.error_count += 1
            
            self._error_recovery(p)
        else:
            print("Parser Error: Syntax error at EOF")
            self.error_count += 1
    
    def _syntax_error(self, p, message: str):
        line_info = ""
        if len(p) > 1 and hasattr(p.slice[1], 'lineno'):
            line_info = f" at line {p.slice[1].lineno}"
        
        error_msg = f"{message}{line_info}"
        print(f"Parser Error: {error_msg}")
        self.error_count += 1
    
    def _error_recovery(self, p):
        sync_tokens = ['SEMICOLON', 'ENDMODULE', 'MODULE', 'COMMA']
        
        while True:
            tok = self.parser.token()
            if not tok:
                break
            if tok.type in sync_tokens:
                self.parser.restart()
                break

    def _propress_file(self, file_path: str, macros: MacrosType = None) -> str:
        try:
            if self.debug:
                print(f"begin to preprocess verilog code")
                print(f"use macros : {macros}")

            preprocess = VerilogPreprocess(macros)

            preprocess_code = preprocess.preprocess_string(file_path)

            if self.debug:
                print("preprocess done")
                print("=" * 50)
                print(preprocess_code)
                print("=" * 50)
            
            return preprocess_code
        
        except Exception as e:
            if self.debug:
                print(f"preprocess failed : {e}")
            
                

    def _preprocess_code(self, verilog_code: str, macros: MacrosType = None) -> str:
        try:
            if self.debug:
                print(f"begin to preprocess verilog code")
                print(f"use macros : {macros}")

            preprocess = VerilogPreprocess(macros)

            preprocess_code = preprocess.preprocess_string(verilog_code)

            if self.debug:
                print("preprocess done")
                print("=" * 50)
                print(preprocess_code)
                print("=" * 50)
            
            return preprocess_code
        
        except Exception as e:
            if self.debug:
                print(f"preprocess failed : {e}")
                print(f"use original code to parser")
            return verilog_code
            

    
    def parse(self, verilog_code: str, macros: MacrosType = None) -> Optional[VerilogAST]:
        try:
            self.error_count = 0

            processed_code = self._preprocess_code(verilog_code, macros)
            
            if not self.lexer.lexer:
                self.lexer.build()
            
            self.lexer.input(processed_code)
            
            result = self.parser.parse(lexer=self.lexer.lexer, debug=self.debug)
            
            if self.error_count > 0:
                print(f"Parsing completed with {self.error_count} errors")
            if result:
                return VerilogAST(result)
            else:
                return None
                
        except Exception as e:
            print(f"Parser Exception: {str(e)}")
            return None
    
    def parse_file(self, file_path: str,macros: MacrosType = None, encoding: str = 'utf-8') -> Optional[VerilogAST]:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                verilog_code = f.read()
            processed_code = self._preprocess_code(verilog_code, macros)
            return self.parse(processed_code)
        except IOError as e:
            print(f"File Error: {str(e)}")
            return None
    
    def get_error_count(self) -> int:
        return self.error_count
    
    def reset_error_count(self) -> None:
        self.error_count = 0


def parse_verilog(verilog_code: str, macros: MacrosType = None, debug: bool = False) -> Optional[VerilogAST]:
    parser = VerilogParser(debug=debug)
    return parser.parse(verilog_code, macros)


def parse_verilog_file(file_path: str, macros: MacrosType = None, debug: bool = False) -> Optional[VerilogAST]:
    parser = VerilogParser(debug=debug)
    return parser.parse_file(file_path, macros)


def test_parser():
    
    test_code1 = """
    module simple_module (
        input wire clk,
        input wire [7:0] data_in,
        output reg [15:0] data_out,
        inout wire enable
    );
    // module body
    endmodule
    """
    
    test_code2 = """
    module param_module #(
        parameter WIDTH = 8,
        parameter DEPTH = 256,
        parameter ID = 3,
        localparam ADDR_WIDTH = 8
    ) (
        input wire clk,
        input wire [WIDTH-1:0] data_in,
        output logic [WIDTH-1:0] data_out,
        output logic [ID**2-1:0] data_out_2
    );
    // module body
    assign data_out = data_in;
    endmodule
    """
    
    print("Testing VerilogParser with Parametric Width Support...")
    print("=" * 70)
    
    parser = VerilogParser(debug=False)
    
    print("Test 1: Simple Module with Fixed Width")
    ast1 = parser.parse(test_code1)
    if ast1:
        print(f"Module Name: {ast1.get_module_name()}")
        print(f"Port Count: {ast1.get_port_count()}")
        for port in ast1.get_module_ports():
            print(f"  Port: {port.name} ({port.direction}, {port.net_type})")
            print(f"    Range: {port.get_range_description()}")
            print(f"    Width: {port.get_width_description()}")
            print(f"    Parametric: {port.is_parametric}")
    
    print("\n" + "-" * 50 + "\n")
    
    print("Test 2: Module with Parametric Width")
    ast2 = parser.parse(test_code2)
    if ast2:
        print(f"Module Name: {ast2.get_module_name()}")
        print(f"Parameters: {len(ast2.get_module_parameters())}")
        for param in ast2.get_module_parameters():
            print(f"  Parameter: {param.name} = {param.default_value} ({param.param_type})")
        
        print(f"Port Count: {ast2.get_port_count()}")
        for port in ast2.get_module_ports():
            print(f"  Port: {port.name} ({port.direction}, {port.net_type})")
            print(f"    Range: {port.get_range_description()}")
            print(f"    Width: {port.get_width_description()}")
            print(f"    Parametric: {port.is_parametric}")
            if port.range_expr:
                print(f"    MSB Expression: {port.range_expr.msb_expr}")
                print(f"    LSB Expression: {port.range_expr.lsb_expr}")
                print(f"    Width Expression: {port.range_expr.width_expr}")



if __name__ == "__main__":
    test_code = """
    module test_module #(
        parameter A=1,
        parameter C=3) (
hif_burst_size,hif_burst_size2
    );
    //parameter B = 7;
    parameter B1 = 7, B2=4;
            input [DATA_WDITH+7:0] hif_burst_size;
        input  hif_burst_size2;
    endmodule
    """

    #parser = VerilogParser(debug=True)
    parser = VerilogParser(debug=False)
    
    result = parser.parse(test_code)
    print(result.get_module_name())
    print(result.get_module_parameters())
    print(result.get_module_ports())
    ports = result.get_module_ports()
    for port in ports:
        print(f"port name : {port.name}")
        print(f"port width : {port.width}")
    #test_parser()
    #test_code = """
    #ast = parse_verilog_file("axi_slave.v")
    #module param_module #(
    #    parameter WIDTH = 8,
    #    parameter DEPTH = 256,
    #    parameter ID = 3,
    #    localparam ADDR_WIDTH = 8
    #) (
    #    input wire clk,
    #    input wire [WIDTH-1:0] data_in,
    #    output logic [WIDTH-1:0] data_out,
    #    output logic [ID**2-1:0] data_out_2
    #);
    #// module body
    #assign data_out = data_in;
    #endmodule
    #"""
    #parser = VerilogParser(debug=False)
    #ast2 = parser.parse(test_code)
    #if ast2:
    #    print(f"Module Name: {ast2.get_module_name()}")
    #    print(f"Parameters: {len(ast2.get_module_parameters())}")
    #    for param in ast2.get_module_parameters():
    #        print(f"  Parameter: {param.name} = {param.default_value} ({param.param_type})")
    #    
    #    print(f"Port Count: {ast2.get_port_count()}")
    #    for port in ast2.get_module_ports():
    #        print(f"  Port: {port.name} ({port.direction}, {port.net_type})")
    #        print(f"    Range: {port.get_range_description()}")
    #        print(f"    Width: {port.get_width_description()}")
    #        print(f"    Parametric: {port.is_parametric}")
    #        if port.range_expr:
    #            print(f"    MSB Expression: {port.range_expr.msb_expr}")
    #            print(f"    LSB Expression: {port.range_expr.lsb_expr}")
    #            print(f"    Width Expression: {port.range_expr.width_expr}")
    #ast2 = parser.parse_file("xx.v")
    #print(f"Module Name : {ast2.get_module_name()}")
    #for param in ast2.get_module_parameters():
    #        print(f"  Parameter: {param.name} = {param.default_value} ({param.param_type})")
    #for port in ast2.get_module_ports():
    #    print(f"  Port: {port.name} ({port.direction}, {port.net_type})")
    #    print(f"    Range: {port.get_range_description()}")
    #    print(f"    Width: {port.get_width_description()}")
    #    print(f"    Parametric: {port.is_parametric}")
    #    if port.range_expr:
    #        print(f"    MSB Expression: {port.range_expr.msb_expr}")
    #        print(f"    LSB Expression: {port.range_expr.lsb_expr}")
    #        print(f"    Width Expression: {port.range_expr.width_expr}")
