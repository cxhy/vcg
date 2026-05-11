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

from typing import Any, Optional

import ply.lex as lex

from .VerilogDiagnostics import FrontendDiagnostic, SourceLocation
from .vcg_logger import get_vcg_logger

logger = get_vcg_logger('VerilogLexer')


class VerilogLexer:

    UNSUPPORTED_SINGLE_CHAR_TOKENS = {
        "@": "procedural event control",
        ".": "named port connection or hierarchical name",
    }

    UNSUPPORTED_MULTI_CHAR_TOKENS = {
        "::": "SystemVerilog package scope",
        "->": "event trigger",
    }

    UNSUPPORTED_KEYWORDS = {
        "always": "procedural block",
        "initial": "procedural block",
        "begin": "procedural block",
        "end": "procedural block",
        "generate": "generate block",
        "endgenerate": "generate block",
        "case": "procedural block",
        "endcase": "procedural block",
        "for": "procedural or generate loop",
        "if": "procedural or generate conditional",
        "typedef": "SystemVerilog type declaration",
        "interface": "SystemVerilog interface",
        "modport": "SystemVerilog modport",
        "import": "SystemVerilog package import",
    }

    reserved = {
        'module':     'MODULE',
        'endmodule':  'ENDMODULE',
        'input':      'INPUT',
        'inout':      'INOUT',
        'output':     'OUTPUT',
        'reg':        'REG',
        'logic':      'LOGIC',
        'wire':       'WIRE',
        'parameter':  'PARAMETER',
        'localparam': 'LOCALPARAM',
        'assign':     'ASSIGN',
    }

    keywords_list_spec = tuple(reserved.values())

    operators_list_spec = (
        'PLUS', 'MINUS', 'POWER', 'TIMES', 'DIVIDE', 'MOD',  # + - * ** / %
        'NOT', 'OR', 'AND', 'XOR', 'XNOR',                   # ~ | & ^ ^~/~^
        'LOR', 'LAND', 'LNOT',                               # || && !
        'LSHIFT', 'RSHIFT',                                  # << >>
        'LT', 'GT', 'LE', 'GE', 'EQ', 'NE',                  # < > <= >= == !=
        'COND',                                              # ?
        'EQUALS',                                            # =
    )

    other_tokens = (
        'ID',
        'COMMA', 'COLON', 'SEMICOLON',
        'STRING_LITERAL',
        'INTNUMBER_DEC',
        'INTNUMBER_HEX',
        'INTNUMBER_OCT',
        'INTNUMBER_BIN',
        'LPAREN', 'RPAREN', 'LBRACKET', 'RBRACKET', 'LBRACE', 'RBRACE',
        'HASH',
    )

    tokens = keywords_list_spec + operators_list_spec + other_tokens

    def __init__(self, **kwargs: Any) -> None:
        self.lexer: Optional[lex.Lexer] = None
        self._diagnostics: list[FrontendDiagnostic] = []
        self.build(**kwargs)

    def build(self, **kwargs: Any) -> None:
        self.lexer = lex.lex(module=self, **kwargs)

    def input(self, data: str) -> None:
        self.reset_diagnostics()
        self.lexer.lineno = 1
        self.lexer.input(data)

    def token(self) -> Optional[lex.LexToken]:
        return self.lexer.token()

    def reset_diagnostics(self) -> None:
        self._diagnostics = []

    def get_diagnostics(self) -> tuple[FrontendDiagnostic, ...]:
        return tuple(self._diagnostics)

    t_ignore = ' \t'

    t_PLUS     = r'\+'
    t_MINUS    = r'-'
    t_TIMES    = r'\*'
    t_DIVIDE   = r'/'
    t_MOD      = r'%'
    t_EQUALS   = r'='
    t_LPAREN   = r'\('
    t_RPAREN   = r'\)'
    t_LBRACKET = r'\['
    t_RBRACKET = r'\]'
    t_LBRACE   = r'\{'
    t_RBRACE   = r'\}'
    t_COMMA    = r','
    t_SEMICOLON = r';'
    t_COLON    = r':'
    t_HASH     = r'\#'
    t_COND     = r'\?'

    def t_POWER(self, t):
        r'\*\*'
        return t

    def t_LOR(self, t):
        r'\|\|'
        return t

    def t_LAND(self, t):
        r'&&'
        return t

    def t_LSHIFT(self, t):
        r'<<'
        return t

    def t_RSHIFT(self, t):
        r'>>'
        return t

    def t_LE(self, t):
        r'<='
        return t

    def t_GE(self, t):
        r'>='
        return t

    def t_EQ(self, t):
        r'=='
        return t

    def t_NE(self, t):
        r'!='
        return t

    def t_UNSUPPORTED_SCOPE(self, t):
        r'::'
        self._record_unsupported(t, "SystemVerilog package scope")

    def t_UNSUPPORTED_ARROW(self, t):
        r'->'
        self._record_unsupported(t, "event trigger")

    def t_LT(self, t):
        r'<'
        return t

    def t_GT(self, t):
        r'>'
        return t

    def t_XNOR(self, t):
        r'\^~|~\^'
        return t

    def t_OR(self, t):
        r'\|'
        return t

    def t_LNOT(self, t):
        r'!'
        return t

    def t_AND(self, t):
        r'&'
        return t

    def t_XOR(self, t):
        r'\^'
        return t

    def t_NOT(self, t):
        r'~'
        return t

    def t_STRING_LITERAL(self, t):
        r'"([^"\\]|\\.)*"'
        t.value = t.value[1:-1]
        # Protect escaped backslashes via sentinel so "\\n" stays literal "\n"
        # (backslash + n) instead of being further interpreted as newline.
        _sentinel = '\x00'
        t.value = t.value.replace('\\\\', _sentinel)
        t.value = t.value.replace('\\"', '"')
        t.value = t.value.replace('\\n', '\n')
        t.value = t.value.replace('\\t', '\t')
        t.value = t.value.replace(_sentinel, '\\')
        return t

    def t_INTNUMBER_HEX(self, t):
        r"""(?:\d+\'h[0-9a-fA-F]+(?:_[0-9a-fA-F]+)*|\'h[0-9a-fA-F]+(?:_[0-9a-fA-F]+)*)"""
        t.value = t.value.replace('_', '')
        return t

    def t_INTNUMBER_OCT(self, t):
        r"""(?:\d+\'o[0-7]+(?:_[0-7]+)*|\'o[0-7]+(?:_[0-7]+)*)"""
        t.value = t.value.replace('_', '')
        return t

    def t_INTNUMBER_BIN(self, t):
        r"""(?:\d+\'b[01]+(?:_[01]+)*|\'b[01]+(?:_[01]+)*)"""
        t.value = t.value.replace('_', '')
        return t

    def t_INTNUMBER_DEC(self, t):
        r"""(?:\d+\'d\d+(?:_\d+)*|\'d\d+(?:_\d+)*|\d+(?:_\d+)*)"""
        t.value = t.value.replace('_', '')
        return t

    def t_ID(self, t):
        r'[a-zA-Z_`$][a-zA-Z_0-9`$]*'
        if t.value in self.UNSUPPORTED_KEYWORDS:
            self._record_unsupported_keyword(t, self.UNSUPPORTED_KEYWORDS[t.value])
            return None
        t.type = self.reserved.get(t.value.lower(), 'ID')
        return t

    def t_newline(self, t):
        r'\n+'
        t.lexer.lineno += len(t.value)

    def t_COMMENT_SINGLE(self, t):
        r'//.*'
        pass

    def t_COMMENT_MULTI(self, t):
        r'/\*(.|\n)*?\*/'
        t.lexer.lineno += t.value.count('\n')
        pass

    def t_error(self, t):
        line_num = t.lineno
        col_num = self.find_column(t.lexer.lexdata, t)
        char = t.value[0]
        if char in self.UNSUPPORTED_SINGLE_CHAR_TOKENS:
            self._record_unsupported_char(t, self.UNSUPPORTED_SINGLE_CHAR_TOKENS[char])
            t.lexer.skip(1)
            return

        self._record_invalid_char(t)
        logger.error(
            f"Lexical error at line {line_num}, column {col_num}: "
            f"Illegal character '{char}' (0x{ord(char):02x})"
        )
        t.lexer.skip(1)

    def find_column(self, input_text: str, token: lex.LexToken) -> int:
        line_start = input_text.rfind('\n', 0, token.lexpos) + 1
        return (token.lexpos - line_start) + 1

    def _location_for_token(self, token: lex.LexToken) -> SourceLocation:
        return SourceLocation(
            line=token.lineno,
            column=self.find_column(token.lexer.lexdata, token),
            lexpos=token.lexpos,
        )

    def _record_unsupported(
        self,
        token: lex.LexToken,
        feature: str,
    ) -> None:
        spelling = token.value
        self._diagnostics.append(
            FrontendDiagnostic(
                code="VLEX_UNSUPPORTED_TOKEN",
                message=(
                    f"unsupported token '{spelling}' in current parser subset "
                    f"({feature})"
                ),
                severity="error",
                stage="lexer",
                kind="recognized_unsupported",
                location=self._location_for_token(token),
                spelling=spelling,
            )
        )

    def _record_unsupported_char(
        self,
        token: lex.LexToken,
        feature: str,
    ) -> None:
        spelling = token.value[0]
        self._diagnostics.append(
            FrontendDiagnostic(
                code="VLEX_UNSUPPORTED_TOKEN",
                message=(
                    f"unsupported token '{spelling}' in current parser subset "
                    f"({feature})"
                ),
                severity="error",
                stage="lexer",
                kind="recognized_unsupported",
                location=self._location_for_token(token),
                spelling=spelling,
            )
        )

    def _record_unsupported_keyword(
        self,
        token: lex.LexToken,
        feature: str,
    ) -> None:
        spelling = token.value
        self._diagnostics.append(
            FrontendDiagnostic(
                code="VLEX_UNSUPPORTED_KEYWORD",
                message=(
                    f"unsupported keyword '{spelling}' in current parser subset "
                    f"({feature})"
                ),
                severity="error",
                stage="lexer",
                kind="recognized_unsupported",
                location=self._location_for_token(token),
                spelling=spelling,
            )
        )

    def _record_invalid_char(self, token: lex.LexToken) -> None:
        spelling = token.value[0]
        location = self._location_for_token(token)
        self._diagnostics.append(
            FrontendDiagnostic(
                code="VLEX_INVALID_CHARACTER",
                message=(
                    f"invalid lexical input '{spelling}' "
                    f"(0x{ord(spelling):02x})"
                ),
                severity="error",
                stage="lexer",
                kind="invalid",
                location=location,
                spelling=spelling,
            )
        )
