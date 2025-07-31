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

import ply.lex as lex
import re
import warnings
warnings.filterwarnings('ignore', message='.*unused tokens.*')
warnings.filterwarnings('ignore', message='.*defined, but not used.*')

class VerilogLexer:
    
    keywords_list_spec = (
        'MODULE', 'ENDMODULE', 'BEGIN', 'END', 'INPUT', 'INOUT', 'OUTPUT', 'REG', 'LOGIC', 'WIRE',
        'PARAMETER', 'LOCALPARAM', 'ASSIGN', 'ALWAYS', #'SENS_OR', 'POSEDGE', 'NEGEDGE',
        #'IF', 'ELSE', 'CASE', 'CASEX', 'CASEZ', 'ENDCASE', 'DEFAULT'
    )
    
    operators_list_spec = (
        'PLUS', 'MINUS', 'POWER', 'TIMES', 'DIVIDE', 'MOD',    # + - * ** / %
        'NOT', 'OR', #'NOR', 
        'AND', #'NAND', 
        'XOR', 'XNOR',      # ~ | ^~ & ~& ^ ~^
        'LOR', 'LAND', 'LNOT',                                 # || && !
        #'LSHIFTA', 'RSHIFTA', 
        'LSHIFT', 'RSHIFT',              # <<< >>> << >>
        'LT', 'GT', 'LE', 'GE', 'EQ', 'NE', #'EQL', 'NEL',      # < > <= >= == != === !==
        'COND',                                                # ?
        'EQUALS',                                              # =)
    )
    
    other_tokens = (
        'ID',                
        #'AT', 
        'COMMA', 'COLON', 'SEMICOLON', #'DOT',
        #'PLUSCOLON', 'MINUSCOLON',
        'STRING_LITERAL',
        'INTNUMBER_DEC',  # For 123, 10'd255, 'd255
        'INTNUMBER_HEX', 
        'INTNUMBER_OCT', 
        'INTNUMBER_BIN', 
        'LPAREN', 'RPAREN', 'LBRACKET', 'RBRACKET', 'LBRACE', 'RBRACE',
        'HASH'#, 'DOLLER'
    )
    
    tokens = keywords_list_spec + operators_list_spec + other_tokens
    
    reserved = {
        'module': 'MODULE',
        'endmodule': 'ENDMODULE',
        'begin': 'BEGIN',
        'end': 'END',
        'input': 'INPUT',
        'inout': 'INOUT',
        'output': 'OUTPUT',
        'reg': 'REG',
        'logic': 'LOGIC',
        'wire': 'WIRE',
        'parameter': 'PARAMETER',
        'localparam': 'LOCALPARAM',
        'assign': 'ASSIGN',
        'always': 'ALWAYS'#,
        #'or': 'SENS_OR',
        #'posedge': 'POSEDGE',
        #'negedge': 'NEGEDGE',
        #'if': 'IF',
        #'else': 'ELSE',
        #'case': 'CASE',
        #'casex': 'CASEX',
        #'casez': 'CASEZ',
        #'endcase': 'ENDCASE',
        #'default': 'DEFAULT'
    }
    
    def __init__(self):
        self.tokens = VerilogLexer.tokens
        self.lexer = None
    def build(self, **kwargs):
        self.lexer = lex.lex(module=self, **kwargs)
        
    def input(self, data):
        if self.lexer is None:
            raise RuntimeError("Lexer not built. Call build() first.")
        self.lexer.input(data)
        
    def token(self):
        if self.lexer is None:
            raise RuntimeError("Lexer not built. Call build() first.")
        return self.lexer.token()
    
    t_ignore = ' \t'

    t_PLUS = r'\+'
    t_MINUS = r'-'
    t_TIMES = r'\*'
    t_DIVIDE = r'/'
    t_MOD = r'%'
    t_EQUALS = r'='
    t_LPAREN = r'\('
    t_RPAREN = r'\)'
    t_LBRACKET = r'\['
    t_RBRACKET = r'\]'
    t_LBRACE = r'\{'
    t_RBRACE = r'\}'
    t_COMMA = r','
    t_SEMICOLON = r';'
    t_COLON = r':'
    #t_DOT = r'\.'
    #t_AT = r'@'
    t_HASH = r'\#'
    #t_DOLLER = r'\$'
    t_COND = r'\?'



    def t_POWER(self, t):
        r'\*\*'
        return t
        
    def t_LOR(self, t):
        r'\|\|'
        return t
        
    def t_LAND(self, t):
        r'&&'
        return t
        
    #def t_LSHIFTA(self, t):
    #    r'<<<'
    #    return t

    #def t_RSHIFTA(self, t):
    #    r'>>>'
    #    return t
        
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
        
    #def t_EQL(self, t):
    #    r'==='
    #    return t
    
    #def t_NEL(self, t):
    #    r'!=='
    #    return t
        
    def t_EQ(self, t):
        r'=='
        return t
        
    def t_NE(self, t):
        r'!='
        return t
        
    def t_LT(self, t):
        r'<'
        return t
        
    def t_GT(self, t):
        r'>'
        return t
        
    #def t_NOR(self, t):
    #    r'~\|'
    #    return t
        
    #def t_NAND(self, t):
    #    r'~&'
    #    return t
        
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
        
    #def t_PLUSCOLON(self, t):
    #    r'\+:'
    #    return t
        
    #def t_MINUSCOLON(self, t):
    #    r'-:'
    #    return t

    def t_STRING_LITERAL(self, t):
        r'"([^"\\]|\\.)*"'
 
        t.value = t.value[1:-1] 
        t.value = t.value.replace(r'\"', '"')
        t.value = t.value.replace(r'\\', '\\')
        t.value = t.value.replace(r'\n', '\n')
        t.value = t.value.replace(r'\t', '\t')
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
        #if '$' in t.value:
        #    print(f"DEBUG: Found ID with $: '{t.value}' at line {t.lineno}")
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
        
        print(f"Lexical error at line {line_num}, column {col_num}: "
              f"Illegal character '{char}' (0x{ord(char):02x})")
        

        t.lexer.skip(1)
    
    def find_column(self, input_text, token):
        line_start = input_text.rfind('\n', 0, token.lexpos) + 1
        return (token.lexpos - line_start) + 1


def test_lexer():

    lexer = VerilogLexer()
    lexer.build(debug=False)
    

    test_code = '''
    module test_module (
        input wire clk,
        input wire [7:0] data_in,
        output reg [`WIDTH-1:0] data_out
    );
    
    parameter WIDTH = 8;
    localparam `DEPTH = 16;
    
    always @(posedge clk) begin
        if (data_in == 8'hFF) begin
            data_out <= 'd255;
        end else begin
            data_out <= data_in + 1'b1;
        end
    end
    
    assign result = (a > b) ? a : b;
    
    endmodule
    '''
    

    lexer.input(test_code)
    
    print("=== Verilog Lexer Test Results ===")
    print("Token Type".ljust(15) + "Value".ljust(20) + "Line:Col")
    print("-" * 50)
    
    while True:
        tok = lexer.token()
        if not tok:
            break
        
        col = lexer.find_column(test_code, tok)
        print(f"{tok.type}".ljust(15) + 
              f"'{tok.value}'".ljust(20) + 
              f"{tok.lineno}:{col}")


def tokenize_file(filename):
    lexer = VerilogLexer()
    lexer.build()
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lexer.input(content)
        tokens = []
        
        while True:
            tok = lexer.token()
            if not tok:
                break
            tokens.append(tok)
        
        return tokens
        
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return []
    except Exception as e:
        print(f"Error reading file '{filename}': {e}")
        return []


def interactive_lexer():
    lexer = VerilogLexer()
    lexer.build()
    
    print("=== Interactive Verilog Lexer ===")
    print("Enter Verilog code (press Ctrl+C to exit):")
    print("Type 'quit' to exit")
    
    while True:
        try:
            user_input = input(">>> ")
            if user_input.strip().lower() == 'quit':
                break
                
            lexer.input(user_input)
            
            print("\nTokens:")
            while True:
                tok = lexer.token()
                if not tok:
                    break
                col = lexer.find_column(user_input, tok)
                print(f"  {tok.type}: '{tok.value}' at {tok.lineno}:{col}")
            print()
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == '__main__':
    #test_lexer()
    test_code = "parameter HIF_DW_CLOG2 = $clog2(HIF_DW),"
    lexer = VerilogLexer()
    lexer.build()
    lexer.input(test_code)

    while True:
        tok = lexer.token()
        if not tok:
            break
        print(f"Token: {tok.type}, Value: '{tok.value}', Line: {tok.lineno}")
    
