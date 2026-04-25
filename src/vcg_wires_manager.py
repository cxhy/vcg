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
from typing import List, Dict, Optional, Tuple
from .VerilogParser import VerilogParser
from .VerilogAst import PortInfo, ParameterInfo, PortType
from .vcg_rule_manager import VCGRuleManager
from .vcg_exceptions import VCGRuntimeError, VCGSyntaxError, VCGFileError, VCGParseError
from .vcg_logger import get_vcg_logger

class WiresManager:
    
    def __init__(self, rule_manager: VCGRuleManager, macros=None):
        self.rule_manager = rule_manager
        self.macros = macros
        self.logger = get_vcg_logger('WiresManager')
        self._BASE_SPACING = 15
        self.parser = VerilogParser(macros=self.macros, debug=False)
    
    def generate_wires_def(self, file_path: str, module_name: str,
                          port_direction: Optional[str] = None, 
                          pattern: str = 'greedy') -> str:
        try:
            if pattern not in ['lazy', 'greedy']:
                raise ValueError(f"Invalid pattern: {pattern}. Must be 'lazy' or 'greedy'")

            self.logger.debug(f"Generating wire definitions from {file_path} for module '{module_name}' "
                            f"(direction: {port_direction or 'all'}, pattern: {pattern})")
            
            ast = self._parse_verilog_file(file_path)
            
            ports = self._get_ports_by_direction(ast, port_direction)
            self.logger.debug(f"Found {len(ports)} ports to process")

            wire_declarations = []
            generated_count = 0
            skipped_count = 0

            for port in ports:
                wire_decl = self._generate_single_wire(port, pattern)
                if wire_decl and wire_decl.strip():
                    wire_declarations.append(wire_decl)
                    generated_count += 1
                    self.logger.debug(f"Generated wire for port '{port.name}': {wire_decl.strip()}")
                else:
                    skipped_count += 1
                    self.logger.debug(f"Skipped port '{port.name}' (no wire generated)")

            self.logger.info(f"Wire generation completed: {generated_count} wires generated, {skipped_count} ports skipped")
            return '\n'.join(wire_declarations)

        except (VCGFileError, VCGParseError, ValueError):
            raise
        except Exception as e:
            self.logger.error(f"Wire generation failed: {e}")
            raise VCGRuntimeError(f"Generate Wire Error: {e}") from e

    def _parse_verilog_file(self, file_path: str):
        self.logger.debug(f"Parsing Verilog file: {file_path}")
        return self.parser.parse_file(file_path)
    
    def _get_ports_by_direction(self, ast, port_direction: Optional[str]) -> List[PortInfo]:
        all_ports = ast.get_port_info()
        
        if port_direction is None:
            self.logger.debug(f"Retrieved all {len(all_ports)} module ports")
            return all_ports
        
        direction_lower = port_direction.lower()
        if direction_lower not in ['input', 'output', 'inout']:
            self.logger.error(f"Invalid port direction: {port_direction}")
            raise ValueError(f"Unsupported port direction: {port_direction}")
        
        filtered_ports = [p for p in all_ports if p.direction and p.direction.lower() == direction_lower]
        
        self.logger.debug(f"Retrieved {len(filtered_ports)} {direction_lower} ports "
                         f"(out of {len(all_ports)} total)")
        
        return filtered_ports
    
    def _generate_single_wire(self, port: PortInfo, pattern: str = 'greedy') -> str:
        port_name = port.name
        
        wire_name, width, expression, rule_matched = self.rule_manager.resolve_wire_generation(port, pattern)

        if pattern == 'lazy' and not rule_matched:
            self.logger.debug(f"Port '{port_name}' -> no rule matched in lazy mode, skipping")
            return ""

        if not wire_name or not wire_name.strip():
            if rule_matched:
                self.logger.debug(f"Port '{port_name}' -> rule matched but returned empty wire name, respecting rule intent")
                return ""
            elif pattern == 'greedy':
                wire_name = port_name
                self.logger.debug(f"Port '{port_name}' -> no rule matched, using default wire name in greedy mode")
            else:
                self.logger.debug(f"Port '{port_name}' -> no rule matched in lazy mode, skipping")
                return ""

        return self._format_wire_declaration(wire_name, width, expression, port)
    
    def _format_wire_declaration(self, wire_name: str, width: Optional[str], expression: Optional[str], port: PortInfo) -> str:
        width_str = ""
        if width:
            width_str = self._format_wire_width(width)
        elif port.range_string:
            width_str = self._format_wire_width(port.width)

        if width_str:
            prefix = f"wire {width_str}"
            prefix_length = len(prefix)
            
            if prefix_length >= self._BASE_SPACING:
                spacing = " "
            else:
                spacing = " " * (self._BASE_SPACING - prefix_length)
        else:
            prefix = "wire"
            spacing = " " * (self._BASE_SPACING - len("wire"))

        if expression:
            wire_decl = f"{prefix}{spacing}{wire_name} = {expression};"
        else:
            wire_decl = f"{prefix}{spacing}{wire_name};"

        return wire_decl
    
    def _format_wire_width(self, width_input) -> str:
        if not width_input:
            return ""

        if isinstance(width_input, int):
            return "" if width_input <= 1 else f"[{width_input-1}:0]"

        width_str = str(width_input).strip()
        if not width_str:
            return ""
        
        if self._is_multi_dimensional(width_str):
            self.logger.debug(f"Multi-dimensional array: {width_str}")
            return width_str
        
        if width_str.startswith('[') and width_str.endswith(']') and width_str.count('[') == 1:
            return width_str

        if width_str.isdigit():
            width_num = int(width_str)
            return "" if width_num <= 1 else f"[{width_num-1}:0]"
        
        if any(op in width_str for op in ['+', '-', '*', '/', '(', ')']):
            return f"[({width_str})-1:0]"
        else:
            return f"[{width_str}-1:0]"

    def _is_multi_dimensional(self, width_str: str) -> bool:
        if '[' not in width_str or ']' not in width_str:
            return False

        dimension_count = width_str.count(']')

        if dimension_count >= 2:
            if '][' in width_str:
                self.logger.debug(f"Multi-dimensional array detected: {dimension_count} dimensions")
                return True

        return False    

    def set_base_spacing(self, spacing: int):
        self._BASE_SPACING = spacing
        self.logger.debug(f"Set base spacing to {spacing}")
    
    def get_base_spacing(self) -> int:
        return self._BASE_SPACING