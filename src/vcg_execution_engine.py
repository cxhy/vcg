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
import io
import sys
import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from VerilogParser import parse_verilog_file
from VerilogAst import PortInfo, ParameterInfo
from vcg_connect_manager import VCGConnectManager
from vcg_exceptions import VCGRuntimeError, VCGSyntaxError, VCGFileError, VCGParseError
from vcg_logger import get_vcg_logger

class OrderedOutputManager:  
    def __init__(self):
        self.outputs: List[str] = []
    
    def add_text_output(self, text: str):
        if text == '\n':
            self.outputs.append('')
        elif text.strip():
            self.outputs.append(text.rstrip())
        elif text and not text.strip():
            if '\n' in text:
                self.outputs.append('')
    
    def add_instance_output(self, instance_code: str):
        if instance_code.strip():
            self.outputs.append(instance_code)
    
    def add_wires_output(self, wires_code: str):
        if wires_code.strip():
            self.outputs.append(wires_code)
    
    def get_final_output(self) -> str:
        return '\n'.join(self.outputs)
    
    def clear(self):
        self.outputs.clear()

class WiresManager:
    def __init__(self, macros = None):
        self.current_rules: List[Dict] = []
        self.macros = macros
        self.logger = get_vcg_logger('WiresManager') 
        self.safe_functions = {
            'upper': str.upper,
            'lower': str.lower,
            'title': str.title,
            'capitalize': str.capitalize,
            'replace': str.replace,
            'strip': str.strip,
            'lstrip': str.lstrip,
            'rstrip': str.rstrip,
        }
        
    def reset(self):
        self.current_rules.clear()
        self.logger.debug(f"Reset wire rules (cleared {len(self.current_rules)} rules)")
    
    def add_wire_rule(self, port_pattern: str, wire_pattern: str, 
                     width: Optional[str] = None, expression: Optional[str] = None):
        rule = {
            'port_pattern': port_pattern,
            'wire_pattern': wire_pattern,
            'width': width,
            'expression': expression,
            'priority': len(self.current_rules)
        }
        self.current_rules.append(rule)
        rule_desc = f"'{port_pattern}' -> '{wire_pattern}'"
        if width:
            rule_desc += f" (width: {width})"
        if expression:
            rule_desc += f" (expr: {expression})"
        self.logger.debug(f"Added wire rule #{rule['priority']}: {rule_desc}")
    
    def generate_wires_def(self, file_path: str, module_name: str, 
                          port_type: Optional[str] = None) -> str:
        try:
            self.logger.debug(f"Generating wire definitions from {file_path} for module '{module_name}' (type: {port_type or 'all'})")
            ast = parse_verilog_file(file_path, macros=self.macros)
            if not ast:
                raise VCGParseError(f"Cannot Parser Verilog file: {file_path}")

            ports = self._get_ports_by_type(ast, port_type)
            self.logger.debug(f"Found {len(ports)} ports to process")

            if self.current_rules:
                self.logger.debug(f"Applying {len(self.current_rules)} wire rules")
            else:
                self.logger.warning("No wire rules defined, using default wire generation")

            wire_declarations = []
            generated_count = 0
            skipped_count = 0

            for port in ports:
                wire_decl = self._generate_single_wire(port)
                if wire_decl and wire_decl.strip():
                    wire_declarations.append(wire_decl)
                    generated_count += 1
                    self.logger.debug(f"Generated wire for port '{port.name}': {wire_decl.strip()}")
                else:
                    skipped_count += 1
                    self.logger.debug(f"Skipped port '{port.name}' (no wire generated)")

            self.current_rules.clear()

            self.logger.info(f"Wire generation completed: {generated_count} wires generated, {skipped_count} ports skipped")

            return '\n'.join(wire_declarations)

        except FileNotFoundError:
            self.logger.error(f"Verilog file not found: {file_path}")
            raise VCGFileError(f"Cannot found Verilog File: {file_path}")
        except Exception as e:
            self.logger.error(f"Wire generation failed: {e}")
            raise VCGParseError(f"Generate Wire Error: {e}")
        

    
    def _get_ports_by_type(self, ast, port_type: Optional[str]) -> List[PortInfo]:
        if port_type is None:
            self.logger.debug("Retrieved all module ports")
            return ast.get_module_ports()
        elif port_type.lower() == 'input':
            self.logger.debug("Retrieved input ports only")
            return ast.get_input_ports()
        elif port_type.lower() == 'output':
            self.logger.debug("Retrieved output ports only")
            return ast.get_output_ports()
        elif port_type.lower() == 'inout':
            self.logger.debug("Retrieved inout ports only")
            return ast.get_inout_ports()
        else:
            self.logger.error(f"Invalid port type: {port_type}")
            raise ValueError(f"Unsupport port type: {port_type}")
    
    def _generate_single_wire(self, port: PortInfo) -> str:
        port_name = port.name

        wire_name, width, expression = self._apply_wire_rules(port_name, port)

        if not wire_name or not wire_name.strip():
            self.logger.debug(f"Port '{port_name}' -> empty wire name, skipping")
            return ""

        wire_decl = "wire"

        if width:
            formatted_width = self._format_wire_width(width)
            if formatted_width:
                wire_decl += f" {formatted_width}"
        elif hasattr(port, 'width') and port.width and port.width != '1':
            formatted_width = self._format_wire_width(port.width)
            if formatted_width:
                wire_decl += f" {formatted_width}"

        wire_decl += f" {wire_name}"

        if expression:
            wire_decl += f" = {expression};"
        else:
            wire_decl += ";"

        return wire_decl

    def _format_wire_width(self, width_input) -> str:
        if not width_input:
            return ""

        if isinstance(width_input, int):
            return "" if width_input <= 1 else f"[{width_input-1}:0]"

        width_str = str(width_input).strip()
        if not width_str:
            return ""

        if width_str.isdigit():
            width_num = int(width_str)
            return "" if width_num <= 1 else f"[{width_num-1}:0]"

        plus_one_pattern = r'^(.+?)\s*\+\s*1$'
        match = re.match(plus_one_pattern, width_str)
        if match:
            base_expr = match.group(1).strip()
            if base_expr.startswith('$') and '(' in base_expr:
                return f"[{base_expr}:0]"
            elif any(op in base_expr for op in ['+', '-', '*', '/', ' ']):
                return f"[({base_expr}):0]"
            else:
                return f"[{base_expr}:0]"
        else:
            if any(op in width_str for op in ['+', '-', '*', '/', '(', ')']):
                return f"[({width_str})-1:0]"
            else:
                return f"[{width_str}-1:0]"
    
    def _apply_wire_rules(self, port_name: str, port: PortInfo) -> Tuple[str, Optional[str], Optional[str]]:
        wire_name = port_name
        width = None
        expression = None
        applied_rule = None

        for rule in reversed(self.current_rules):
            if self._match_pattern(port_name, rule['port_pattern']):
                pattern_result = rule['wire_pattern']

                if not pattern_result or not str(pattern_result).strip():
                    wire_name = ""
                else:
                    wire_name = self._apply_pattern_substitution_with_functions(
                        port_name, rule['port_pattern'], pattern_result
                    )

                if rule['width'] is not None:
                    width = rule['width']

                if rule['expression'] is not None:
                    expression = rule['expression']
                applied_rule = rule
                break
        if applied_rule:
            self.logger.debug(f"Applied rule #{applied_rule['priority']} to port '{port_name}' -> wire '{wire_name}'")
        else:
            self.logger.debug(f"No rules matched port '{port_name}', using default wire name")
            
        return wire_name, width, expression
    
    def _match_pattern(self, signal_name: str, pattern: str) -> bool:
        if '*' in pattern:
            regex_pattern = pattern.replace('*', '(.*)')
            return bool(re.match(f'^{regex_pattern}$', signal_name))
        else:
            return signal_name == pattern
    
    def _apply_pattern_substitution(self, signal_name: str, source_pattern: str, target_pattern: str) -> str:
        if '*' in source_pattern:
            regex_pattern = source_pattern.replace('*', '(.*)')
            match = re.match(f'^{regex_pattern}$', signal_name)
            if match:
                result = target_pattern
                for group in match.groups():
                    result = result.replace('*', group, 1)
                return result
        
        return target_pattern
    
    def _apply_pattern_substitution_with_functions(self, signal_name: str, source_pattern: str, target_pattern: str) -> str:
        if '*' in source_pattern:
            regex_pattern = source_pattern.replace('*', '(.*)')
            match = re.match(f'^{regex_pattern}$', signal_name)
            if match:
                result = target_pattern
                groups = match.groups()
                
                function_pattern = r'\$\{([^}]+)\}'
                
                def replace_function_call(match_obj):
                    function_call = match_obj.group(1)
                    return self._execute_function_call(function_call, groups)
                
                result = re.sub(function_pattern, replace_function_call, result)

                comment_pattern = r'/\*(.*?)\*/'
                comments = []

                def save_comment(match_obj):
                    comment_content = match_obj.group(1)
                    placeholder = f"__COMMENT_PLACEHOLDER_{len(comments)}__"
                    comments.append(comment_content)
                    return f"/{placeholder}/"
                
                result_with_placeholders = re.sub(comment_pattern, save_comment, result)
                
                for group in groups:
                    result_with_placeholders = result_with_placeholders.replace('*', group, 1)
                    #result = result.replace('*', group, 1)
                
                for i, comment in enumerate(comments):
                    result_with_placeholders = result_with_placeholders.replace(
                    f"__COMMENT_PLACEHOLDER_{i}__", f"*{comment}*")
                
                return result_with_placeholders
                
                #return result
        
        return target_pattern
    
    def _execute_function_call(self, function_call: str, groups: tuple) -> str:
        try:
            processed_call = function_call
            for i, group in enumerate(groups):
                processed_call = processed_call.replace(f'*{i}', f'group_{i}')
            
            processed_call = processed_call.replace('*', 'group_0')
            
            local_vars = {}
            for i, group in enumerate(groups):
                local_vars[f'group_{i}'] = group
            
            local_vars.update(self.safe_functions)
            local_vars['str'] = str
            
            result = eval(processed_call, {"__builtins__": {}}, local_vars)
            return str(result)
            
        except Exception as e:
            self.logger.warning(f"Function call evaluation failed: {function_call}, error: {e}")
            return groups[0] if groups else function_call

class VCGExecutionEngine:   
    def __init__(self,macros = None):
        self.connect_manager = VCGConnectManager()
        self.output_manager = OrderedOutputManager()
        self.wires_manager = WiresManager(macros=macros)
        self.macros = macros
        self.logger = get_vcg_logger('ExecutionEngine')
        self._ALIGN = 18
        
    def execute(self, python_code: str) -> str:
        try:
            self.logger.debug("Starting Python code execution")

            self.logger.debug("Resetting execution environment")
            self.connect_manager.reset()
            self.output_manager.clear()
            self.wires_manager.reset()
            
            context = self._create_execution_context()
            self.logger.debug("Created execution context with VCG functions")
            
            self.logger.debug("Executing Python code in VCG context")
            exec(python_code, context)

            result = self.output_manager.get_final_output()
            
            if result.strip():
                line_count = len(result.split('\n'))
                self.logger.info(f"Code execution completed successfully, generated {line_count} lines")
            else:
                self.logger.warning("Code execution completed but no content was generated")
            
            return result
            
        except SyntaxError as e:
            self.logger.error(f"Python syntax error at line {e.lineno}: {e.msg}")
            raise VCGSyntaxError(f"Python syntax Error: {e.msg} (Line{e.lineno})")
        except Exception as e:
            self.logger.error(f"Execution error: {str(e)}")
            raise VCGRuntimeError(f"Exec Error: {str(e)}")
    
    def _create_execution_context(self) -> dict:
        context = {
            '__builtins__': __builtins__,
            'print': self._create_custom_print_func(),
            'Instance': self._create_instance_func(),
            'Connect': self._create_connect_func(),
            'ConnectParam': self._create_connect_param_func(),
            'WiresDef': self._create_wires_def_func(),
            'WiresRule': self._create_wires_rule_func(),
        }
        return context
    
    def _create_custom_print_func(self):
        def custom_print(*args, sep=' ', end='\n', file=None, flush=False):
            if file is not None:
                print(*args, sep=sep, end=end, file=file, flush=flush)
                return
            
            text = sep.join(str(arg) for arg in args) + end
            self.output_manager.add_text_output(text)
            self.logger.debug(f"Print output: {repr(text.rstrip())}")
        
        return custom_print
    
    def _create_wires_def_func(self):
        def WiresDef(file_path: str, module_name: str, port_type: Optional[str] = None):
            self.logger.info(f"Generating wire definitions for module '{module_name}' from {file_path}")
            wire_code = self.wires_manager.generate_wires_def(
                file_path, module_name, port_type
            )

            if wire_code.strip():
                self.output_manager.add_wires_output(wire_code)
                wire_count = len([line for line in wire_code.split('\n') if line.strip()])
                self.logger.info(f"WiresDef generated {wire_count} wire declarations")
            else:
                self.logger.warning(f"WiresDef generated no wire declarations for {module_name}")

        return WiresDef
    
    def _create_wires_rule_func(self):
        def WiresRule(port_pattern: str, wire_pattern: str, width: Optional[str] = None, expression: Optional[str] = None):
            self.logger.debug(f"Adding wire rule: '{port_pattern}' -> '{wire_pattern}'")
            self.wires_manager.add_wire_rule(
                port_pattern, wire_pattern, width, expression
            )

        return WiresRule
    
    def _create_instance_func(self):
        def Instance(file_path: str, module_name: str, instance_name: str):
            self.logger.info(f"Generating instance '{instance_name}' of module '{module_name}' from {file_path}")
            instance_code = self._generate_instance_with_rules(
                file_path, module_name, instance_name
            )
            
            if instance_code.strip():
                self.output_manager.add_instance_output(instance_code)
                lines = instance_code.split('\n')
                port_count = sum(1 for line in lines if '.(' in line and ')' in line)
                self.logger.info(f"Instance '{instance_name}' generated successfully with {port_count} port connections")
            else:
                self.logger.error(f"Failed to generate instance code for '{instance_name}'")
            
            self.connect_manager.reset()
            

        return Instance
    
    def _create_connect_func(self):
        def Connect(source_pattern: str, target_pattern: str, port_type: Optional[str] = None):
            if port_type is not None:
                valid_types = ['input', 'output', 'inout']
                if port_type.lower() not in valid_types:
                    self.logger.error(f"Invalid port_type: {port_type}")
                    raise ValueError(f"Invalid port_type: {port_type}. Must be one of {valid_types}")
            self.logger.debug(f"Adding connection rule: '{source_pattern}' -> '{target_pattern}' (type: {port_type or 'all'})")
            self.connect_manager.add_signal_rule(source_pattern, target_pattern, port_type)

            rules_summary = self.connect_manager.get_rules_summary()
            self.logger.debug(f"Current rules count: {rules_summary}")
                #self.connect_manager.add_signal_rule(source_pattern, target_pattern)
        
        return Connect
    
    def _create_connect_param_func(self):
        def ConnectParam(param_name: str, param_value: str):
            self.logger.debug(f"Adding parameter connection: {param_name} = {param_value}")
            self.connect_manager.add_param_rule(param_name, param_value)
        
        return ConnectParam
    
    def _generate_instance_with_rules(self, file_path: str, module_name: str, instance_name: str) -> str:
        try:
            self.logger.debug(f"Parsing Verilog file: {file_path}")
            ast = parse_verilog_file(file_path, macros=self.macros)
            if not ast:
                raise VCGParseError(f"Cannot Parse Verilog File: {file_path}")

            ports = ast.get_module_ports()
            parameters = ast.get_module_parameters()

            self.logger.debug(f"Found {len(ports)} ports and {len(parameters)} parameters")

            port_connections, port_infos = self._generate_port_connections(ports)
            param_connections = self._generate_param_connections(parameters)

            connected_ports = len([conn for conn in port_connections.values() if conn != ''])
            connected_params = len(param_connections)
            
            self.logger.debug(f"Generated {connected_ports}/{len(ports)} port connections and {connected_params} parameter connections")

            return self._render_instance_code(
                module_name, instance_name, param_connections, port_connections, port_infos
            )

        except FileNotFoundError:
            self.logger.error(f"Verilog file not found: {file_path}")
            raise VCGFileError(f"Cannot find Verilog File: {file_path}")
        except Exception as e:
            self.logger.error(f"Instance generation failed: {e}")
            raise VCGParseError(f"Generate instance Error: {e}")
    
    def _generate_port_connections(self, ports: List[PortInfo]) -> Tuple[Dict[str, str], Dict[str, PortInfo]]:
        connections = {}
        port_infos = {}
        
        for port in ports:
            port_name = port.name
            target_signal = self.connect_manager.resolve_signal_connection(port)
            connections[port_name] = target_signal
            port_infos[port_name] = port
            
        return connections, port_infos
    
    def _generate_param_connections(self, parameters: List[ParameterInfo]) -> Dict[str, str]:
        connections = {}
        
        for param in parameters:
            param_name = param.name
            param_value = self.connect_manager.resolve_param_connection(param_name)
            if param_value is not None:
                connections[param_name] = param_value
                
        return connections
    
    def _render_instance_code(self, module_name: str, instance_name: str, 
                            param_connections: Dict[str, str], port_connections: Dict[str, str],
                            port_infos: Dict[str, PortInfo]) -> str:
        lines = []
        
        if param_connections:
            lines.append(f"{module_name} #(")
            
            param_lines = []
            for param_name, param_value in param_connections.items():
                param_lines.append(f"    .{param_name:<{self._ALIGN}}({param_value})")
            
            for i, line in enumerate(param_lines):
                if i < len(param_lines) - 1:
                    lines.append(line + ",")
                else:
                    lines.append(line)
            
            lines.append(f") {instance_name} (")
        else:
            lines.append(f"{module_name} {instance_name} (")
        
        port_lines = []
        port_names = list(port_connections.keys())
        for i, port_name in enumerate(port_names):
            signal_name = port_connections[port_name]

            connection_part = f".{port_name:<{self._ALIGN}}({signal_name})"

            if i < len(port_names) - 1:
                connection_part += ","

            if port_name in port_infos:
                comment = self._generate_port_comment(port_infos[port_name])
                if comment:
                    base_line = f"    {connection_part:<{self._ALIGN * 2}}{comment}"
                else:
                    base_line = f"    {connection_part}"
            else:
                base_line = f"    {connection_part}"


            lines.append(base_line)

        lines.append(");")

        return '\n'.join(lines)

    
    def _generate_port_comment(self, port: PortInfo) -> str:
        if not hasattr(port, 'direction'):
            return ""

        direction = port.direction.lower()
        comment_parts = [f"// {direction}"]

        if hasattr(port, 'width') and port.width:
            width_str = self._format_port_width_comment(port.width)
            if width_str:
                comment_parts.append(width_str)

        return " ".join(comment_parts)

    def _format_port_width_comment(self, width) -> str:
        if not width:
            return ""

        if isinstance(width, int):
            if width <= 1:
                return "" 
            else:
                return f"[{width-1}:0]"

        width_str = str(width).strip()
        if not width_str:
            return ""

        if width_str.isdigit():
            width_num = int(width_str)
            if width_num <= 1:
                return ""
            else:
                return f"[{width_num-1}:0]"
            
        plus_one_pattern = r'^(.+?)\s*\+\s*1$'
        match = re.match(plus_one_pattern, width_str)
        if match:
            base_expr = match.group(1).strip()
            if base_expr.startswith('$') and '(' in base_expr:
                return f"[{base_expr}:0]" 
            elif any(op in base_expr for op in ['+', '-', '*', '/', ' ']):
                return f"[({base_expr}):0]" 
            else:
                return f"[{base_expr}:0]"
        else:
            if any(op in width_str for op in ['+', '-', '*', '/', '(', ')']):
                return f"[({width_str})-1:0]"
            else:
                return f"[{width_str}-1:0]"
