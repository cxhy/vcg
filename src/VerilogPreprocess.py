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


@dataclass(frozen=True)
class SourceLine:
    line_no: int
    raw: str
    code: str
    active: bool = True


@dataclass(frozen=True)
class ModuleSpan:
    name: str
    start_line: int
    end_line: int
    lines: Tuple[SourceLine, ...]


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
        active_lines = self._process_conditionals_to_lines(content)
        spans = self._find_module_spans(active_lines)
        if not spans:
            return ""
        first = spans[0]
        return "\n".join(line.raw for line in active_lines if line.line_no >= first.start_line)

    def extract_module_ports_section(self, content: str) -> Tuple[str, str]:
        active_lines = self._process_conditionals_to_lines(content)
        span = self._select_module_span(self._find_module_spans(active_lines), None)
        if span is None:
            return "", "endmodule"
        module_text = self._extract_declaration_text(span)
        if module_text.endswith("\nendmodule"):
            return module_text[: -len("\nendmodule")], "endmodule"
        if module_text == "endmodule":
            return "", "endmodule"
        return module_text, "endmodule"

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
        return "\n".join(line.raw for line in self._process_conditionals_to_lines(content))

    def _scan_source_lines(self, content: str) -> List[SourceLine]:
        source_lines = []
        in_block_comment = False
        for line_no, line in enumerate(content.split("\n"), start=1):
            code, in_block_comment = self._code_visible_to_preprocessor(line, in_block_comment)
            source_lines.extend(self._split_inline_endmodule(line_no, line, code))
        return source_lines

    def _split_inline_endmodule(self, line_no: int, raw: str, code: str) -> List[SourceLine]:
        keyword_start = self._find_code_keyword(code, "endmodule")
        if keyword_start is None or code[:keyword_start].strip() == "":
            return [SourceLine(line_no=line_no, raw=raw, code=code, active=True)]

        prefix_code = code[:keyword_start].rstrip()
        return [
            SourceLine(line_no=line_no, raw=prefix_code, code=prefix_code, active=True),
            SourceLine(line_no=line_no, raw="endmodule", code="endmodule", active=True),
        ]

    def _find_code_keyword(self, text: str, keyword: str) -> Optional[int]:
        in_string = False
        escaped = False
        i = 0
        while i < len(text):
            char = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == "\"":
                    in_string = False
                i += 1
                continue
            if char == "\"":
                in_string = True
            elif self._keyword_at(text, keyword, i):
                return i
            i += 1
        return None

    def _keyword_at(self, text: str, keyword: str, index: int) -> bool:
        end = index + len(keyword)
        if text[index:end] != keyword:
            return False
        before = text[index - 1] if index > 0 else " "
        after = text[end] if end < len(text) else " "
        return not self._is_identifier_char(before) and not self._is_identifier_char(after)

    def _is_identifier_char(self, char: str) -> bool:
        return bool(re.match(r"[A-Za-z_0-9$]", char))

    def _process_conditionals_to_lines(self, content: str) -> List[SourceLine]:
        active_lines = []
        condition_stack: List[ConditionalFrame] = []

        for source_line in self._scan_source_lines(content):
            directive = self._parse_preprocessor_directive(source_line.code)
            if directive:
                condition_stack = self._handle_directive(directive, condition_stack, source_line.line_no)
                continue
            if self._should_include_line(condition_stack):
                active_lines.append(source_line)

        if condition_stack:
            frame = condition_stack[-1]
            raise VCGParseError(f"Unterminated conditional directive opened at line {frame.line_no}")

        return active_lines

    def _find_module_spans(self, lines: List[SourceLine]) -> List[ModuleSpan]:
        spans = []
        index = 0
        while index < len(lines):
            line = lines[index]
            module_match = self._match_module_start(line.code)
            if not module_match:
                index += 1
                continue

            module_name = module_match.group(1)
            span_lines = [line]
            end_line = None
            index += 1
            while index < len(lines):
                span_lines.append(lines[index])
                if self._is_endmodule_start(lines[index].code.strip()):
                    end_line = lines[index].line_no
                    index += 1
                    break
                index += 1

            if end_line is None:
                raise VCGParseError(
                    f"Unterminated module '{module_name}' opened at line {line.line_no}"
                )
            spans.append(
                ModuleSpan(
                    name=module_name,
                    start_line=line.line_no,
                    end_line=end_line,
                    lines=tuple(span_lines),
                )
            )
        return spans

    def _select_module_span(
        self,
        spans: List[ModuleSpan],
        target_module: Optional[str],
    ) -> Optional[ModuleSpan]:
        if not spans:
            return None
        if target_module is None:
            return spans[0]

        matches = [span for span in spans if span.name == target_module]
        if not matches:
            raise VCGParseError(f"Target module not found: {target_module}")
        if len(matches) > 1:
            raise VCGParseError(f"Duplicate target module found: {target_module}")
        return matches[0]

    def _extract_declaration_text(self, span: ModuleSpan) -> str:
        result_lines: List[str] = []
        declaration: List[str] = []
        header_lines: List[str] = []
        in_header = True
        skipping_body_item: List[str] = []

        for source_line in span.lines:
            stripped_code = source_line.code.strip()
            if not stripped_code:
                continue
            if self._is_endmodule_start(stripped_code):
                self._raise_if_open_declaration(declaration, source_line.line_no)
                result_lines.append("endmodule")
                break

            if in_header:
                in_header = self._append_header_line(source_line, header_lines, result_lines)
                continue

            if self._is_unsupported_directive(stripped_code):
                self._raise_unsupported_directive(source_line)

            if declaration:
                declaration = self._append_declaration_line(source_line, declaration, result_lines)
                continue

            if skipping_body_item:
                skipping_body_item = self._append_ignored_body_line(source_line, skipping_body_item)
                continue

            if self._starts_declaration(stripped_code):
                declaration = self._start_declaration(source_line, result_lines)
                continue

            if not self._line_ends_statement([source_line.code]):
                skipping_body_item = [source_line.code]

        if declaration:
            raise VCGParseError(f"Unterminated declaration in module '{span.name}'")
        if not result_lines or result_lines[-1] != "endmodule":
            raise VCGParseError(f"Module '{span.name}' missing endmodule")
        return "\n".join(result_lines)

    def _append_header_line(
        self,
        source_line: SourceLine,
        header_lines: List[str],
        result_lines: List[str],
    ) -> bool:
        self._raise_if_unsupported_directive(source_line)
        result_lines.append(source_line.code)
        header_lines.append(source_line.code)
        return not self._line_ends_statement(header_lines)

    def _append_declaration_line(
        self,
        source_line: SourceLine,
        declaration: List[str],
        result_lines: List[str],
    ) -> List[str]:
        declaration.append(source_line.code)
        if self._line_ends_statement(declaration):
            result_lines.extend(declaration)
            return []
        return declaration

    def _start_declaration(
        self,
        source_line: SourceLine,
        result_lines: List[str],
    ) -> List[str]:
        declaration = [source_line.code]
        if self._line_ends_statement(declaration):
            result_lines.extend(declaration)
            return []
        return declaration

    def _append_ignored_body_line(
        self,
        source_line: SourceLine,
        skipping_body_item: List[str],
    ) -> List[str]:
        skipping_body_item.append(source_line.code)
        if self._line_ends_statement(skipping_body_item):
            return []
        return skipping_body_item

    def _raise_if_open_declaration(self, declaration: List[str], line_no: int) -> None:
        if declaration:
            raise VCGParseError(f"Unterminated declaration before line {line_no}")

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
        in_string = False
        escaped = False
        while i < len(line):
            if in_block_comment:
                end = line.find("*/", i)
                if end == -1:
                    return "".join(result), True
                i = end + 2
                in_block_comment = False
                continue
            char = line[i]
            if in_string:
                result.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == "\"":
                    in_string = False
                i += 1
                continue
            if line.startswith("//", i):
                break
            if line.startswith("/*", i):
                in_block_comment = True
                i += 2
                continue
            result.append(char)
            if char == "\"":
                in_string = True
            i += 1
        return "".join(result), in_block_comment

    def _should_include_line(self, condition_stack: List[ConditionalFrame]) -> bool:
        return all(condition.active for condition in condition_stack)

    def preprocess_file(self, file_path: str, target_module: Optional[str] = None) -> str:
        try:
            content = self.read_file(file_path)
            return self.preprocess_string(content, target_module=target_module)
        except (ValueError, VCGError):
            raise
        except Exception as e:
            raise VCGParseError(f"Unexpected preprocess failure: {e}") from e

    def preprocess_string(self, verilog_code: str, target_module: Optional[str] = None) -> str:
        try:
            active_lines = self._process_conditionals_to_lines(verilog_code)
            module_span = self._select_module_span(
                self._find_module_spans(active_lines),
                target_module,
            )
            if module_span is None:
                return ""
            return self._extract_declaration_text(module_span)
        except (ValueError, VCGError):
            raise
        except Exception as e:
            raise VCGParseError(f"Unexpected preprocess failure: {e}") from e

    def clear_macros(self) -> None:
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

    def _match_module_start(self, code: str) -> Optional[re.Match]:
        return re.match(r"\s*module\s+([A-Za-z_][A-Za-z_0-9$]*)\b", code)

    def _is_module_start(self, code: str) -> bool:
        return self._match_module_start(code) is not None

    def _is_endmodule_start(self, code: str) -> bool:
        return bool(re.match(r"endmodule\b", code))

    def _is_unsupported_directive(self, code: str) -> bool:
        return bool(re.match(r"\s*`[A-Za-z_][A-Za-z_0-9$]*\b", code))

    def _raise_if_unsupported_directive(self, source_line: SourceLine) -> None:
        if self._is_unsupported_directive(source_line.code.strip()):
            self._raise_unsupported_directive(source_line)

    def _raise_unsupported_directive(self, source_line: SourceLine) -> None:
        directive = source_line.code.strip().split(None, 1)[0]
        if directive == "`include":
            raise VCGParseError(
                f"Unsupported `include inside extracted declaration at line {source_line.line_no}"
            )
        raise VCGParseError(
            f"Unsupported preprocessor directive {directive} at line {source_line.line_no}"
        )

    def _strip_line_comment(self, line: str) -> str:
        code, _ = self._code_visible_to_preprocessor(line, False)
        return code

    def _line_ends_statement(self, lines: List[str]) -> bool:
        return self._has_code_semicolon("\n".join(lines))

    def _has_code_semicolon(self, text: str) -> bool:
        in_block_comment = False
        in_line_comment = False
        in_string = False
        escaped = False
        i = 0
        while i < len(text):
            char = text[i]
            next_char = text[i + 1] if i + 1 < len(text) else ""
            if in_line_comment:
                if char == "\n":
                    in_line_comment = False
                i += 1
                continue
            if in_block_comment:
                if char == "*" and next_char == "/":
                    in_block_comment = False
                    i += 2
                    continue
                i += 1
                continue
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == "\"":
                    in_string = False
                i += 1
                continue
            if char == "/" and next_char == "/":
                in_line_comment = True
                i += 2
                continue
            if char == "/" and next_char == "*":
                in_block_comment = True
                i += 2
                continue
            if char == "\"":
                in_string = True
            elif char == ";":
                return True
            i += 1
        return False

    def _remove_comments_from_text(self, text: str) -> str:
        result = []
        in_block_comment = False
        for line in text.split("\n"):
            code, in_block_comment = self._code_visible_to_preprocessor(line, in_block_comment)
            result.append(code)
        return "\n".join(result)
