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
import ast
import re
from dataclasses import dataclass
from typing import Optional

from .VerilogAst import PortInfo
from .vcg_logger import get_vcg_logger

INLINE_BINARY_THRESHOLD = 8
FUNCTION_PATTERN = re.compile(r'\$\{([^}]+)\}')
FUNCTION_CALL_PATTERN = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\((.*)\)$')
GROUP_REF_PATTERN = re.compile(r'^\*(\d*)$')


@dataclass(frozen=True)
class SignalRule:
    source: str
    target: str
    comments: tuple[str, ...]
    port_direction: Optional[str]
    priority: int


@dataclass(frozen=True)
class ParamRule:
    pattern: str
    value: str
    priority: int


@dataclass(frozen=True)
class WireRule:
    port_pattern: str
    wire_pattern: str
    comments: tuple[str, ...]
    width: Optional[str]
    expression: Optional[str]
    priority: int


class VCGRuleManager:

    def __init__(self) -> None:
        self.rules = self._empty_rules()
        self.logger = get_vcg_logger('RuleManager')

    @staticmethod
    def _empty_rules() -> dict[str, list]:
        return {
            'signal_rules': [],
            'param_rules': [],
            'wire_rules': [],
        }

    def add_signal_rule(
        self,
        source_pattern: str,
        target_pattern: str,
        port_direction: Optional[str] = None,
    ) -> None:
        processed_target, comments = self._extract_inline_comments(target_pattern)
        rule = SignalRule(
            source=source_pattern,
            target=processed_target,
            comments=tuple(comments),
            port_direction=port_direction.lower() if port_direction else None,
            priority=len(self.rules['signal_rules']),
        )
        self.rules['signal_rules'].append(rule)
        self.logger.debug(
            "Added signal rule #%s: %r -> %r",
            rule.priority, source_pattern, target_pattern
        )

    def add_param_rule(self, param_name: str, param_value: str) -> None:
        rule = ParamRule(
            pattern=param_name,
            value=param_value,
            priority=len(self.rules['param_rules']),
        )
        self.rules['param_rules'].append(rule)
        self.logger.debug(
            "Added parameter rule #%s: %s = %s",
            rule.priority, param_name, param_value
        )

    def add_wire_rule(
        self,
        port_pattern: str,
        wire_pattern: str,
        width: Optional[str] = None,
        expression: Optional[str] = None,
    ) -> None:
        processed_pattern, comments = self._extract_inline_comments(wire_pattern)
        rule = WireRule(
            port_pattern=port_pattern,
            wire_pattern=processed_pattern,
            comments=tuple(comments),
            width=width,
            expression=expression,
            priority=len(self.rules['wire_rules']),
        )
        self.rules['wire_rules'].append(rule)
        self.logger.debug(
            "Added wire rule #%s: %r -> %r",
            rule.priority, port_pattern, wire_pattern
        )

    def reset(self) -> None:
        total_rules = sum(len(rules) for rules in self.rules.values())
        self.rules = self._empty_rules()
        self.logger.debug("Reset all rules (cleared %s rules)", total_rules)

    def resolve_signal_connection(self, port: PortInfo) -> str:
        signal_name = port.name
        for rule in reversed(self.rules['signal_rules']):
            if not self._signal_rule_matches(rule, port):
                continue

            result = self._apply_pattern_substitution(
                signal_name, rule.source, rule.target
            )
            result = self._handle_literal_value_if_needed(result, port)
            result = self._restore_inline_comments(result, rule.comments)
            self.logger.debug(
                "Signal connection resolved by rule #%s: %r -> %r",
                rule.priority, signal_name, result
            )
            return result

        return signal_name

    def resolve_param_connection(self, param_name: str) -> Optional[str]:
        for rule in reversed(self.rules['param_rules']):
            if self._match_pattern(param_name, rule.pattern):
                self.logger.debug(
                    "Parameter connection resolved by rule #%s: %r -> %r",
                    rule.priority, param_name, rule.value
                )
                return rule.value
        return None

    def resolve_wire_generation(
        self,
        port: PortInfo,
        pattern: str = 'greedy',
    ) -> tuple[str, Optional[str], Optional[str], bool]:
        port_name = port.name
        if not self._should_generate_wire_for_port(port):
            return "", None, None, False

        for rule in reversed(self.rules['wire_rules']):
            if not self._match_pattern(port_name, rule.port_pattern):
                continue

            wire_name = self._apply_pattern_substitution(
                port_name, rule.port_pattern, rule.wire_pattern
            )
            wire_name = self._handle_literal_value_if_needed(wire_name, port)
            wire_name = self._restore_inline_comments(wire_name, rule.comments)
            expression = self._resolve_wire_expression(rule, port_name)
            self.logger.debug(
                "Wire generation resolved by rule #%s: name=%r width=%r expr=%r",
                rule.priority, wire_name, rule.width, expression
            )
            return wire_name, rule.width, expression, True

        if pattern == 'lazy':
            return "", None, None, False
        return port_name, None, None, False

    def get_rules_summary(self) -> dict[str, int]:
        return {
            'signal_rules': len(self.rules['signal_rules']),
            'param_rules': len(self.rules['param_rules']),
            'wire_rules': len(self.rules['wire_rules']),
        }

    def _signal_rule_matches(self, rule: SignalRule, port: PortInfo) -> bool:
        if rule.port_direction and not self._check_port_direction_match(
            port, rule.port_direction
        ):
            return False
        return self._match_pattern(port.name, rule.source)

    def _check_port_direction_match(
        self,
        port: PortInfo,
        required_direction: str,
    ) -> bool:
        if port.direction is None:
            return True
        return port.direction.lower() == required_direction

    def _resolve_wire_expression(
        self,
        rule: WireRule,
        port_name: str,
    ) -> Optional[str]:
        if rule.expression is None:
            return None
        return self._apply_pattern_substitution(
            port_name, rule.port_pattern, rule.expression
        )

    def _handle_literal_value_if_needed(self, value: str, port: PortInfo) -> str:
        stripped_value = value.strip()
        if stripped_value in {'0', '1'}:
            return self._generate_width_literal(port, stripped_value)
        return value

    def _apply_pattern_substitution(
        self,
        input_name: str,
        source_pattern: str,
        target_pattern: str,
    ) -> str:
        if '*' not in source_pattern:
            return target_pattern

        groups = self._match_groups(input_name, source_pattern)
        if groups is None:
            return target_pattern

        result = FUNCTION_PATTERN.sub(
            lambda match: self._execute_function_call(match.group(1), groups),
            target_pattern,
        )
        for group in groups:
            result = result.replace('*', group, 1)
        return result

    def _match_pattern(self, signal_name: str, pattern: str) -> bool:
        return self._match_groups(signal_name, pattern) is not None

    def _match_groups(
        self,
        input_name: str,
        source_pattern: str,
    ) -> Optional[tuple[str, ...]]:
        if '*' not in source_pattern:
            return () if input_name == source_pattern else None

        escaped_pattern = re.escape(source_pattern).replace(r'\*', '(.*)')
        match = re.match(f'^{escaped_pattern}$', input_name)
        return match.groups() if match else None

    def _execute_function_call(
        self,
        function_call: str,
        groups: tuple[str, ...],
    ) -> str:
        try:
            return self._evaluate_function_expression(function_call, groups)
        except (IndexError, TypeError, ValueError) as error:
            fallback = groups[0] if groups else function_call
            self.logger.warning(
                "Function expression rejected: %r (%s); using fallback %r",
                function_call, error, fallback
            )
            return fallback

    def _evaluate_function_expression(
        self,
        expression: str,
        groups: tuple[str, ...],
    ) -> str:
        expression = expression.strip()
        direct_ref = self._try_resolve_group_ref(expression, groups)
        if direct_ref is not None:
            return direct_ref

        match = FUNCTION_CALL_PATTERN.match(expression)
        if not match:
            raise ValueError(f"invalid function expression: {expression}")

        function_name, args_text = match.groups()
        args = [
            self._resolve_function_arg(arg, groups)
            for arg in self._split_function_args(args_text)
        ]
        return self._apply_safe_function(function_name, args)

    def _split_function_args(self, args_text: str) -> list[str]:
        args: list[str] = []
        current: list[str] = []
        quote: Optional[str] = None
        escaped = False

        for char in args_text:
            if escaped:
                current.append(char)
                escaped = False
            elif char == '\\' and quote:
                current.append(char)
                escaped = True
            elif quote:
                current.append(char)
                if char == quote:
                    quote = None
            elif char in {'"', "'"}:
                current.append(char)
                quote = char
            elif char == ',':
                args.append(''.join(current).strip())
                current = []
            else:
                current.append(char)

        if quote:
            raise ValueError("unterminated quoted argument")
        args.append(''.join(current).strip())
        return args if args != [''] else []

    def _resolve_function_arg(
        self,
        arg: str,
        groups: tuple[str, ...],
    ) -> str:
        direct_ref = self._try_resolve_group_ref(arg, groups)
        if direct_ref is not None:
            return direct_ref

        if self._is_quoted_string(arg):
            return self._parse_quoted_string(arg)

        if '.' in arg or '(' in arg or ')' in arg:
            raise ValueError(f"unsupported argument expression: {arg}")
        return arg

    def _try_resolve_group_ref(
        self,
        token: str,
        groups: tuple[str, ...],
    ) -> Optional[str]:
        match = GROUP_REF_PATTERN.match(token.strip())
        if not match:
            return None

        index_text = match.group(1)
        index = int(index_text) if index_text else 0
        return groups[index]

    @staticmethod
    def _is_quoted_string(value: str) -> bool:
        return (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {'"', "'"}
        )

    @staticmethod
    def _parse_quoted_string(value: str) -> str:
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError) as error:
            raise ValueError(f"invalid string literal: {value}") from error
        if not isinstance(parsed, str):
            raise ValueError(f"argument is not a string literal: {value}")
        return parsed

    def _apply_safe_function(self, name: str, args: list[str]) -> str:
        if name == 'upper' and len(args) == 1:
            return args[0].upper()
        if name == 'lower' and len(args) == 1:
            return args[0].lower()
        if name == 'title' and len(args) == 1:
            return args[0].title()
        if name == 'capitalize' and len(args) == 1:
            return args[0].capitalize()
        if name == 'strip' and len(args) == 1:
            return args[0].strip()
        if name == 'lstrip' and len(args) == 1:
            return args[0].lstrip()
        if name == 'rstrip' and len(args) == 1:
            return args[0].rstrip()
        if name == 'replace' and len(args) == 3:
            return args[0].replace(args[1], args[2])
        raise ValueError(f"unsupported function or arity: {name}/{len(args)}")

    def _extract_inline_comments(self, target_pattern: str) -> tuple[str, list[str]]:
        comments: list[str] = []
        comment_pattern = r'/\*([^*]*(?:\*(?!/)[^*]*)*)\*/'

        def replace_comment(match: re.Match[str]) -> str:
            placeholder = f"__COMMENT_{len(comments)}__"
            comments.append(match.group(1))
            return placeholder

        processed_pattern = re.sub(comment_pattern, replace_comment, target_pattern)
        return processed_pattern, comments

    def _restore_inline_comments(
        self,
        result: str,
        comments: tuple[str, ...],
    ) -> str:
        for index, comment in enumerate(comments):
            result = result.replace(f"__COMMENT_{index}__", f"/*{comment}*/")
        return result

    def _generate_width_literal(self, port: PortInfo, value: str) -> str:
        width = port.width
        if not width or width == 1:
            return f"1'b{value}"

        width_int = self._width_as_int(width)
        if width_int and width_int <= INLINE_BINARY_THRESHOLD:
            return f"{width_int}'b{value * width_int}"

        if width_int:
            return f"{{{width_int}{{1'b{value}}}}}"

        width_expr = str(width)
        if any(op in width_expr for op in ['+', '-', '*', '/']):
            return f"{{({width_expr}){{1'b{value}}}}}"
        return f"{{{width_expr}{{1'b{value}}}}}"

    @staticmethod
    def _width_as_int(width) -> Optional[int]:
        if isinstance(width, int):
            return width
        if isinstance(width, str) and width.isdigit():
            return int(width)
        return None

    def _should_generate_wire_for_port(self, port: PortInfo) -> bool:
        return self._port_type_value(port).lower() != 'interface'

    @staticmethod
    def _port_type_value(port: PortInfo) -> str:
        port_type = getattr(port, 'port_type', '')
        return str(getattr(port_type, 'value', port_type))
