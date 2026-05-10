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
import os
from pathlib import Path

from .vcg_rule_manager import VCGRuleManager
from .vcg_instance_manager import InstanceManager
from .vcg_wires_manager import WiresManager
from .vcg_exceptions import VCGRuntimeError, VCGSyntaxError, VCGFileError, VCGParseError
from .vcg_logger import get_vcg_logger


class OrderedOutputManager:
    def __init__(self) -> None:
        self.outputs: list[str] = []

    def add(self, text: str) -> None:
        self.outputs.append(text)

    def get_final_output(self) -> str:
        return '\n'.join(self.outputs)

    def clear(self) -> None:
        self.outputs.clear()


class VCGExecutionEngine:

    """Execute trusted VCG Python DSL blocks.

    VCG blocks run with full Python builtins. This engine is a local
    developer-tool executor, not a sandbox for untrusted templates.
    """

    def __init__(self, macros=None):
        self.rule_manager = VCGRuleManager()
        self.output_manager = OrderedOutputManager()
        self.wires_manager = WiresManager(self.rule_manager, macros=macros)
        self.instance_manager = InstanceManager(self.rule_manager, macros=macros)
        self.logger = get_vcg_logger('ExecutionEngine')

    def expand_path(self, path_str: str) -> str:
        stripped_path = path_str.strip()
        if not stripped_path:
            raise VCGFileError("Empty file path")

        expanded_path = os.path.expandvars(stripped_path)
        expanded_path = os.path.expanduser(expanded_path)
        resolved_path = Path(expanded_path).resolve()
        if not resolved_path.exists():
            raise VCGFileError(f"File not found: {path_str} -> {resolved_path}")
        return str(resolved_path)

    def execute(self, python_code: str) -> str:
        try:
            self.logger.debug("Starting Python code execution")

            self.rule_manager.reset()
            self.output_manager.clear()

            context = self._create_execution_context()

            exec(python_code, context)

            return self.output_manager.get_final_output()

        except (VCGFileError, VCGParseError, VCGSyntaxError, VCGRuntimeError):
            raise
        except Exception as e:
            self.logger.error(f"Execution error: {str(e)}")
            raise VCGRuntimeError(f"Exec Error: {str(e)}") from e

    def _create_execution_context(self) -> dict[str, object]:
        return {
            '__builtins__': __builtins__,
            'print': self._print,
            'Instance': self._instance,
            'Connect': self.rule_manager.add_signal_rule,
            'ConnectParam': self.rule_manager.add_param_rule,
            'WiresDef': self._wires_def,
            'WiresRule': self.rule_manager.add_wire_rule,
        }

    def _instance(self, file_path: str, module_name: str, instance_name: str) -> None:
        resolved_path = self.expand_path(file_path)
        instance_code = self.instance_manager.generate_instance(
            resolved_path, module_name, instance_name
        )
        self._add_generated_output(instance_code)
        self.rule_manager.reset()
        self.logger.debug(f"Auto-reset rules after Instance '{instance_name}' generation completed")

    def _wires_def(
        self,
        file_path: str,
        module_name: str,
        port_type: str | None = None,
        pattern: str = 'greedy',
    ) -> None:
        resolved_path = self.expand_path(file_path)
        wire_code = self.wires_manager.generate_wires_def(
            resolved_path, module_name, port_type, pattern
        )
        self._add_generated_output(wire_code)
        self.rule_manager.reset()
        self.logger.debug(f"Auto-reset rules after WiresDef for module '{module_name}' generation completed")

    def _add_generated_output(self, output: str) -> None:
        if output.strip():
            self.output_manager.add(output)

    def _print(self, *args, sep=' ', end='\n', file=None, flush=False) -> None:
        if file is not None:
            print(*args, sep=sep, end=end, file=file, flush=flush)
            return

        text = sep.join(str(arg) for arg in args) + end
        normalized = self._normalize_print_output(text)
        if normalized is not None:
            self.output_manager.add(normalized)

    def _normalize_print_output(self, text: str) -> str | None:
        if text == '\n':
            return ''
        if text.strip():
            return text.rstrip()
        if text and '\n' in text:
            return ''
        return None
