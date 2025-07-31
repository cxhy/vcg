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
import re
import os
from typing import Dict, List, Optional, Tuple, Union

class VerilogPreprocess:
    
    def __init__(self, macros: Union[Dict[str, str], List[str], List[Tuple[str, str]], None] = None):
        self.macros = self._parse_macros(macros)
    
    def _parse_macros(self, macros: Union[Dict[str, str], List[str], List[Tuple[str, str]], None]) -> Dict[str, str]:
        if macros is None:
            return {}
        
        if isinstance(macros, dict):
            return macros.copy()
        
        if isinstance(macros, list):
            result = {}
            
            for item in macros:
                if isinstance(item, str):
                    result[item] = '1'
                elif isinstance(item, tuple) and len(item) == 2:
                    macro_name, macro_value = item
                    if isinstance(macro_name, str) and isinstance(macro_value, str):
                        result[macro_name] = macro_value
                    else:
                        raise ValueError(f"macros key and value must be : {item}")
                else:
                    raise ValueError(f"Unknow type Macros define: {item}")
            
            return result
        
        raise ValueError(f"Unsupported Macros Define: {type(macros)}")
    
    def read_file(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Verilog File Missing: {file_path}")
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()
    
    def remove_pre_module_content(self, content: str) -> str:
        lines = content.split('\n')
        result_lines = []
        found_module = False
        
        for line in lines:
            stripped_line = line.strip()
            
            if re.match(r'\s*module\s+\w+', stripped_line):
                found_module = True
                result_lines.append(line)
            elif found_module:
                result_lines.append(line)
            
        return '\n'.join(result_lines)
    
    def extract_module_ports_section(self, content: str) -> Tuple[str, str]:
        lines = content.split('\n')
        result_lines = []
        in_module = False
        module_decl_complete = False
        collecting_declaration = False
        current_declaration_lines = []

        for i, line in enumerate(lines):
            stripped_line = line.strip()
            if re.match(r'\s*module\s+\w+', stripped_line):
                in_module = True
                result_lines.append(line)
                continue
            
            if not in_module:
                continue
            
            if not module_decl_complete:
                result_lines.append(line)
                if ';' in line:
                    module_decl_complete = True
                continue
            
            if self._starts_declaration(stripped_line):
                if collecting_declaration and current_declaration_lines:
                    result_lines.extend(current_declaration_lines)

                collecting_declaration = True
                current_declaration_lines = [line]

                if ';' in line:
                    result_lines.extend(current_declaration_lines)
                    collecting_declaration = False
                    current_declaration_lines = []

            elif collecting_declaration:
                current_declaration_lines.append(line)
                if ';' in line:
                    result_lines.extend(current_declaration_lines)
                    collecting_declaration = False
                    current_declaration_lines = []

            elif stripped_line.startswith('endmodule'):
                if collecting_declaration and current_declaration_lines:
                    result_lines.extend(current_declaration_lines)
                break
            
        module_and_ports = '\n'.join(result_lines)
        endmodule = 'endmodule'

        return module_and_ports, endmodule

    def _starts_declaration(self, line: str) -> bool:
        if not line:
            return False

        declaration_keywords = [
            r'^\s*input\s+',
            r'^\s*output\s+', 
            r'^\s*inout\s+',
            r'^\s*parameter\s+'
        ]

        for pattern in declaration_keywords:
            if re.match(pattern, line, re.IGNORECASE):
                return True

        return False
    def process_conditional_compilation(self, content: str) -> str:
        lines = content.split('\n')
        result_lines = []
        condition_stack = []

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped_line = line.strip()

            if stripped_line.startswith('//') or stripped_line.startswith('/*'):
                if self._should_include_line(condition_stack):
                    result_lines.append(line)
                i += 1
                continue
            
            # `ifdef
            ifdef_match = re.match(r'`ifdef\s+(\w+)', stripped_line)
            if ifdef_match:
                macro_name = ifdef_match.group(1)
                condition_met = macro_name in self.macros
                condition_stack.append({
                    'type': 'ifdef', 
                    'condition': condition_met, 
                    'macro': macro_name,
                    'matched': condition_met,  
                    'active': condition_met    
                })
                i += 1
                continue
            
            # `ifndef
            ifndef_match = re.match(r'`ifndef\s+(\w+)', stripped_line)
            if ifndef_match:
                macro_name = ifndef_match.group(1)
                condition_met = macro_name not in self.macros
                condition_stack.append({
                    'type': 'ifndef', 
                    'condition': condition_met, 
                    'macro': macro_name,
                    'matched': condition_met,  
                    'active': condition_met    
                })
                i += 1
                continue
            
            # `else
            if stripped_line.startswith('`else'):
                if condition_stack:
                    current = condition_stack[-1]
                    current['active'] = not current['matched']
                    if current['active']:
                        current['matched'] = True
                i += 1
                continue
            
            # `elsif
            elsif_match = re.match(r'`elsif\s+(\w+)', stripped_line)
            if elsif_match:
                macro_name = elsif_match.group(1)
                if condition_stack:
                    current = condition_stack[-1]
                    if not current['matched']:
                        condition_met = macro_name in self.macros
                        current['active'] = condition_met
                        if condition_met:
                            current['matched'] = True
                        current['macro'] = macro_name
                        current['type'] = 'elsif'
                    else:
                        current['active'] = False
                i += 1
                continue
            
            # `endif
            if stripped_line.startswith('`endif'):
                if condition_stack:
                    condition_stack.pop()
                i += 1
                continue
            
            if self._should_include_line(condition_stack):
                result_lines.append(line)

            i += 1

        return '\n'.join(result_lines)

    def _should_include_line(self, condition_stack: List[Dict]) -> bool:
        if not condition_stack:
            return True

        for condition in condition_stack:
            if not condition.get('active', True):
                return False
        return True
    
    def preprocess_file(self, file_path: str) -> str:
        try:
            content = self.read_file(file_path)
            content = self.remove_pre_module_content(content)
            module_decl, endmodule = self.extract_module_ports_section(content)
            processed_ports = self.process_conditional_compilation(module_decl)
            
            result = processed_ports + '\n' + endmodule
            return result
        except Exception as e:
            raise RuntimeError(f"Preprocess Failed: {str(e)}")
    
    def preprocess_string(self, verilog_code: str) -> str:
        try:
            content = self.remove_pre_module_content(verilog_code)
            module_decl, endmodule = self.extract_module_ports_section(content)
            processed_ports = self.process_conditional_compilation(module_decl)
            
            result = processed_ports + '\n' + endmodule
            return result
        except Exception as e:
            raise RuntimeError(f"Preprocess Failed: {str(e)}")
    
    def update_macros(self, new_macros: Union[Dict[str, str], List[str], List[Tuple[str, str]]]):
        parsed_macros = self._parse_macros(new_macros)
        self.macros.update(parsed_macros)
    
    def clear_macros(self):
        self.macros.clear()
    
    def get_macros(self) -> Dict[str, str]:
        return self.macros.copy()


if __name__ == "__main__":
    
    macros = ['DEBUG_MODE', 'FEATURE_X']
    preprocessor = VerilogPreprocess(macros)
    
    sample_code = """
`timescale 1ns/1ps
`include "common.vh"
`ifndef XX
    `define TEST
`endif 

module test_module (
    input clk,
    input rst,
`ifdef DEBUG_MODE
    output debug_signal,
`endif
    input [`DATA_WIDTH-1:0] data_in,
    output [`DATA_WIDTH-1:0] data_out
);

    // module body content
    reg [`DATA_WIDTH-1:0] internal_reg;
    
    always @(posedge clk) begin
        if (rst) begin
            internal_reg <= 0;
        end else begin
            internal_reg <= data_in;
        end
    end
    
    assign data_out = internal_reg;

endmodule
"""
    test_verilog = '''
module test_module #(
    parameter WIDTH = 8,
    parameter DEPTH = 16
) (
  clk,
    rst,
     data_in,
    data_out
);
    parameter WIDTH2 = 8;
    parameter DEPTH2 = 18;
    parameter WIDTH3 = 8, DEPTH3 = 16;
 input wire clk;
    input wire rst;
input wire [WIDTH-1:0]data_in;
output reg [WIDTH-1:0] data_out;

// 其他逻辑代码
always @(posedge clk) begin
    // ...
end

endmodule
'''
    file_path = "axi_slave.v"
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
                verilog_code = f.read()
        result = preprocessor.preprocess_string(verilog_code)
        print(result)
    except Exception as e:
        print(f"Error: {e}")
