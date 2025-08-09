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
        self.logger.debug(f"Adding signal rule: source='{source_pattern}', target='{target_pattern}', port_type='{port_type}'")
        processed_target, comments = self._extract_inline_comments(target_pattern)
        self.logger.debug(f"Processed target pattern: '{processed_target}', extracted {len(comments)} comments")
        
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
        self.logger.info(f"Total signal rules: {len(self.rules['signal_rules'])}")
    
    def add_param_rule(self, param_name: str, param_value: str):
        self.logger.debug(f"Adding parameter rule: name='{param_name}', value='{param_value}'")
        rule = {
            'type': 'param',
            'param_name': param_name,
            'param_value': param_value,
            'priority': len(self.rules['param_rules'])
        }
        self.rules['param_rules'].append(rule)
        self.logger.debug(f"Added parameter rule #{rule['priority']}: {param_name} = {param_value}")
        self.logger.info(f"Total parameter rules: {len(self.rules['param_rules'])}")
    
    def add_wire_rule(self, port_pattern: str, wire_pattern: str,
                     width: Optional[str] = None, expression: Optional[str] = None):
        self.logger.debug(f"Adding wire rule: port_pattern='{port_pattern}', wire_pattern='{wire_pattern}', width='{width}', expression='{expression}'")
        processed_pattern, comments = self._extract_inline_comments(wire_pattern)
        self.logger.debug(f"Processed wire pattern: '{processed_pattern}', extracted {len(comments)} comments")
        
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
        self.logger.info(f"Total wire rules: {len(self.rules['wire_rules'])}")

    def reset(self):
        total_rules = sum(len(rules) for rules in self.rules.values())
        self.logger.info(f"Resetting all rules (total: {total_rules})")
        self.rules = {
            'signal_rules': [],
            'param_rules': [], 
            'wire_rules': []
        }
        self.logger.debug(f"Reset all rules (cleared {total_rules} rules)")
    

    def resolve_signal_connection(self, port: PortInfo) -> str:
        signal_name = port.name
        rules = self.rules['signal_rules']
        self.logger.debug(f"Resolving signal connection for port: '{signal_name}', port_type: {getattr(port, 'direction', 'unknown')}")
        self.logger.debug(f"Available signal rules: {len(rules)}")

        for rule_index, rule in enumerate(reversed(rules)):
            rule_num = len(rules) - 1 - rule_index
            self.logger.debug(f"Checking signal rule #{rule_num}: source='{rule['source']}', target='{rule['target']}', port_type='{rule['port_type']}'")

            if rule['port_type'] is not None:
                port_type_match = self._check_port_type_match(port, rule['port_type'])
                self.logger.debug(f"Port type check: required='{rule['port_type']}', port_direction='{getattr(port, 'direction', 'none')}', match={port_type_match}")
                if not self._check_port_type_match(port, rule['port_type']):
                    continue

            pattern_match = self._match_pattern(signal_name, rule['source'])
            self.logger.debug(f"Pattern match: signal='{signal_name}', pattern='{rule['source']}', match={pattern_match}")
                
            if pattern_match:
                self.logger.debug(f"Rule #{rule_num} matched, applying pattern substitution")
                pattern_result = self._apply_pattern_substitution( signal_name, rule['source'], rule['target'])
                self.logger.debug(f"Pattern substitution result: '{pattern_result}'")

                final_result = self._handle_literal_value_if_needed(pattern_result, port)
                self.logger.debug(f"After literal value handling: '{final_result}'")

                if rule.get('comments'):
                    self.logger.debug(f"Restoring {len(rule['comments'])} inline comments")
                    final_result = self._restore_inline_comments(final_result, rule['comments'])
                    self.logger.debug(f"After comment restoration: '{final_result}'")

                self.logger.debug(f"Applied signal rule #{len(rules)-1-rule_index} to '{signal_name}' -> '{final_result}'")
                self.logger.info(f"Signal connection resolved: '{signal_name}' -> '{final_result}'")
                return final_result

        return signal_name

    
    def resolve_param_connection(self, param_name: str) -> Optional[str]:
        rules = self.rules['param_rules']

        self.logger.debug(f"Resolving parameter connection for: '{param_name}'")
        self.logger.debug(f"Available parameter rules: {len(rules)}")
        
        for rule_index, rule in enumerate(reversed(rules)):
            rule_num = len(rules) - 1 - rule_index
            self.logger.debug(f"Checking parameter rule #{rule_num}: pattern='{rule['param_name']}', value='{rule['param_value']}'")
            if self._match_pattern(param_name, rule['param_name']):
                self.logger.debug(f"Parameter rule #{rule_num} matched")
                self.logger.info(f"Parameter connection resolved: '{param_name}' -> '{rule['param_value']}'")
                return rule['param_value']
            
        self.logger.debug(f"No parameter rule matched for '{param_name}'")
        return None
    
    def resolve_wire_generation(self, port: PortInfo, pattern: str = 'greedy') -> Tuple[str, Optional[str], Optional[str], bool]:
        port_name = port.name
        rules = self.rules['wire_rules']

        self.logger.debug(f"Resolving wire generation for port: '{port_name}', pattern: '{pattern}'")
        self.logger.debug(f"Available wire rules: {len(rules)}")

        for rule_index, rule in enumerate(reversed(rules)):
            rule_num = len(rules) - 1 - rule_index
            self.logger.debug(f"Checking wire rule #{rule_num}: pattern='{rule['port_pattern']}', wire='{rule['wire_pattern']}'")
            
            if self._match_pattern(port_name, rule['port_pattern']):
                self.logger.debug(f"Wire rule #{rule_num} matched for port '{port_name}'")

                pattern_result = self._apply_pattern_substitution(port_name, rule['port_pattern'], rule['wire_pattern'])
                self.logger.debug(f"Wire pattern '{rule['wire_pattern']}' → '{pattern_result}'")

                final_result = self._handle_literal_value_if_needed(pattern_result, port)
                self.logger.debug(f"After literal value handling: '{final_result}'")

                if rule.get('comments'):
                    self.logger.debug(f"Restoring {len(rule['comments'])} inline comments")
                    final_result = self._restore_inline_comments(final_result, rule['comments'])
                    self.logger.debug(f"After comment restoration: '{final_result}'")
                
                width = rule.get('width')

                expression = rule.get('expression')
                self.logger.debug(f"Rule width: '{width}', expression: '{expression}'")

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
        stripped_value = value.strip()
        self.logger.debug(f"Checking if value needs literal conversion: '{stripped_value}'")

        if value.strip() in ['0', '1']:
            self.logger.debug(f"Value '{stripped_value}' is a literal, generating width literal")
            result = self._generate_width_literal(port, stripped_value)
            self.logger.debug(f"Width literal generated: '{result}'")
            return result
        
        self.logger.debug(f"Value '{stripped_value}' is not a literal, returning as-is")    
        
        return value
    

    def _apply_pattern_substitution(self, input_name: str, source_pattern: str, target_pattern: str) -> str:
        self.logger.debug(f"Applying pattern substitution: input='{input_name}', source='{source_pattern}', target='{target_pattern}'")
        if '*' not in source_pattern:
            self.logger.debug("Source pattern has no wildcards, returning target pattern as-is")
            return target_pattern

        escaped_pattern = re.escape(source_pattern).replace('\\*', '(.*)')
        self.logger.debug(f"Escaped regex pattern: '{escaped_pattern}'")

        match = re.match(f'^{escaped_pattern}$', input_name)
        
        if not match:
            self.logger.debug(f"Pattern '{escaped_pattern}' did not match input '{input_name}', returning target pattern")
            return target_pattern
            
        groups = match.groups()
        self.logger.debug(f"Pattern matched, captured groups: {groups}")
        
        result = target_pattern

        function_pattern = r'\$\{([^}]+)\}'
        function_matches = re.findall(function_pattern, result)
        if function_matches:
            self.logger.debug(f"Found {len(function_matches)} function calls: {function_matches}")
            result = re.sub(function_pattern, 
                           lambda m: self._execute_function_call(m.group(1), groups), 
                           result)
            self.logger.debug(f"After function processing: '{result}'")


#        function_pattern = r'\$\{([^}]+)\}'
#        result = re.sub(function_pattern, 
#                       lambda m: self._execute_function_call(m.group(1), groups), 
#                       result)
        
        for i, group in enumerate(groups):
            old_result = result
            result = result.replace('*', group, 1)
            self.logger.debug(f"Replaced wildcard #{i} with '{group}': '{old_result}' -> '{result}'")

        self.logger.debug(f"Pattern substitution complete: '{result}'")
        return result
    
    def _extract_inline_comments(self, target_pattern: str) -> Tuple[str, List[str]]:
        self.logger.debug(f"Extracting inline comments from: '{target_pattern}'")

        comments = []
        comment_pattern = r'/\*([^*]*(?:\*(?!/)[^*]*)*)\*/'
        
        def replace_comment(match):
            comment_content = match.group(1)
            placeholder = f"__COMMENT_{len(comments)}__"
            comments.append(comment_content)
            self.logger.debug(f"Extracted comment #{len(comments)-1}: '{comment_content}' -> placeholder '{placeholder}'")
            return placeholder
        
        processed_pattern = re.sub(comment_pattern, replace_comment, target_pattern)

        self.logger.debug(f"Comment extraction complete: extracted {len(comments)} comments, result: '{processed_pattern}'")
        return processed_pattern, comments
    
    def _restore_inline_comments(self, result: str, comments: List[str]) -> str:
        self.logger.debug(f"Restoring {len(comments)} inline comments to: '{result}'")

        for i, comment in enumerate(comments):
            placeholder = f"__COMMENT_{i}__"
            old_result = result
            result = result.replace(placeholder, f"/*{comment}*/")
            self.logger.debug(f"Restored comment #{i}: '{comment}', '{old_result}' -> '{result}'")
        
        self.logger.debug(f"Comment restoration complete: '{result}'")
        return result
    
    def _match_pattern(self, signal_name: str, pattern: str) -> bool:
        self.logger.debug(f"Matching pattern: signal='{signal_name}', pattern='{pattern}'")
        if '*' in pattern:
            escaped_pattern = re.escape(pattern).replace('\\*', '(.*)')
            self.logger.debug(f"Using wildcard matching with escaped pattern: '{escaped_pattern}'")
            match_result = bool(re.match(f'^{escaped_pattern}$', signal_name))
        else:
            self.logger.debug("Using exact string matching")
            match_result = signal_name == pattern

        self.logger.debug(f"Pattern match result: {match_result}")
        return match_result
    
    def _execute_function_call(self, function_call: str, groups: tuple) -> str:
        self.logger.debug(f"Executing function call: '{function_call}' with groups: {groups}")
        try:
            processed_call = function_call
            for i, group in enumerate(groups):
                old_call = processed_call
                processed_call = processed_call.replace(f'*{i}', f'group_{i}')
                if old_call != processed_call:
                    self.logger.debug(f"Replaced '*{i}' with 'group_{i}': '{old_call}' -> '{processed_call}'")
            
            old_call = processed_call
            processed_call = processed_call.replace('*', 'group_0')
            if old_call != processed_call:
                self.logger.debug(f"Replaced '*' with 'group_0': '{old_call}' -> '{processed_call}'")
            
            local_vars = {}
            for i, group in enumerate(groups):
                local_vars[f'group_{i}'] = group
            
            local_vars.update(self.safe_functions)
            local_vars['str'] = str
            
            self.logger.debug(f"Evaluating processed call: '{processed_call}'")
            result = eval(processed_call, {"__builtins__": {}}, local_vars)
            result_str = str(result)

            self.logger.debug(f"Function call executed successfully: '{function_call}' -> '{result_str}'")
            return result_str
        
        except Exception as e:
            fallback = groups[0] if groups else function_call
            self.logger.warning(f"Function call execution failed: '{function_call}', error: {e}, using fallback: '{fallback}'")
            return fallback
    
    def _check_port_type_match(self, port: PortInfo, required_type: str) -> bool:
        self.logger.debug(f"Checking port type match: required='{required_type}'")

        if not hasattr(port, 'direction'):
            self.logger.debug("Port has no direction attribute, skipping type check (allowing match)")
            return True
        
        port_direction = port.direction.lower()
        required_type_lower = required_type.lower()
        match_result = port_direction == required_type_lower
        
        self.logger.debug(f"Port type check: port_direction='{port_direction}', required='{required_type_lower}', match={match_result}")
        return match_result
    
    def _generate_width_literal(self, port: PortInfo, value: str) -> str:
        self.logger.debug(f"Generating width literal for value '{value}', port: '{port.name}'")

        if not hasattr(port, 'width') or not port.width:
            result = f"1'b{value}"
            self.logger.debug(f"Port has no width, using default: '{result}'")
            return result
        
        width = port.width
        self.logger.debug(f"Port width: {width} (type: {type(width)})")
        
        if isinstance(width, int):
            self.logger.debug(f"Width is integer: {width}")
            if width <= 1:
                result = f"1'b{value}"
                self.logger.debug(f"Width <= 1, result: '{result}'")
                return result
            else:
                result = f"{width}'b{value * width}"
                self.logger.debug(f"Width > 1, result: '{result}'")
                return result
        
        width_str = str(width).strip()
        self.logger.debug(f"Width as string: '{width_str}'")
        
        if width_str.isdigit():
            width_num = int(width_str)
            self.logger.debug(f"Width string is digit: {width_num}")
            if width_num <= 1:
                result = f"1'b{value}"
                self.logger.debug(f"Width <= 1, result: '{result}'")
                return result
            else:
                result = f"{width_num}'b{value * width_num}"
                self.logger.debug(f"Width > 1, result: '{result}'")
                return result
        
        if any(char in width_str for char in ['+', '-', '*', '/', '(', ')']):
            result = f"{{({width_str}){{1'b{value}}}}}"
            self.logger.debug(f"Expression width format: '{result}'")
            return result
        else:
            result = f"{{{width_str}{{1'b{value}}}}}"
            self.logger.debug(f"Parameter width format: '{result}'")
            return result
    
    def get_rules_summary(self) -> Dict[str, int]:
        return {
            'signal_rules': len(self.rules['signal_rules']),
            'param_rules': len(self.rules['param_rules']),
            'wire_rules': len(self.rules['wire_rules'])
        }