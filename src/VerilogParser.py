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
from typing import Optional, Dict, Any, List

from .vcg_exceptions import VCGError, VCGFileError, VCGParseError
from .vcg_logger import get_vcg_logger

from .VerilogDiagnostics import FrontendDiagnostic, SourceLocation, format_diagnostics
from .VerilogAst import VerilogAST, VerilogASTBuilder, VerilogASTError
from .VerilogDeclarations import (
    AnsiPortHeaderElement,
    ParameterDeclarationGroup,
    ParameterDeclarator,
    ParameterHeaderElement,
    PortDeclarationGroup,
    PortDeclarator,
    RangeSpec,
)
from .VerilogLexer import VerilogLexer
from .VerilogPreprocess import VerilogPreprocess


class VerilogParser:
    """
    Verilog语法解析器
    功能：
    1. 解析Verilog模块声明
    2. 提取模块名、参数、端口信息
    3. 支持Verilog-1995和Verilog-2001语法
    4. 为SystemVerilog扩展预留接口
    """

    def __init__(self, macros: Optional[Dict[str, str]] = None, debug: bool = False):
        """
        初始化解析器

        Args:
            macros: 预处理宏定义字典
            debug: 是否启用调试模式
        """
        self.macros = macros or {}
        self.debug = debug
        self.logger = get_vcg_logger('VerilogParser')

        self.lexer = VerilogLexer()
        self.tokens = self.lexer.tokens

        self.preprocessor = VerilogPreprocess(self.macros)

        self.parser = yacc.yacc(
            module=self,
            debug=debug,
            write_tables=False,
            errorlog=yacc.NullLogger(),
        )

        self.builder: Optional[VerilogASTBuilder] = None
        self.ast: Optional[VerilogAST] = None
        self.parse_errors: List[str] = []
        self._diagnostics: List[FrontendDiagnostic] = []


    def parse_file(self, filepath: str) -> VerilogAST:
        """
        从文件解析 Verilog 代码。

        Raises:
            VCGFileError: 文件不存在、无法读取、或编码错误
            VCGParseError: 语法/语义错误导致无法构建 AST
        """
        self.logger.info(f"Reading file: {filepath}")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                verilog_code = f.read()
        except FileNotFoundError as e:
            raise VCGFileError(f"Verilog file not found: {filepath}") from e
        except UnicodeDecodeError as e:
            raise VCGFileError(f"Encoding error in {filepath}: {e}") from e
        except OSError as e:
            raise VCGFileError(f"Failed to read {filepath}: {e}") from e
        return self.parse_string(verilog_code)

    def parse_string(self, verilog_code: str) -> VerilogAST:
        """
        直接解析 Verilog 代码字符串。

        Raises:
            VCGParseError: 预处理/词法/语法/AST 构建中的任一阶段失败
            VCGFileError: 预处理阶段 include 文件缺失（由预处理器抛出）
        """
        self._reset_parse_state()

        try:
            preprocessed_code = self.preprocessor.preprocess_string(verilog_code)
            self.logger.debug(f"Preprocessed code:\n{preprocessed_code}")

            if not self.lexer.lexer:
                self.lexer.build()
            self.lexer.input(preprocessed_code)

            self.parser.parse(lexer=self.lexer.lexer, debug=self.debug)
        except VCGError:
            self.ast = None
            raise
        except Exception as e:
            self.ast = None
            raise VCGParseError(f"Unexpected parse failure: {e}") from e

        self._diagnostics.extend(self.lexer.get_diagnostics())
        self._raise_if_error_diagnostics()

        if self.ast is None:
            raise VCGParseError(
                "Parser did not produce an AST (no module declaration found?)"
            )
        return self.ast

    def get_diagnostics(self) -> tuple[FrontendDiagnostic, ...]:
        return tuple(self._diagnostics)

    def _reset_parse_state(self) -> None:
        self.builder = VerilogASTBuilder()
        self.ast = None
        self.parse_errors.clear()
        self._diagnostics = []
        self.lexer.reset_diagnostics()

    def _raise_if_error_diagnostics(self) -> None:
        diagnostics = tuple(self._diagnostics)
        if not any(diagnostic.is_error for diagnostic in diagnostics):
            return

        self.ast = None
        message = format_diagnostics(diagnostics)
        raise VCGParseError(message or "Parse failed with diagnostics")

    def _record_parse_error(
        self,
        message: str,
        line: Optional[int] = None,
        column: Optional[int] = None,
        lexpos: Optional[int] = None,
    ) -> None:
        self.parse_errors.append(message)
        location = None
        if line is not None and column is not None:
            location = SourceLocation(line=line, column=column, lexpos=lexpos)
        self._diagnostics.append(
            FrontendDiagnostic(
                code="VPARSE_SYNTAX",
                message=message,
                severity="error",
                stage="parser",
                kind="syntax",
                location=location,
            )
        )

    def _coalesce_ansi_port_elements(
        self,
        elements: tuple[AnsiPortHeaderElement, ...],
    ) -> tuple[PortDeclarationGroup, ...]:
        groups: list[PortDeclarationGroup] = []
        current: PortDeclarationGroup | None = None

        for element in elements:
            if element.direction is not None:
                current = PortDeclarationGroup(
                    direction=element.direction,
                    net_type=element.net_type,
                    range_spec=element.range_spec,
                    declarators=(element.declarator,),
                )
                groups.append(current)
                continue

            if current is None:
                self._record_parse_error(
                    "ANSI port continuation "
                    f"'{element.declarator.name}' has no declaration context"
                )
                return ()

            current = PortDeclarationGroup(
                direction=current.direction,
                net_type=current.net_type,
                range_spec=current.range_spec,
                declarators=current.declarators + (element.declarator,),
            )
            groups = groups[:-1] + [current]

        return tuple(groups)

    def _coalesce_parameter_header_elements(
        self,
        elements: tuple[ParameterHeaderElement, ...],
    ) -> tuple[ParameterDeclarationGroup, ...]:
        groups: list[ParameterDeclarationGroup] = []
        current: ParameterDeclarationGroup | None = None

        for element in elements:
            if element.param_type is not None:
                current = ParameterDeclarationGroup(
                    param_type=element.param_type,
                    data_type=element.data_type,
                    declarators=(element.declarator,),
                )
                groups.append(current)
                continue

            if current is None:
                self._record_parse_error(
                    "Parameter continuation "
                    f"'{element.declarator.name}' has no declaration context"
                )
                return ()

            current = ParameterDeclarationGroup(
                param_type=current.param_type,
                data_type=current.data_type,
                declarators=current.declarators + (element.declarator,),
            )
            groups = groups[:-1] + [current]

        return tuple(groups)

    def _range_parts(
        self,
        range_spec: RangeSpec | None,
    ) -> tuple[str | None, str | None]:
        if range_spec is None:
            return None, None
        return range_spec.msb_expr, range_spec.lsb_expr

    def _add_port_group(
        self,
        group: PortDeclarationGroup,
        *,
        update_existing: bool = False,
    ) -> None:
        if self.builder is None:
            return
        msb_expr, lsb_expr = self._range_parts(group.range_spec)
        method = self.builder.update_port if update_existing else self.builder.add_port
        for declarator in group.declarators:
            method(
                name=declarator.name,
                direction=group.direction,
                net_type=group.net_type or "wire",
                msb_expr=msb_expr,
                lsb_expr=lsb_expr,
            )

    def _add_parameter_group(self, group: ParameterDeclarationGroup) -> None:
        if self.builder is None:
            return
        for declarator in group.declarators:
            self.builder.add_parameter(
                name=declarator.name,
                param_type=group.param_type,
                default_value=declarator.default_value,
                data_type=group.data_type,
            )

    def get_module_info(self) -> Optional[Dict[str, Any]]:
        if self.ast is None:
            return None
        return {
            "name": self.ast.module_name,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.param_type,
                    "default_value": p.default_value
                } for p in self.ast.get_parameter_info()
            ],
            "ports": [
                {
                    "name": p.name,
                    "direction": p.direction,
                    "net_type": p.net_type,
                    "range": p.range_string,
                    "width": p.width,
                    "type": p.port_type.value
                } for p in self.ast.get_port_info()
            ]
        }


    precedence = (
        ('right', 'COND', 'COLON'),                     # 条件运算符 ? :
        ('left', 'LOR'),                                # 逻辑或 ||
        ('left', 'LAND'),                               # 逻辑与 &&
        ('left', 'OR'),                                 # 按位或 |
        ('left', 'XOR', 'XNOR'),                        # 按位异或 ^, ~^
        ('left', 'AND'),                                # 按位与 &
        ('left', 'EQ', 'NE'),                           # 相等 ==, !=
        ('left', 'LT', 'GT', 'LE', 'GE'),               # 关系 <, >, <=, >=
        ('left', 'LSHIFT', 'RSHIFT'),                   # 移位 <<, >>
        ('left', 'PLUS', 'MINUS'),                      # 加减 +, -
        ('left', 'TIMES', 'DIVIDE', 'MOD'),             # 乘除模 *, /, %
        ('right', 'POWER'),                             # 幂运算 **
        ('right', 'UMINUS', 'UPLUS', 'UNOT', 'ULNOT'),  # 一元运算符)
    )

    def p_design_unit(self, p):
        """design_unit : module_declaration
                       | empty"""
        p[0] = p[1]


    def p_module_declaration(self, p):
        """module_declaration : MODULE module_name opt_parameter_list opt_port_list SEMICOLON module_item_list ENDMODULE"""
        module_name = p[2]
        self._finalize_ast(module_name)
        p[0] = self.ast

    def p_module_declaration_error(self, p):
        """module_declaration : MODULE module_name error ENDMODULE"""
        module_name = p[2]
        self.logger.error(f"Syntax error in module declaration: {module_name}")
        self.parse_errors.append(
            f"Syntax error inside module '{module_name}' declaration"
        )
        # 不构造伪造 AST；parse_string 会基于 ast is None + parse_errors 抛 VCGParseError
        p[0] = None

    def _finalize_ast(self, module_name: str) -> None:
        """Build the AST from the current builder. Records errors instead of raising
        inside yacc actions — parse_string inspects self.ast / self.parse_errors."""
        if self.builder is None:
            self.parse_errors.append("Internal error: AST builder not initialized")
            return
        try:
            self.builder.set_module_name(module_name)
            self.ast = self.builder.build()
            self.logger.info(f"Successfully parsed module: {module_name}")
            self.logger.debug(f"  - Parameters: {len(self.ast.get_parameter_info())}")
            self.logger.debug(f"  - Ports: {len(self.ast.get_port_info())}")
        except VerilogASTError as e:
            self.logger.error(f"Failed to build AST for module '{module_name}': {e}")
            self._diagnostics.append(
                FrontendDiagnostic(
                    code="VAST_BUILD_FAILED",
                    message=f"AST build failed: {e}",
                    severity="error",
                    stage="ast",
                    kind="semantic",
                )
            )
            self.parse_errors.append(f"AST build failed: {e}")
            self.ast = None

    def p_module_name(self, p):
        """module_name : ID"""
        p[0] = p[1]

    def p_opt_parameter_list(self, p):
        """opt_parameter_list : HASH LPAREN parameter_header_list RPAREN
                              | HASH LPAREN RPAREN
                              | HASH LPAREN error RPAREN
                              | empty"""
        if len(p) == 5 and isinstance(p[3], tuple):
            for group in self._coalesce_parameter_header_elements(p[3]):
                if isinstance(group, ParameterDeclarationGroup):
                    self._add_parameter_group(group)
        elif len(p) == 5 and p.slice[3].type == "error":
            self._record_parse_error(f"Invalid parameter list near line {p.lineno(1)}")

    def p_parameter_header_list_single(self, p):
        """parameter_header_list : parameter_header_first"""
        if len(p) == 2:
            p[0] = (p[1],)

    def p_parameter_header_list_append(self, p):
        """parameter_header_list : parameter_header_list COMMA parameter_header_next"""
        p[0] = p[1] + (p[3],)

    def p_parameter_header_first(self, p):
        """parameter_header_first : parameter_kind opt_parameter_data_type param_assignment"""
        p[0] = ParameterHeaderElement(
            param_type=p[1],
            data_type=p[2],
            declarator=p[3],
        )

    def p_parameter_header_next_decl(self, p):
        """parameter_header_next : parameter_kind opt_parameter_data_type param_assignment"""
        p[0] = ParameterHeaderElement(
            param_type=p[1],
            data_type=p[2],
            declarator=p[3],
        )

    def p_parameter_header_next_continuation(self, p):
        """parameter_header_next : param_assignment"""
        p[0] = ParameterHeaderElement(
            param_type=None,
            data_type=None,
            declarator=p[1],
        )

    def p_parameter_declaration_group(self, p):
        """parameter_declaration_group : parameter_kind opt_parameter_data_type param_assignment_list"""
        p[0] = ParameterDeclarationGroup(
            param_type=p[1],
            data_type=p[2],
            declarators=p[3],
        )

    def p_parameter_kind(self, p):
        """parameter_kind : PARAMETER
                          | LOCALPARAM"""
        p[0] = p[1].lower()

    def p_opt_parameter_data_type(self, p):
        """opt_parameter_data_type : empty"""
        p[0] = None

    def p_parameter_declaration_group_error(self, p):
        """parameter_declaration_group : parameter_kind error"""
        self._record_parse_error(f"Invalid parameter declaration at line {p.lineno(1)}")
        p[0] = None

    def p_param_assignment(self, p):
        """param_assignment : ID EQUALS expression"""
        p[0] = ParameterDeclarator(name=p[1], default_value=p[3])

    def p_param_assignment_error(self, p):
        """param_assignment : ID EQUALS error"""
        self._record_parse_error(f"Invalid parameter value for '{p[1]}' at line {p.lineno(1)}")
        p[0] = None

    def p_opt_port_list(self, p):
        """opt_port_list : LPAREN ansi_port_header_list RPAREN
                         | LPAREN port_name_list RPAREN
                         | LPAREN RPAREN
                         | empty"""
        if len(p) == 4 and isinstance(p[2], tuple):
            if p[2] and isinstance(p[2][0], AnsiPortHeaderElement):
                for group in self._coalesce_ansi_port_elements(p[2]):
                    self._add_port_group(group)
            else:
                for port_name in p[2]:
                    if self.builder:
                        self.builder.add_port(name=port_name)

    def p_opt_port_list_error(self, p):
        """opt_port_list : LPAREN error RPAREN"""
        self._record_parse_error(f"Invalid port list near line {p.lineno(1)}")

    def p_ansi_port_header_list_single(self, p):
        """ansi_port_header_list : ansi_port_header_first"""
        p[0] = (p[1],)

    def p_ansi_port_header_list_append(self, p):
        """ansi_port_header_list : ansi_port_header_list COMMA ansi_port_header_next"""
        p[0] = p[1] + (p[3],)

    def p_ansi_port_header_first(self, p):
        """ansi_port_header_first : port_direction opt_net_or_reg_type opt_packed_dimension port_declarator"""
        p[0] = AnsiPortHeaderElement(
            direction=p[1],
            net_type=p[2],
            range_spec=p[3],
            declarator=p[4],
        )

    def p_ansi_port_header_next_decl(self, p):
        """ansi_port_header_next : port_direction opt_net_or_reg_type opt_packed_dimension port_declarator"""
        p[0] = AnsiPortHeaderElement(
            direction=p[1],
            net_type=p[2],
            range_spec=p[3],
            declarator=p[4],
        )

    def p_ansi_port_header_next_continuation(self, p):
        """ansi_port_header_next : port_declarator"""
        p[0] = AnsiPortHeaderElement(
            direction=None,
            net_type=None,
            range_spec=None,
            declarator=p[1],
        )

    def p_port_name_list(self, p):
        """port_name_list : ID
                          | port_name_list COMMA ID"""
        if len(p) == 2:
            p[0] = (p[1],)
        else:
            p[0] = p[1] + (p[3],)

    def p_port_direction(self, p):
        """port_direction : INPUT
                          | OUTPUT
                          | INOUT"""
        p[0] = p[1].lower()

    def p_opt_net_or_reg_type(self, p):
        """opt_net_or_reg_type : WIRE
                               | REG
                               | LOGIC
                               | empty"""
        p[0] = p[1].lower() if p[1] else None

    def p_opt_packed_dimension(self, p):
        """opt_packed_dimension : LBRACKET expression COLON expression RBRACKET
                                | LBRACKET error RBRACKET
                                | empty"""
        if len(p) == 6:
            p[0] = RangeSpec(msb_expr=p[2], lsb_expr=p[4])
        elif len(p) == 4:
            self._record_parse_error(f"Invalid dimension near line {p.lineno(2)}")
            p[0] = None
        else:
            p[0] = None

    def p_port_declarator(self, p):
        """port_declarator : ID"""
        p[0] = PortDeclarator(name=p[1])

    def p_module_item_list(self, p):
        """module_item_list : empty
                            | module_item_list module_item
                            | module_item"""
        pass

    def p_module_item_list_error(self, p):
        """module_item_list : module_item_list error SEMICOLON"""
        # Error-recovery path: record it so parse_string doesn't return silently.
        self._record_parse_error(f"Syntax error in module body near line {p.lineno(3)}")

    def p_module_item(self, p):
        """module_item : module_item_declaration"""
        pass

    def p_module_item_declaration_port(self, p):
        """module_item_declaration : port_direction opt_net_or_reg_type opt_packed_dimension port_declarator_list SEMICOLON"""
        group = PortDeclarationGroup(
            direction=p[1],
            net_type=p[2],
            range_spec=p[3],
            declarators=p[4],
        )
        self._add_port_group(group, update_existing=True)

    def p_module_item_declaration_param(self, p):
        """module_item_declaration : parameter_declaration_group SEMICOLON"""
        if isinstance(p[1], ParameterDeclarationGroup):
            self._add_parameter_group(p[1])

    def p_port_declarator_list(self, p):
        """port_declarator_list : port_declarator
                                | port_declarator_list COMMA port_declarator"""
        if len(p) == 2:
            p[0] = (p[1],)
        else:
            p[0] = p[1] + (p[3],)

    def p_param_assignment_list(self, p):
        """param_assignment_list : param_assignment
                                | param_assignment_list COMMA param_assignment"""
        if len(p) == 2:
            p[0] = (p[1],) if isinstance(p[1], ParameterDeclarator) else ()
        else:
            next_param = (p[3],) if isinstance(p[3], ParameterDeclarator) else ()
            p[0] = p[1] + next_param

    def p_expression_binop(self, p):
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
        p[0] = f"{p[1]} {p[2]} {p[3]}"

    def p_expression_unary(self, p):
        """expression : PLUS expression %prec UPLUS
                      | MINUS expression %prec UMINUS
                      | NOT expression %prec UNOT
                      | LNOT expression %prec ULNOT"""
        p[0] = f"{p[1]}{p[2]}"

    def p_expression_ternary(self, p):
        """expression : expression COND expression COLON expression"""
        p[0] = f"{p[1]} ? {p[3]} : {p[5]}"

    def p_expression_paren(self, p):
        """expression : LPAREN expression RPAREN"""
        p[0] = f"({p[2]})"

    def p_expression_concat(self, p):
        """expression : concatenation"""
        p[0] = p[1]

    def p_expression_primary(self, p):
        """expression : primary"""
        p[0] = p[1]

    def p_primary_number(self, p):
        """primary : INTNUMBER_DEC
                   | INTNUMBER_HEX
                   | INTNUMBER_OCT
                   | INTNUMBER_BIN"""
        p[0] = str(p[1])

    def p_primary_id(self, p):
        """primary : ID"""
        p[0] = p[1]

    def p_primary_string(self, p):
        """primary : STRING_LITERAL"""
        p[0] = p[1]

    def p_primary_bit_select(self, p):
        """primary : ID LBRACKET expression RBRACKET"""
        p[0] = f"{p[1]}[{p[3]}]"

    def p_primary_bit_select_error(self, p):
        """primary : ID LBRACKET error RBRACKET"""
        self._record_parse_error(f"Invalid bit selection for '{p[1]}' at line {p.lineno(1)}")
        p[0] = None

    def p_primary_part_select(self, p):
        """primary : ID LBRACKET expression COLON expression RBRACKET"""
        p[0] = f"{p[1]}[{p[3]}:{p[5]}]"

    def p_primary_part_select_error(self, p):
        """primary : ID LBRACKET error COLON error RBRACKET"""
        self._record_parse_error(f"Invalid part selection for '{p[1]}' at line {p.lineno(1)}")
        p[0] = None

    def p_primary_signed_number(self, p):
        """primary : PLUS INTNUMBER_DEC
                   | PLUS INTNUMBER_HEX
                   | PLUS INTNUMBER_OCT
                   | PLUS INTNUMBER_BIN
                   | MINUS INTNUMBER_DEC
                   | MINUS INTNUMBER_HEX
                   | MINUS INTNUMBER_OCT
                   | MINUS INTNUMBER_BIN"""
        p[0] = f"{p[1]}{p[2]}"

    def p_primary_function_call(self, p):
        """primary : ID LPAREN expression_list RPAREN"""
        args = ','.join(p[3])
        p[0] = f"{p[1]}({args})"

    def p_concatenation(self, p):
        """concatenation : LBRACE expression_list RBRACE"""
        p[0] = '{' + ','.join(p[2]) + '}'

    def p_concatenation_error(self, p):
        """concatenation : LBRACE error RBRACE"""
        self._record_parse_error(f"Invalid concatenation at line {p.lineno(1)}")
        p[0] = None

    def p_expression_list(self, p):
        """expression_list : expression
                           | expression_list COMMA expression"""
        if len(p) == 2:
            p[0] = [p[1]]
        else:
            p[0] = p[1] + [p[3]]

    def p_empty(self, p):
        """empty :"""
        pass

    def p_error(self, p):
        if p:
            column = self.lexer.find_column(self.lexer.lexer.lexdata, p)
            error_msg = f"Syntax error at token '{p.value}' (line {p.lineno}, position {p.lexpos})"
            self.logger.error(error_msg)
            self._record_parse_error(error_msg, line=p.lineno, column=column, lexpos=p.lexpos)
            # Rely on the `error` productions (opt_parameter_list, module_item_list, etc.)
            # to resynchronize. Advancing the token here breaks those rules and causes
            # cascaded failures. errok() signals yacc to resume after this point.
            self.parser.errok()
        else:
            error_msg = "Syntax error at EOF"
            self.logger.error(error_msg)
            self._record_parse_error(error_msg)

