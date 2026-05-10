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
from dataclasses import dataclass

from .VerilogParser import VerilogParser
from .VerilogAst import PortInfo, ParameterInfo, PortType
from .vcg_rule_manager import VCGRuleManager
from .vcg_exceptions import VCGRuntimeError, VCGSyntaxError, VCGFileError, VCGParseError
from .vcg_logger import get_vcg_logger


DEFAULT_ALIGNMENT = 18


@dataclass(frozen=True)
class PortConnection:
    port: PortInfo
    signal: str


@dataclass(frozen=True)
class ParameterConnection:
    parameter: ParameterInfo
    value: str


class InstanceManager:

    def __init__(self, rule_manager: VCGRuleManager, macros=None):
        self.rule_manager = rule_manager
        self.macros = macros
        self.logger = get_vcg_logger('InstanceManager')
        self._ALIGN = DEFAULT_ALIGNMENT
        self.parser = VerilogParser(macros=self.macros, debug=False)

    def generate_instance(self, file_path: str, module_name: str, instance_name: str) -> str:
        try:
            self.logger.info(f"Generating instance '{instance_name}' of module '{module_name}' from {file_path}")

            ast = self._parse_verilog_file(file_path)

            ports = ast.get_port_info()
            parameters = ast.get_parameter_info()

            self.logger.debug(f"Found {len(ports)} ports and {len(parameters)} parameters")

            port_connections = self._generate_port_connections(ports)
            param_connections = self._generate_param_connections(parameters)

            connected_ports = sum(
                1 for connection in port_connections if connection.signal != ''
            )
            connected_params = len(param_connections)

            self.logger.debug(f"Generated {connected_ports}/{len(ports)} port connections and {connected_params} parameter connections")

            instance_code = self._render_instance_code(
                module_name, instance_name, param_connections, port_connections
            )

            if instance_code.strip():
                self.logger.info(f"Instance '{instance_name}' generated successfully with {len(port_connections)} port connections")

            return instance_code

        except (VCGFileError, VCGParseError, VCGSyntaxError, VCGRuntimeError):
            raise
        except Exception as e:
            self.logger.error(f"Instance generation failed: {e}")
            raise VCGRuntimeError(f"Generate instance Error: {e}") from e

    def _parse_verilog_file(self, file_path: str):
        self.logger.debug(f"Parsing Verilog file: {file_path}")
        return self.parser.parse_file(file_path)

    def _generate_port_connections(self, ports: list[PortInfo]) -> list[PortConnection]:
        connections = []

        self.logger.debug("Generating port connections...")

        for port in ports:
            port_name = port.name
            target_signal = self.rule_manager.resolve_signal_connection(port)
            connections.append(PortConnection(port=port, signal=target_signal))

            self.logger.debug(f"Port '{port_name}' -> '{target_signal}'")

        return connections

    def _generate_param_connections(self, parameters: list[ParameterInfo]) -> list[ParameterConnection]:
        connections = []

        self.logger.debug("Generating parameter connections...")

        for param in parameters:
            param_name = param.name
            param_value = self.rule_manager.resolve_param_connection(param_name)
            if param_value is not None:
                connections.append(ParameterConnection(parameter=param, value=param_value))
                self.logger.debug(f"Parameter '{param_name}' -> '{param_value}'")

        return connections

    def _render_instance_code(
        self,
        module_name: str,
        instance_name: str,
        param_connections: list[ParameterConnection],
        port_connections: list[PortConnection],
    ) -> str:
        lines = []

        if param_connections:
            lines.append(f"{module_name} #(")
            lines.extend(self._render_parameter_section(param_connections))
            lines.append(f") {instance_name} (")
        else:
            lines.append(f"{module_name} {instance_name} (")

        lines.extend(self._render_port_section(port_connections))

        lines.append(");")

        return '\n'.join(lines)

    def _render_parameter_section(self, param_connections: list[ParameterConnection]) -> list[str]:
        param_lines = [
            f"    .{connection.parameter.name:<{self._ALIGN}}({connection.value})"
            for connection in param_connections
        ]
        return self._with_trailing_commas(param_lines)

    def _render_port_section(self, port_connections: list[PortConnection]) -> list[str]:
        port_lines = []

        for index, connection in enumerate(port_connections):
            connection_part = self._format_port_connection(connection)
            if index < len(port_connections) - 1:
                connection_part += ","
            comment = self._generate_port_comment(connection.port)
            if comment:
                port_lines.append(f"    {connection_part:<{self._ALIGN * 2}}{comment}")
            else:
                port_lines.append(f"    {connection_part}")

        return port_lines

    def _format_port_connection(self, connection: PortConnection) -> str:
        return f".{connection.port.name:<{self._ALIGN}}({connection.signal})"

    def _with_trailing_commas(self, items):
        return [
            item + ("," if index < len(items) - 1 else "")
            for index, item in enumerate(items)
        ]

    def _generate_port_comment(self, port: PortInfo) -> str:
        if not port.direction:
            return ""

        comment_parts = [f"// {port.direction}"]

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
