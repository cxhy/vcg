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
                pattern_result = self._apply_pattern_substitution(
                    signal_name, rule['source'], rule['target']
                )

                final_result = self._handle_literal_value_if_needed(pattern_result, port)

                if rule.get('comments'):
                    final_result = self._restore_inline_comments(final_result, rule['comments'])

                self.logger.debug(f"Applied signal rule #{len(rules)-1-rule_index} to '{signal_name}' -> '{final_result}'")
                return final_result

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
                self.logger.debug(f"Wire rule #{len(rules)-1-rule_index} matched for port '{port_name}'")

                pattern_result = self._apply_pattern_substitution(port_name, rule['port_pattern'], rule['wire_pattern'])
                self.logger.debug(f"Wire pattern '{rule['wire_pattern']}' → '{pattern_result}'")

                final_result = self._handle_literal_value_if_needed(pattern_result, port)

                if rule.get('comments'):
                    final_result = self._restore_inline_comments(final_result, rule['comments'])
                
                width = rule.get('width')

                expression = rule.get('expression')

                if expression:
                    original_expression = expression
                    expression = self._apply_pattern_substitution(port_name, rule['port_pattern'], expression)
                    self.logger.debug(f"Expression pattern '{original_expression}' → '{expression}'")
                
                self.logger.info(f"Generated wire: name='{final_result}', width='{width}', expression='{expression}'")
                return final_result, width, expression, True
        
        if pattern == 'lazy':
            self.logger.debug(f"No wire rule matched for '{port_name}' in lazy mode")
            return "", None, None, False
        else:  # greedy
            self.logger.debug(f"No wire rule matched for '{port_name}', using port name as wire name")
            return port_name, None, None, False
        

    def _handle_literal_value_if_needed(self, value: str, port: PortInfo) -> str:
        if value.strip() in ['0', '1']:
            return self._generate_width_literal(port, value.strip())
        
        return value
    

    def _apply_pattern_substitution(self, input_name: str, source_pattern: str, target_pattern: str) -> str:
        if '*' not in source_pattern:
            return target_pattern

        escaped_pattern = re.escape(source_pattern).replace('\\*', '(.*)')
        match = re.match(f'^{escaped_pattern}$', input_name)
        
        if not match:
            return target_pattern
            
        result = target_pattern
        groups = match.groups()
        
        function_pattern = r'\$\{([^}]+)\}'
        result = re.sub(function_pattern, 
                       lambda m: self._execute_function_call(m.group(1), groups), 
                       result)
        
        for group in groups:
            result = result.replace('*', group, 1)
        
        return result
    
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
        """修复后的模式匹配方法 - 正确处理特殊字符"""
        if '*' in pattern:
            # 先转义所有正则表达式特殊字符，然后将\*替换为通配符组
            escaped_pattern = re.escape(pattern).replace('\\*', '(.*)')
            return bool(re.match(f'^{escaped_pattern}$', signal_name))
        else:
            return signal_name == pattern


    #def _match_pattern(self, signal_name: str, pattern: str) -> bool:
    #    if '*' in pattern:
    #        regex_pattern = pattern.replace('*', '(.*)')
    #        return bool(re.match(f'^{regex_pattern}$', signal_name))
    #    else:
    #        return signal_name == pattern
    
    def _match_param_pattern(self, param_name: str, pattern: str) -> bool:
        return self._match_pattern(param_name, pattern)
    
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