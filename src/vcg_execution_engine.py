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
from vcg_rule_manager import VCGRuleManager
from vcg_instance_manager import InstanceManager
from vcg_wires_manager import WiresManager
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

class VCGExecutionEngine:
    
    def __init__(self, macros=None):
        self.rule_manager = VCGRuleManager()
        self.output_manager = OrderedOutputManager()
        self.wires_manager = WiresManager(self.rule_manager, macros=macros)
        self.instance_manager = InstanceManager(self.rule_manager, macros=macros)  # 新增self.macros = macros
        self.logger = get_vcg_logger('ExecutionEngine')
    def execute(self, python_code: str) -> str:
        try:
            self.logger.debug("Starting Python code execution")
            
            self.rule_manager.reset()
            self.output_manager.clear()
            
            context = self._create_execution_context()
            
            exec(python_code, context)
            
            return self.output_manager.get_final_output()
            
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
    
    def _create_instance_func(self):
        def Instance(file_path: str, module_name: str, instance_name: str):
            instance_code = self.instance_manager.generate_instance(
                file_path, module_name, instance_name
            )
            if instance_code.strip():
                self.output_manager.add_instance_output(instance_code)
        return Instance
    
    def _create_wires_def_func(self):
        def WiresDef(file_path: str, module_name: str, port_type: Optional[str] = None, pattern: str = 'greedy'):
            wire_code = self.wires_manager.generate_wires_def(
                file_path, module_name, port_type, pattern
            )
            if wire_code.strip():
                self.output_manager.add_wires_output(wire_code)
        
        return WiresDef
    
    def _create_connect_func(self):
        def Connect(source_pattern: str, target_pattern: str, port_type: Optional[str] = None):
            self.rule_manager.add_signal_rule(source_pattern, target_pattern, port_type)
        
        return Connect
    
    def _create_connect_param_func(self):
        def ConnectParam(param_name: str, param_value: str):
            self.rule_manager.add_param_rule(param_name, param_value)
        
        return ConnectParam
    
    def _create_wires_rule_func(self):
        def WiresRule(port_pattern: str, wire_pattern: str, width: Optional[str] = None, expression: Optional[str] = None):
            self.rule_manager.add_wire_rule(port_pattern, wire_pattern, width, expression)
        
        return WiresRule
    
    def _create_custom_print_func(self):
        def custom_print(*args, sep=' ', end='\n', file=None, flush=False):
            if file is not None:
                print(*args, sep=sep, end=end, file=file, flush=flush)
                return
            
            text = sep.join(str(arg) for arg in args) + end
            self.output_manager.add_text_output(text)
        return custom_print