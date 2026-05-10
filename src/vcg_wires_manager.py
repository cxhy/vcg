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

from .VerilogParser import VerilogParser
from .VerilogAst import PortInfo
from .vcg_rule_manager import VCGRuleManager
from .vcg_exceptions import VCGRuntimeError, VCGSyntaxError, VCGFileError, VCGParseError
from .vcg_logger import get_vcg_logger


DEFAULT_NAME_COLUMN = 15


class WiresManager:

    def __init__(self, rule_manager: VCGRuleManager, macros=None):
        self.rule_manager = rule_manager
        self.macros = macros
        self.logger = get_vcg_logger('WiresManager')
        self._BASE_SPACING = DEFAULT_NAME_COLUMN
        self.parser = VerilogParser(macros=self.macros, debug=False)

    def generate_wires_def(
        self,
        file_path: str,
        module_name: str,
        port_direction: str | None = None,
        pattern: str = 'greedy',
    ) -> str:
        try:
            self._validate_pattern(pattern)

            self.logger.debug(f"Generating wire definitions from {file_path} for module '{module_name}' "
                            f"(direction: {port_direction or 'all'}, pattern: {pattern})")

            ast = self._parse_verilog_file(file_path)

            ports = self._get_ports_by_direction(ast, port_direction)
            self.logger.debug(f"Found {len(ports)} ports to process")

            wire_declarations = self._generate_wire_declarations(ports, pattern)
            skipped_count = len(ports) - len(wire_declarations)

            self.logger.info(
                f"Wire generation completed: {len(wire_declarations)} wires generated, "
                f"{skipped_count} ports skipped"
            )
            return '\n'.join(wire_declarations)

        except (VCGFileError, VCGParseError, VCGSyntaxError, VCGRuntimeError, ValueError):
            raise
        except Exception as e:
            self.logger.error(f"Wire generation failed: {e}")
            raise VCGRuntimeError(f"Generate Wire Error: {e}") from e

    def _parse_verilog_file(self, file_path: str):
        self.logger.debug(f"Parsing Verilog file: {file_path}")
        return self.parser.parse_file(file_path)

    def _get_ports_by_direction(self, ast, port_direction: str | None) -> list[PortInfo]:
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

    def _validate_pattern(self, pattern: str) -> None:
        if pattern not in ['lazy', 'greedy']:
            raise ValueError(f"Invalid pattern: {pattern}. Must be 'lazy' or 'greedy'")

    def _generate_wire_declarations(self, ports: list[PortInfo], pattern: str) -> list[str]:
        wire_declarations = []

        for port in ports:
            wire_decl = self._generate_single_wire(port, pattern)
            if wire_decl.strip():
                wire_declarations.append(wire_decl)
                self.logger.debug(f"Generated wire for port '{port.name}': {wire_decl.strip()}")
            else:
                self.logger.debug(f"Skipped port '{port.name}' (no wire generated)")

        return wire_declarations

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
            wire_name = port_name
            self.logger.debug(f"Port '{port_name}' -> no rule matched, using default wire name in greedy mode")

        return self._format_wire_declaration(wire_name, width, expression, port)

    def _format_wire_declaration(
        self,
        wire_name: str,
        width,
        expression: str | None,
        port: PortInfo,
    ) -> str:
        effective_width = self._resolve_effective_width(width, port)
        width_text = self._format_wire_width(effective_width)
        return self._render_wire_declaration(wire_name, width_text, expression)

    def _resolve_effective_width(self, rule_width, port: PortInfo):
        if rule_width is not None and str(rule_width).strip():
            return rule_width
        return getattr(port, "width", None)

    def _render_wire_declaration(
        self,
        wire_name: str,
        width_text: str,
        expression: str | None,
    ) -> str:
        prefix = f"wire {width_text}" if width_text else "wire"
        spacing = self._pad_prefix(prefix)

        if expression:
            return f"{prefix}{spacing}{wire_name} = {expression};"
        return f"{prefix}{spacing}{wire_name};"

    def _pad_prefix(self, prefix: str) -> str:
        if len(prefix) >= self._BASE_SPACING:
            return " "
        return " " * (self._BASE_SPACING - len(prefix))

    def _format_wire_width(self, width_input) -> str:
        if not width_input:
            return ""

        if isinstance(width_input, int):
            return self._format_integer_width(width_input)

        width_text = str(width_input).strip()
        if not width_text:
            return ""

        if self._is_multi_dimensional(width_text) or self._is_range_text(width_text):
            return width_text

        if width_text.isdigit():
            return self._format_integer_width(int(width_text))

        if self._is_expression_width(width_text):
            return f"[({width_text})-1:0]"

        return f"[{width_text}-1:0]"

    def _format_integer_width(self, width: int) -> str:
        return "" if width <= 1 else f"[{width - 1}:0]"

    def _is_range_text(self, width_text: str) -> bool:
        return bool(re.fullmatch(r"\[[^\[\]]+\]", width_text))

    def _is_multi_dimensional(self, width_text: str) -> bool:
        if not re.fullmatch(r"\s*(\[[^\[\]]+\]\s*){2,}", width_text):
            return False

        self.logger.debug(f"Multi-dimensional array detected: {width_text}")
        return True

    def _is_expression_width(self, width_text: str) -> bool:
        return any(op in width_text for op in ['+', '-', '*', '/', '(', ')'])

    def set_base_spacing(self, spacing: int):
        self._BASE_SPACING = spacing
        self.logger.debug(f"Set base spacing to {spacing}")

    def get_base_spacing(self) -> int:
        return self._BASE_SPACING
