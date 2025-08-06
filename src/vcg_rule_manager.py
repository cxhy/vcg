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
from typing import List, Dict, Optional, Tuple, Any
from VerilogAst import PortInfo
from vcg_logger import get_vcg_logger

class VCGRuleManager:
    
    def __init__(self):
        self.rules = {
            'signal_rules': [],   
            'param_rules': [],    
            'wire_rules': []      
        }
        self.logger = get_vcg_logger('RuleManager')
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
    
    def add_signal_rule(self, source_pattern: str, target_pattern: str, port_type: Optional[str] = None):
        processed_target, comments = self._extract_inline_comments(target_pattern)
        
        rule = {
            'type': 'signal',
            'source': source_pattern,
            'target': processed_target,
            'comments': comments,
            'port_type': port_type.lower() if port_type else None,
            'priority': len(self.rules['signal_rules'])
        }
        
        self.rules['signal_rules'].append(rule)
        self.logger.debug(f"Added signal rule #{rule['priority']}: '{source_pattern}' -> '{target_pattern}'")
    
    def add_param_rule(self, param_name: str, param_value: str):
        rule = {
            'type': 'param',
            'param_name': param_name,
            'param_value': param_value,
            'priority': len(self.rules['param_rules'])
        }
        self.rules['param_rules'].append(rule)
        self.logger.debug(f"Added parameter rule #{rule['priority']}: {param_name} = {param_value}")
    
    def add_wire_rule(self, port_pattern: str, wire_pattern: str,
                     width: Optional[str] = None, expression: Optional[str] = None):
        processed_pattern, comments = self._extract_inline_comments(wire_pattern)
        
        rule = {
            'type': 'wire',
            'port_pattern': port_pattern,
            'wire_pattern': processed_pattern,
            'comments': comments,
            'width': width,
            'expression': expression,
            'priority': len(self.rules['wire_rules'])
        }
        
        self.rules['wire_rules'].append(rule)
        self.logger.debug(f"Added wire rule #{rule['priority']}: '{port_pattern}' -> '{wire_pattern}'")
    def reset(self):
        total_rules = sum(len(rules) for rules in self.rules.values())
        self.rules = {
            'signal_rules': [],
            'param_rules': [], 
            'wire_rules': []
        }
        self.logger.debug(f"Reset all rules (cleared {total_rules} rules)")
    
    def resolve_signal_connection(self, port: PortInfo) -> str:
        signal_name = port.name
        rules = self.rules['signal_rules']
        
        for rule_index, rule in enumerate(reversed(rules)):
            if rule['port_type'] is not None:
                if not self._check_port_type_match(port, rule['port_type']):
                    continue
            
            if self._match_pattern(signal_name, rule['source']):
                target_result = self._apply_pattern_substitution(signal_name, rule)
                if 'comments' in rule and rule['comments']:
                    target_result = self._restore_inline_comments(target_result, rule['comments'])
                
                if target_result.replace('/*', '').replace('*/', '').strip() in ['0', '1']:
                    clean_result = re.sub(r'/\*[^*]*(?:\*(?!/)[^*]*)*\*/', '', target_result).strip()
                    if clean_result in ['0', '1']:
                        literal_result = self._generate_width_literal(port, clean_result)
                        comment_match = re.search(r'/\*[^*]*(?:\*(?!/)[^*]*)*\*/', target_result)
                        if comment_match:
                            return literal_result + comment_match.group(0)
                        return literal_result
                
                self.logger.debug(f"Applied signal rule #{len(rules)-1-rule_index} to '{signal_name}' -> '{target_result}'")
                return target_result
        
        return signal_name
    
    def resolve_param_connection(self, param_name: str) -> Optional[str]:
        rules = self.rules['param_rules']
        
        for rule in reversed(rules):
            if self._match_param_pattern(param_name, rule['param_name']):
                return rule['param_value']
        
        return None
    
    def resolve_wire_generation(self, port: PortInfo, pattern: str = 'greedy') -> Tuple[str, Optional[str], Optional[str], bool]:
        port_name = port.name
        rules = self.rules['wire_rules']
        
        for rule_index, rule in enumerate(reversed(rules)):
            if self._match_pattern(port_name, rule['port_pattern']):
                wire_name = self._apply_pattern_substitution_for_wire(port_name, rule)
                
                if 'comments' in rule and rule['comments']:
                    wire_name = self._restore_inline_comments(wire_name, rule['comments'])
                
                width = rule.get('width')
                expression = rule.get('expression')
                
                return wire_name, width, expression, True
        
        if pattern == 'lazy':
            return "", None, None, False
        else:  # greedy
            return port_name, None, None, False
    
    def _extract_inline_comments(self, target_pattern: str) -> Tuple[str, List[str]]:
        comments = []
        comment_pattern = r'/\*([^*]*(?:\*(?!/)[^*]*)*)\*/'
        
        def replace_comment(match):
            comment_content = match.group(1)
            placeholder = f"__COMMENT_{len(comments)}__"
            comments.append(comment_content)
            return placeholder
        
        processed_pattern = re.sub(comment_pattern, replace_comment, target_pattern)
        return processed_pattern, comments
    
    def _restore_inline_comments(self, result: str, comments: List[str]) -> str:
        for i, comment in enumerate(comments):
            placeholder = f"__COMMENT_{i}__"
            result = result.replace(placeholder, f"/*{comment}*/")
        return result
    
    def _match_pattern(self, signal_name: str, pattern: str) -> bool:
        if '*' in pattern:
            regex_pattern = pattern.replace('*', '(.*)')
            return bool(re.match(f'^{regex_pattern}$', signal_name))
        else:
            return signal_name == pattern
    
    def _match_param_pattern(self, param_name: str, pattern: str) -> bool:
        return self._match_pattern(param_name, pattern)
    
    def _apply_pattern_substitution(self, signal_name: str, rule: Dict) -> str:
        return self._apply_pattern_substitution_core(signal_name, rule['source'], rule['target'])
    
    def _apply_pattern_substitution_for_wire(self, port_name: str, rule: Dict) -> str:
        return self._apply_pattern_substitution_core(port_name, rule['port_pattern'], rule['wire_pattern'])
    
    def _apply_pattern_substitution_core(self, signal_name: str, source_pattern: str, target_pattern: str) -> str:
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
                
                for group in groups:
                    result = result.replace('*', group, 1)
                
                return result
        
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
            self.logger.warning(f"Function call execution failed: '{function_call}', error: {e}")
            return groups[0] if groups else function_call
    
    def _check_port_type_match(self, port: PortInfo, required_type: str) -> bool:
        if not hasattr(port, 'direction'):
            return True
        
        port_direction = port.direction.lower()
        return port_direction == required_type.lower()
    
    def _generate_width_literal(self, port: PortInfo, value: str) -> str:
        if not hasattr(port, 'width') or not port.width:
            return f"1'b{value}"
        
        width = port.width
        
        if isinstance(width, int):
            if width <= 1:
                return f"1'b{value}"
            else:
                return f"{width}'b{value * width}"
        
        width_str = str(width).strip()
        
        if width_str.isdigit():
            width_num = int(width_str)
            if width_num <= 1:
                return f"1'b{value}"
            else:
                return f"{width_num}'b{value * width_num}"
        
        if any(char in width_str for char in ['+', '-', '*', '/', '(', ')']):
            return f"{{({width_str}){{1'b{value}}}}}"
        else:
            return f"{{{width_str}{{1'b{value}}}}}"
    
    def get_rules_summary(self) -> Dict[str, int]:
        return {
            'signal_rules': len(self.rules['signal_rules']),
            'param_rules': len(self.rules['param_rules']),
            'wire_rules': len(self.rules['wire_rules'])
        }