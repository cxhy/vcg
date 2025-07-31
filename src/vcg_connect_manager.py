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
from typing import List, Dict, Optional
from VerilogAst import PortInfo
from vcg_logger import get_vcg_logger

class VCGConnectManager:
    
    def __init__(self):
        self.global_rules = {
            'signal_rules': [],
            'param_rules': []
        }
        self.logger = get_vcg_logger('ConnectManager') 
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
            'source': source_pattern,
            'target': processed_target,
            'comments': comments,
            'port_type': port_type.lower() if port_type else None
        }

        rule_desc = f"'{source_pattern}' -> '{target_pattern}'"
        if port_type:
            rule_desc += f" (type: {port_type})"
        if comments:
            rule_desc += f" (with {len(comments)} comments)"

        self.global_rules['signal_rules'].append(rule)
        self.logger.debug(f"Added signal rule #{len(self.global_rules['signal_rules']) - 1}: {rule_desc}")

    def _extract_inline_comments(self, target_pattern: str) -> tuple:
        import re
        
        comments = []
        comment_pattern = r'/\*([^*]*(?:\*(?!/)[^*]*)*)\*/'
        
        def replace_comment(match):
            comment_content = match.group(1)
            placeholder = f"__COMMENT_{len(comments)}__"
            comments.append(comment_content)
            return placeholder
        
        processed_pattern = re.sub(comment_pattern, replace_comment, target_pattern)

        if comments:
            self.logger.debug(f"Extracted {len(comments)} inline comments from pattern")
        return processed_pattern, comments
    
    def _restore_inline_comments(self, result: str, comments: list) -> str:
        for i, comment in enumerate(comments):
            placeholder = f"__COMMENT_{i}__"
            result = result.replace(placeholder, f"/*{comment}*/")

        if comments:
            self.logger.debug(f"Restored {len(comments)} inline comments to result")

        return result
    
    def add_param_rule(self, param_name: str, param_value: str):
        rule = {
            'param_name': param_name,
            'param_value': param_value
        }
        self.logger.debug(f"Added parameter rule #{len(self.global_rules['param_rules']) - 1}: {param_name} = {param_value}")
        self.global_rules['param_rules'].append(rule)
    
    def reset(self):
        self.global_rules = {
            'signal_rules': [],
            'param_rules': []
        }
        self.logger.debug(f"Reset connection rules (cleared {len(self.global_rules['signal_rules'])} signal rules, {len(self.global_rules['param_rules'])} parameter rules)")
    
    def resolve_signal_connection(self, port: PortInfo) -> str:
        signal_name = port.name
        rules = self.global_rules['signal_rules']

        self.logger.debug(f"Resolving signal connection for port '{signal_name}' (type: {getattr(port, 'direction', 'unknown')})")

        #for rule in reversed(rules):
        for rule_index, rule in enumerate(reversed(rules)):
            if rule['port_type'] is not None:
                if not self._check_port_type_match(port, rule['port_type']):
                    self.logger.debug(f"Rule #{len(rules)-1-rule_index} skipped: port type mismatch (need {rule['port_type']}, got {getattr(port, 'direction', 'unknown')})")
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
                
                
                self.logger.debug(f"Applied rule #{len(rules)-1-rule_index} to '{signal_name}' -> '{target_result}'")
                return target_result

        self.logger.debug(f"No rules matched for '{signal_name}', using default signal name")
        return signal_name
    
    def _check_port_type_match(self, port: PortInfo, required_type: str) -> bool:
        if not hasattr(port, 'direction'):
            self.logger.debug(f"Port has no direction attribute, allowing type match")
            return True 
            
        port_direction = port.direction.lower()
        required_type = required_type.lower()
        
        self.logger.debug(f"Port type check: '{port_direction}' == '{required_type}' -> {port_direction == required_type}")
        return port_direction == required_type
    
    def _generate_width_literal(self, port: PortInfo, value: str) -> str:
        if not hasattr(port, 'width') or not port.width:
            self.logger.debug(f"Generated width literal for port without width: 1'b{value}")
            return f"1'b{value}"
            
        width = port.width
        
        if isinstance(width, int):
            if width <= 1:
                return f"1'b{value}"
            else:
                return f"{width}'b{value}"
        
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
        
    
    def resolve_param_connection(self, param_name: str) -> Optional[str]:
        rules = self.global_rules['param_rules']

        self.logger.debug(f"Resolving parameter connection for '{param_name}'")
        
        for rule in reversed(rules):
            if self._match_param_pattern(param_name, rule['param_name']):
                return rule['param_value']

        self.logger.debug(f"No parameter rules matched for '{param_name}'")
        return None
    
    def _match_pattern(self, signal_name: str, pattern: str) -> bool:
        if '*' in pattern:
            regex_pattern = pattern.replace('*', '(.*)')
            self.logger.debug(f"Pattern match: '{signal_name}' against '{pattern}' -> {bool(re.match(f'^{regex_pattern}$', signal_name))}")
            return bool(re.match(f'^{regex_pattern}$', signal_name))
        else:
            self.logger.debug(f"Exact match: '{signal_name}' == '{pattern}' -> {signal_name == pattern}")
            return signal_name == pattern
    
    def _match_param_pattern(self, param_name: str, pattern: str) -> bool:
        if '*' in pattern:
            regex_pattern = pattern.replace('*', '(.*)')
            self.logger.debug(f"Parameter pattern match: '{param_name}' against '{pattern}' -> {bool(re.match(f'^{regex_pattern}$', param_name))}")
            return bool(re.match(f'^{regex_pattern}$', param_name))
        else:
            self.logger.debug(f"Parameter exact match: '{param_name}' == '{pattern}' -> {param_name == pattern}")
            return param_name == pattern

    def _apply_pattern_substitution(self, signal_name: str, rule: Dict) -> str:
        source_pattern = rule['source']
        target_pattern = rule['target']

        if '*' in source_pattern:
            regex_pattern = source_pattern.replace('*', '(.*)')
            match = re.match(f'^{regex_pattern}$', signal_name)
            if match:
                result = target_pattern
                groups = match.groups()

                self.logger.debug(f"Pattern substitution groups: {groups}")

                function_pattern = r'\$\{([^}]+)\}'

                def replace_function_call(match_obj):
                    function_call = match_obj.group(1)
                    self.logger.debug(f"Function call '{function_call}' -> '{self._execute_function_call(function_call, groups)}'")
                    return self._execute_function_call(function_call, groups)

                result = re.sub(function_pattern, replace_function_call, result)

                for group in groups:
                    result = result.replace('*', group, 1)
                
                self.logger.debug(f"Pattern substitution result: '{signal_name}' -> '{result}'")

                return result

        return target_pattern
    
    def _execute_function_call(self, function_call: str, groups: tuple) -> str:
        try:
            self.logger.debug(f"Executing function call: {function_call} with groups: {groups}")

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
            self.logger.debug(f"Function call executed successfully: '{function_call}' -> '{str(result)}'")

            return str(result)
        

        except Exception as e:
            fallback_result = groups[0] if groups else function_call
            self.logger.warning(f"Function call execution failed: '{function_call}', error: {e}, using fallback: '{fallback_result}'")
            return groups[0] if groups else function_call
        
    def get_rules_summary(self) -> Dict[str, int]:
        summary = {
            'signal_rules': len(self.global_rules['signal_rules']),
            'param_rules': len(self.global_rules['param_rules'])
        }
        
        self.logger.debug(f"Rules summary: {summary['signal_rules']} signal rules, {summary['param_rules']} parameter rules")
        return summary
