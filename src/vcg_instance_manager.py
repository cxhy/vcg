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
from typing import List, Dict, Optional, Tuple
from .VerilogParser import VerilogParser
from .VerilogAst import PortInfo, ParameterInfo, PortType
from .vcg_rule_manager import VCGRuleManager
from .vcg_exceptions import VCGRuntimeError, VCGSyntaxError, VCGFileError, VCGParseError
from .vcg_logger import get_vcg_logger

class InstanceManager:
    
    def __init__(self, rule_manager: VCGRuleManager, macros=None):
        self.rule_manager = rule_manager
        self.macros = macros
        self.logger = get_vcg_logger('InstanceManager')
        self._ALIGN = 18
        self.parser = VerilogParser(macros=self.macros, debug=False)
    
    def generate_instance(self, file_path: str, module_name: str, instance_name: str) -> str:
        try:
            self.logger.info(f"Generating instance '{instance_name}' of module '{module_name}' from {file_path}")
            
            ast = self._parse_verilog_file(file_path)
            
            ports = ast.get_port_info()
            parameters = ast.get_parameter_info()
            
            self.logger.debug(f"Found {len(ports)} ports and {len(parameters)} parameters")
            
            port_connections, port_infos = self._generate_port_connections(ports)
            param_connections = self._generate_param_connections(parameters)
            
            connected_ports = len([conn for conn in port_connections.values() if conn != ''])
            connected_params = len(param_connections)
            
            self.logger.debug(f"Generated {connected_ports}/{len(ports)} port connections and {connected_params} parameter connections")
            
            instance_code = self._render_instance_code(
                module_name, instance_name, param_connections, port_connections, port_infos
            )
            
            if instance_code.strip():
                lines = instance_code.split('\n')
                port_count = sum(1 for line in lines if '.(' in line and ')' in line)
                self.logger.info(f"Instance '{instance_name}' generated successfully with {port_count} port connections")
            
            return instance_code
            
        except FileNotFoundError:
            self.logger.error(f"Verilog file not found: {file_path}")
            raise VCGFileError(f"Cannot find Verilog File: {file_path}")
        except Exception as e:
            self.logger.error(f"Instance generation failed: {e}")
            raise VCGParseError(f"Generate instance Error: {e}")
    
    def _parse_verilog_file(self, file_path: str):
        self.logger.debug(f"Parsing Verilog file: {file_path}")
        ast = self.parser.parse_file(file_path)
        if not ast:
            raise VCGParseError(f"Cannot Parse Verilog File: {file_path}")
        return ast
    
    def _generate_port_connections(self, ports: List[PortInfo]) -> Tuple[Dict[str, str], Dict[str, PortInfo]]:
        connections = {}
        port_infos = {}
        
        self.logger.debug("Generating port connections...")
        
        for port in ports:
            port_name = port.name
            target_signal = self.rule_manager.resolve_signal_connection(port)
            connections[port_name] = target_signal
            port_infos[port_name] = port
            
            self.logger.debug(f"Port '{port_name}' -> '{target_signal}'")
            
        return connections, port_infos
    
    def _generate_param_connections(self, parameters: List[ParameterInfo]) -> Dict[str, str]:
        connections = {}
        
        self.logger.debug("Generating parameter connections...")
        
        for param in parameters:
            param_name = param.name
            param_value = self.rule_manager.resolve_param_connection(param_name)
            if param_value is not None:
                connections[param_name] = param_value
                self.logger.debug(f"Parameter '{param_name}' -> '{param_value}'")
                
        return connections
    
    def _render_instance_code(self, module_name: str, instance_name: str,
                            param_connections: Dict[str, str], port_connections: Dict[str, str],
                            port_infos: Dict[str, PortInfo]) -> str:
        lines = []
        
        if param_connections:
            lines.append(f"{module_name} #(")
            lines.extend(self._render_parameter_section(param_connections))
            lines.append(f") {instance_name} (")
        else:
            lines.append(f"{module_name} {instance_name} (")
        
        lines.extend(self._render_port_section(port_connections, port_infos))
        
        lines.append(");")
        
        return '\n'.join(lines)
    
    def _render_parameter_section(self, param_connections: Dict[str, str]) -> List[str]:
        param_lines = []
        param_items = list(param_connections.items())
        
        for i, (param_name, param_value) in enumerate(param_items):
            line = f"    .{param_name:<{self._ALIGN}}({param_value})"
            if i < len(param_items) - 1:
                line += ","
            param_lines.append(line)
        return param_lines
    
    def _render_port_section(self, port_connections: Dict[str, str], 
                           port_infos: Dict[str, PortInfo]) -> List[str]:
        port_lines = []
        port_names = list(port_connections.keys())
        
        for i, port_name in enumerate(port_names):
            signal_name = port_connections[port_name]
            
            connection_part = f".{port_name:<{self._ALIGN}}({signal_name})"
            if i < len(port_names) - 1:
                connection_part += ","
            
            base_line = f"    {connection_part}"
            if port_name in port_infos:
                comment = self._generate_port_comment(port_infos[port_name])
                if comment:
                    base_line = f"    {connection_part:<{self._ALIGN * 2}}{comment}"
            port_lines.append(base_line)
        
        return port_lines
    
    def _generate_port_comment(self, port: PortInfo) -> str:
        comment_parts = []

        if port.direction:
            comment_parts.append(f"// {port.direction}")
        else:
            return ""

        if port.net_type and port.net_type.lower() != 'wire':
            comment_parts.append(port.net_type)

        if port.range_string:
            comment_parts.append(port.range_string)

        if port.port_type == PortType.INTERFACE:
            comment_parts.append(f"<{port.interface_type}>")
        elif port.port_type in [PortType.ARRAY_2D, PortType.ARRAY_3D]:
            comment_parts.append("[ARRAY]")

        return " ".join(comment_parts)
    
    def set_alignment(self, align: int):
        self._ALIGN = align
        self.logger.debug(f"Set alignment width to {align}")
    
    def get_alignment(self) -> int:
        return self._ALIGN