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
from dataclasses import dataclass, replace
from os.path import expandvars
from pathlib import Path
import re
from types import MethodType

from .vcg_execution_engine import VCGExecutionEngine
from .vcg_exceptions import VCGFileError, VCGParseError, VCGRuntimeError
from .vcg_logger import file_context, get_vcg_logger


@dataclass(frozen=True)
class VCGBlock:
    code: str
    start_line: int
    end_line: int
    block_id: int
    gen_start_line: int | None = None
    gen_end_line: int | None = None


@dataclass(frozen=True)
class ExecutedBlock:
    block: VCGBlock
    generated_content: str


@dataclass
class _BlockScanState:
    blocks: list[VCGBlock]
    in_vcg_block: bool = False
    in_gen_block: bool = False
    current_block_lines: list[str] | None = None
    start_line: int = -1
    block_id: int = 0
    gen_start_line: int = -1
    gen_block_id: int | None = None


class VCGFileProcessor:
    VCG_BEGIN = '//VCG_BEGIN'
    VCG_END = '//VCG_END'
    VCG_GEN_BEGIN = '//VCG_GEN_BEGIN'
    VCG_GEN_END = '//VCG_GEN_END'
    VCG_GEN_BEGIN_RE = re.compile(r'//VCG_GEN_BEGIN_(\d+)\b')
    VCG_GEN_END_RE = re.compile(r'//VCG_GEN_END_(\d+)\b')
    
    def __init__(self, macros=None):
        self.macros = macros
        self.logger = get_vcg_logger('FileProcessor')

    def process_file(self, file_path: Path) -> None:
        file_path = Path(file_path).resolve()
        with file_context(file_path):
            try:
                self.logger.info(f"Starting to process file: {file_path.name}")
                content = self._read_file(file_path)
                vcg_blocks = self._extract_vcg_blocks(content)

                if not vcg_blocks:
                    self.logger.info("No VCG blocks found - skipping file")
                    return

                self.logger.info(f"Found {len(vcg_blocks)} VCG block(s) to process")
                executed_blocks = self._execute_blocks(vcg_blocks, file_path.parent)
                self.logger.debug("Injecting generated content back to file")
                updated_content = self._inject_generated_content_for_blocks(content, executed_blocks)
                self._write_file(file_path, updated_content)
                self._log_content_change(content, updated_content)
            except (VCGFileError, VCGParseError, VCGRuntimeError):
                raise
            except Exception as e:
                self.logger.error(f"Unexpected error processing file: {e}")
                raise VCGFileError(f"Process file error {file_path}: {e}") from e

    def _read_file(self, file_path: Path) -> str:
        try:
            content = file_path.read_text(encoding='utf-8')
        except OSError as e:
            self.logger.error(f"Failed to read file {file_path}: {e}")
            raise VCGFileError(f"Read file error {file_path}: {e}") from e

        self.logger.debug(
            f"File loaded - Size: {len(content)} chars, Lines: {len(content.splitlines())}"
        )
        return content

    def _write_file(self, file_path: Path, content: str) -> None:
        try:
            file_path.write_text(content, encoding='utf-8')
        except OSError as e:
            self.logger.error(f"Failed to write file {file_path}: {e}")
            raise VCGFileError(f"Write file error {file_path}: {e}") from e

    def _execute_blocks(self, vcg_blocks: list[VCGBlock], base_dir: Path) -> list[ExecutedBlock]:
        executed_blocks = []
        for vcg_block in vcg_blocks:
            self.logger.debug(
                f"Processing VCG block {vcg_block.block_id} "
                f"(lines {vcg_block.start_line + 1}-{vcg_block.end_line + 1})"
            )
            execution_engine = VCGExecutionEngine(macros=self.macros)
            self._bind_file_relative_paths(execution_engine, base_dir)
            python_code = self._preprocess_vcg_code(vcg_block.code)
            self._log_preprocessed_code(vcg_block, python_code)

            try:
                output = execution_engine.execute(python_code)
            except VCGRuntimeError:
                raise
            except Exception as e:
                raise VCGRuntimeError(f"Exec Error: {e}") from e

            executed_blocks.append(ExecutedBlock(block=vcg_block, generated_content=output))
            self.logger.info(f"VCG Block {vcg_block.block_id} Exec Done")

        return executed_blocks

    def _bind_file_relative_paths(self, execution_engine: VCGExecutionEngine, base_dir: Path) -> None:
        def expand_path(engine: VCGExecutionEngine, path_str: str) -> str:
            expanded_path = Path(expandvars(path_str.strip())).expanduser()
            if expanded_path.is_absolute():
                return str(expanded_path.resolve())
            return str((base_dir / expanded_path).resolve())

        execution_engine.expand_path = MethodType(expand_path, execution_engine)

    def _log_preprocessed_code(self, vcg_block: VCGBlock, python_code: str) -> None:
        self.logger.debug(f"Preprocessed Python code for block {vcg_block.block_id}:")
        for i, line in enumerate(python_code.split('\n'), 1):
            self.logger.debug(f"  {i:2d}: {line}")

    def _log_content_change(self, original_content: str, updated_content: str) -> None:
        original_lines = len(original_content.split('\n'))
        updated_lines = len(updated_content.split('\n'))
        content_change = updated_lines - original_lines
        self.logger.info(
            f"File processing completed - Lines: {original_lines} -> "
            f"{updated_lines} ({content_change:+d})"
        )
    
    def _extract_vcg_blocks(self, content: str) -> list[VCGBlock]:
        state = _BlockScanState(blocks=[])
        lines = content.split('\n')

        self.logger.debug("Scanning file for VCG blocks...")

        for line_num, line in enumerate(lines):
            if state.in_gen_block:
                self._handle_line_in_gen_block(state, line, line_num)
                continue

            if self.VCG_BEGIN in line:
                self._handle_vcg_begin(state, line_num)
                continue

            if self.VCG_END in line:
                self._handle_vcg_end(state, line_num)
                continue

            if self.VCG_GEN_BEGIN in line:
                self._handle_gen_begin(state, line, line_num)
                continue

            if self.VCG_GEN_END in line:
                self._handle_orphan_gen_end(line, line_num)

            if state.in_vcg_block and state.current_block_lines is not None:
                state.current_block_lines.append(line)

        self._validate_completed_scan(state)
        return state.blocks

    def _handle_line_in_gen_block(self, state: _BlockScanState, line: str, line_num: int) -> None:
        if self.VCG_GEN_BEGIN in line:
            raise VCGParseError(f"nested VCG_GEN_BEGIN at line {line_num + 1}")
        if self.VCG_GEN_END not in line:
            return

        end_id = self._parse_gen_marker(line, line_num, is_begin=False)
        if end_id != state.gen_block_id:
            raise VCGParseError(
                f"VCG_GEN_END id {end_id} does not match "
                f"VCG_GEN_BEGIN id {state.gen_block_id} at line {line_num + 1}"
            )

        state.blocks[end_id] = replace(
            state.blocks[end_id],
            gen_start_line=state.gen_start_line,
            gen_end_line=line_num,
        )
        state.in_gen_block = False
        state.gen_block_id = None

    def _handle_vcg_begin(self, state: _BlockScanState, line_num: int) -> None:
        if state.in_vcg_block:
            raise VCGParseError(f"nested VCG_BEGIN at line {line_num + 1}")
        state.in_vcg_block = True
        state.start_line = line_num
        state.current_block_lines = []
        self.logger.debug(f"VCG block start found at line {line_num + 1}")

    def _handle_vcg_end(self, state: _BlockScanState, line_num: int) -> None:
        if not state.in_vcg_block:
            raise VCGParseError(f"orphan VCG_END at line {line_num + 1}")

        current_block_lines = state.current_block_lines or []
        vcg_block = VCGBlock(
            code='\n'.join(current_block_lines),
            start_line=state.start_line,
            end_line=line_num,
            block_id=state.block_id,
        )
        state.blocks.append(vcg_block)
        self.logger.debug(
            f"VCG block {state.block_id} extracted: "
            f"{len(current_block_lines)} lines of Python code"
        )
        state.block_id += 1
        state.in_vcg_block = False
        state.current_block_lines = None

    def _handle_gen_begin(self, state: _BlockScanState, line: str, line_num: int) -> None:
        gen_block_id = self._parse_gen_marker(line, line_num, is_begin=True)
        if gen_block_id >= len(state.blocks):
            raise VCGParseError(f"orphan VCG_GEN_BEGIN_{gen_block_id} at line {line_num + 1}")
        if state.blocks[gen_block_id].gen_start_line is not None:
            raise VCGParseError(f"duplicate VCG_GEN_BEGIN_{gen_block_id} at line {line_num + 1}")

        state.in_gen_block = True
        state.gen_start_line = line_num
        state.gen_block_id = gen_block_id

    def _handle_orphan_gen_end(self, line: str, line_num: int) -> None:
        self._parse_gen_marker(line, line_num, is_begin=False)
        raise VCGParseError(f"orphan VCG_GEN_END at line {line_num + 1}")

    def _validate_completed_scan(self, state: _BlockScanState) -> None:
        if state.in_vcg_block:
            raise VCGParseError(f"unterminated VCG_BEGIN at line {state.start_line + 1}")
        if state.in_gen_block:
            raise VCGParseError(
                f"unterminated VCG_GEN_BEGIN_{state.gen_block_id} "
                f"at line {state.gen_start_line + 1}"
            )

    def _parse_gen_marker(self, line: str, line_num: int, *, is_begin: bool) -> int:
        marker_name = 'VCG_GEN_BEGIN' if is_begin else 'VCG_GEN_END'
        pattern = self.VCG_GEN_BEGIN_RE if is_begin else self.VCG_GEN_END_RE
        match = pattern.search(line)
        if not match:
            raise VCGParseError(f"malformed {marker_name} at line {line_num + 1}")
        return int(match.group(1))
    
    def _preprocess_vcg_code(self, raw_code: str) -> str:
        lines = raw_code.split('\n')
        processed_lines = []

        for line in lines:
            cleaned = re.sub(r'^\s*//', '', line)
            processed_lines.append(cleaned)

        return self._fix_indentation('\n'.join(processed_lines))
    
    def _fix_indentation(self, code: str) -> str:
        lines = code.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        if not non_empty_lines:
            return code
        
        min_indent = min(len(line) - len(line.lstrip()) for line in non_empty_lines)
        
        fixed_lines = []
        for line in lines:
            if line.strip():
                fixed_lines.append(line[min_indent:] if len(line) > min_indent else line)
            else:
                fixed_lines.append('')
        
        return '\n'.join(fixed_lines)
    
    def _inject_generated_content_for_blocks(
        self,
        original_content: str,
        executed_blocks: list[ExecutedBlock],
    ) -> str:
        lines = original_content.split('\n')
        for executed_block in sorted(
            executed_blocks,
            key=lambda item: item.block.gen_start_line
            if item.block.gen_start_line is not None
            else item.block.end_line,
            reverse=True,
        ):
            block = executed_block.block
            generated_lines = self._format_generated_lines(block.block_id, executed_block.generated_content)

            if block.gen_start_line is not None and block.gen_end_line is not None:
                self.logger.debug(f"Updating existing generation block for VCG block {block.block_id}")
                lines[block.gen_start_line:block.gen_end_line + 1] = generated_lines
            else:
                self.logger.debug(f"Creating new generation block for VCG block {block.block_id}")
                insert_at = block.end_line + 1
                lines[insert_at:insert_at] = generated_lines

        return '\n'.join(lines)

    def _format_generated_lines(self, block_id: int, generated_content: str) -> list[str]:
        generated_lines = [f"{self.VCG_GEN_BEGIN}_{block_id}"]
        content = generated_content.rstrip()
        if content:
            generated_lines.extend(content.split('\n'))
        generated_lines.append(f"{self.VCG_GEN_END}_{block_id}")
        return generated_lines
