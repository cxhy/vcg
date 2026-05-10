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
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple, Union

from .vcg_exceptions import VCGError, VCGFileError, VCGParseError


@dataclass(frozen=True)
class ConditionalFrame:
    taken: bool
    active: bool
    line_no: int
    else_seen: bool = False


class VerilogPreprocess:

    def __init__(self, macros: Union[Dict[str, str], List[str], List[Tuple[str, str]], None] = None):
        self.macros = self._parse_macros(macros)

    def _parse_macros(self, macros: Union[Dict[str, str], List[str], List[Tuple[str, str]], None]) -> Dict[str, str]:
        if macros is None:
            return {}

        if isinstance(macros, dict):
            result = {}
            for key, value in macros.items():
                if not isinstance(key, str):
                    raise ValueError(f"Macro key must be string, got {type(key).__name__}: {key}")
                if not isinstance(value, str):
                    raise ValueError(f"Macro value must be string, got {type(value).__name__}: {value}")
                result[key] = value
            return result

        if isinstance(macros, list):
            return self._parse_macro_list(macros)

        raise ValueError(f"Unsupported macros type: {type(macros).__name__}, expected dict, list, or None")

    def _parse_macro_list(self, macros: List[Union[str, Tuple[str, str]]]) -> Dict[str, str]:
        result = {}
        for item in macros:
            if isinstance(item, str):
                result[item] = "1"
            elif isinstance(item, tuple) and len(item) == 2:
                macro_name, macro_value = item
                if isinstance(macro_name, str) and isinstance(macro_value, str):
                    result[macro_name] = macro_value
                else:
                    raise ValueError(f"Macros key and value must be string, got: {item}")
            else:
                raise ValueError(f"Unknown type in macros list: {type(item).__name__}")
        return result

    def read_file(self, file_path: str) -> str:
        path = Path(file_path)
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError as e:
            raise VCGFileError(f"Verilog file not found: {file_path}") from e
        except UnicodeDecodeError:
            try:
                return path.read_text(encoding="latin-1")
            except OSError as e:
                raise VCGFileError(f"Failed to read {file_path}: {e}") from e
        except OSError as e:
            raise VCGFileError(f"Failed to read {file_path}: {e}") from e

    def remove_pre_module_content(self, content: str) -> str:
        lines = content.split("\n")
        module_index = self._find_module_line(lines)
        if module_index is None:
            return ""

        start_index = module_index
        while start_index > 0 and self._is_attribute_line(lines[start_index - 1]):
            start_index -= 1

        return "\n".join(lines[start_index:])

    def extract_module_ports_section(self, content: str) -> Tuple[str, str]:
        lines = content.split("\n")
        result_lines: List[str] = []
        in_module = False
        header_complete = False
        declaration: List[str] = []
        header_visible_lines: List[str] = []
        in_block_comment = False

        for line in lines:
            code, in_block_comment = self._code_visible_to_preprocessor(line, in_block_comment)
            stripped_code = code.strip()
            if not in_module and self._is_module_start(stripped_code):
                in_module = True

            if not in_module:
                continue
            if not header_complete:
                if stripped_code:
                    result_lines.append(code)
                    header_visible_lines.append(code)
                header_complete = self._line_ends_statement(header_visible_lines)
                continue
            if stripped_code.startswith("endmodule"):
                break
            declaration = self._collect_declaration(line, code, declaration, result_lines)

        if declaration:
            result_lines.extend(declaration)

        return "\n".join(result_lines), "endmodule"

    def _collect_declaration(
        self,
        line: str,
        visible_code: str,
        declaration: List[str],
        result_lines: List[str],
    ) -> List[str]:
        stripped_code = visible_code.strip()
        if not stripped_code:
            return declaration

        if declaration:
            declaration.append(visible_code)
            if self._line_ends_statement(declaration):
                result_lines.extend(declaration)
                return []
            return declaration

        if self._starts_declaration(stripped_code):
            new_declaration = [visible_code]
            if self._line_ends_statement(new_declaration):
                result_lines.extend(new_declaration)
                return []
            return new_declaration
        return []

    def _starts_declaration(self, line: str) -> bool:
        if not line:
            return False

        declaration_keywords = [
            r"^\s*input\b",
            r"^\s*output\b",
            r"^\s*inout\b",
            r"^\s*parameter\b",
            r"^\s*localparam\b",
        ]
        return any(re.match(pattern, line, re.IGNORECASE) for pattern in declaration_keywords)

    def process_conditional_compilation(self, content: str) -> str:
        result_lines = []
        condition_stack: List[ConditionalFrame] = []
        in_block_comment = False

        for line_no, line in enumerate(content.split("\n"), start=1):
            code, in_block_comment = self._code_visible_to_preprocessor(line, in_block_comment)
            directive = self._parse_preprocessor_directive(code)
            if directive:
                condition_stack = self._handle_directive(directive, condition_stack, line_no)
                continue
            if self._should_include_line(condition_stack):
                result_lines.append(line)

        if condition_stack:
            frame = condition_stack[-1]
            raise VCGParseError(f"Unterminated conditional directive opened at line {frame.line_no}")

        return "\n".join(result_lines)

    def _handle_directive(
        self,
        directive: Tuple[str, Optional[str]],
        condition_stack: List[ConditionalFrame],
        line_no: int,
    ) -> List[ConditionalFrame]:
        keyword, macro_name = directive
        if keyword in {"ifdef", "ifndef"}:
            return self._push_conditional(keyword, macro_name or "", condition_stack, line_no)
        if keyword == "elsif":
            return self._replace_top_for_elsif(macro_name or "", condition_stack, line_no)
        if keyword == "else":
            return self._replace_top_for_else(condition_stack, line_no)
        if keyword == "endif":
            if not condition_stack:
                raise VCGParseError(f"Orphan `endif at line {line_no}")
            return condition_stack[:-1]
        if keyword == "define":
            self._define_macro(macro_name, condition_stack)
        elif keyword == "undef":
            self._undef_macro(macro_name, condition_stack)
        return condition_stack

    def _push_conditional(
        self,
        keyword: str,
        macro_name: str,
        condition_stack: List[ConditionalFrame],
        line_no: int,
    ) -> List[ConditionalFrame]:
        parent_active = self._should_include_line(condition_stack)
        condition_met = macro_name in self.macros
        if keyword == "ifndef":
            condition_met = not condition_met
        active = parent_active and condition_met
        return condition_stack + [ConditionalFrame(taken=condition_met, active=active, line_no=line_no)]

    def _replace_top_for_elsif(
        self,
        macro_name: str,
        condition_stack: List[ConditionalFrame],
        line_no: int,
    ) -> List[ConditionalFrame]:
        if not condition_stack:
            raise VCGParseError(f"Orphan `elsif at line {line_no}")
        current = condition_stack[-1]
        if current.else_seen:
            raise VCGParseError(f"`elsif after `else at line {line_no}")
        parent_active = self._should_include_line(condition_stack[:-1])
        condition_met = (macro_name in self.macros) and not current.taken
        replacement = ConditionalFrame(
            taken=current.taken or condition_met,
            active=parent_active and condition_met,
            line_no=current.line_no,
        )
        return condition_stack[:-1] + [replacement]

    def _replace_top_for_else(
        self,
        condition_stack: List[ConditionalFrame],
        line_no: int,
    ) -> List[ConditionalFrame]:
        if not condition_stack:
            raise VCGParseError(f"Orphan `else at line {line_no}")
        current = condition_stack[-1]
        if current.else_seen:
            raise VCGParseError(f"Duplicate `else at line {line_no}")
        parent_active = self._should_include_line(condition_stack[:-1])
        replacement = ConditionalFrame(
            taken=True,
            active=parent_active and not current.taken,
            line_no=current.line_no,
            else_seen=True,
        )
        return condition_stack[:-1] + [replacement]

    def _define_macro(self, macro_name: Optional[str], condition_stack: List[ConditionalFrame]) -> None:
        if macro_name and self._should_include_line(condition_stack):
            name, value = self._split_macro_definition(macro_name)
            self.macros[name] = value

    def _undef_macro(self, macro_name: Optional[str], condition_stack: List[ConditionalFrame]) -> None:
        if macro_name and self._should_include_line(condition_stack):
            self.macros.pop(macro_name.split()[0], None)

    def _split_macro_definition(self, macro_definition: str) -> Tuple[str, str]:
        parts = macro_definition.strip().split(None, 1)
        if not parts:
            return "", "1"
        return parts[0], parts[1] if len(parts) == 2 else "1"

    def _parse_preprocessor_directive(self, code: str) -> Optional[Tuple[str, Optional[str]]]:
        match = re.match(r"\s*`(ifdef|ifndef|elsif|else|endif|define|undef)\b(?:\s+(.*))?$", code.strip())
        if not match:
            return None
        return match.group(1), match.group(2)

    def _code_visible_to_preprocessor(self, line: str, in_block_comment: bool) -> Tuple[str, bool]:
        result = []
        i = 0
        while i < len(line):
            if in_block_comment:
                end = line.find("*/", i)
                if end == -1:
                    return "".join(result), True
                i = end + 2
                in_block_comment = False
                continue
            if line.startswith("//", i):
                break
            if line.startswith("/*", i):
                in_block_comment = True
                i += 2
                continue
            result.append(line[i])
            i += 1
        return "".join(result), in_block_comment

    def _should_include_line(self, condition_stack: List[ConditionalFrame]) -> bool:
        return all(condition.active for condition in condition_stack)

    def preprocess_file(self, file_path: str) -> str:
        try:
            content = self.read_file(file_path)
            return self.preprocess_string(content)
        except (ValueError, VCGError):
            raise
        except Exception as e:
            raise VCGParseError(f"Unexpected preprocess failure: {e}") from e

    def preprocess_string(self, verilog_code: str) -> str:
        try:
            content = self.remove_pre_module_content(verilog_code)
            processed_content = self.process_conditional_compilation(content)
            module_decl, endmodule = self.extract_module_ports_section(processed_content)
            if not module_decl.strip():
                return ""
            return module_decl + "\n" + endmodule
        except (ValueError, VCGError):
            raise
        except Exception as e:
            raise VCGParseError(f"Unexpected preprocess failure: {e}") from e

    def clear_macros(self):
        self.macros.clear()

    def get_macros(self) -> Dict[str, str]:
        return self.macros.copy()

    def _find_module_line(self, lines: List[str]) -> Optional[int]:
        in_block_comment = False
        for index, line in enumerate(lines):
            code, in_block_comment = self._code_visible_to_preprocessor(line, in_block_comment)
            if self._is_module_start(code.strip()):
                return index
        return None

    def _is_attribute_line(self, line: str) -> bool:
        return bool(re.match(r"\s*\(\*.*\*\)\s*$", line))

    def _is_module_start(self, code: str) -> bool:
        return bool(re.match(r"module\s+\w+\b", code))

    def _strip_line_comment(self, line: str) -> str:
        code, _ = self._code_visible_to_preprocessor(line, False)
        return code

    def _line_ends_statement(self, lines: List[str]) -> bool:
        return ";" in self._remove_comments_from_text("\n".join(lines))

    def _remove_comments_from_text(self, text: str) -> str:
        result = []
        in_block_comment = False
        for line in text.split("\n"):
            code, in_block_comment = self._code_visible_to_preprocessor(line, in_block_comment)
            result.append(code)
        return "\n".join(result)
