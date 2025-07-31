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
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from vcg_execution_engine import VCGExecutionEngine
from vcg_exceptions import VCGFileError, VCGParseError
from vcg_logger import get_vcg_logger, set_file_context, clear_file_context

class VCGBlock:
    def __init__(self, code: str, start_line: int, end_line: int, block_id: int):
        self.code = code
        self.start_line = start_line
        self.end_line = end_line
        self.block_id = block_id
        self.generated_content = ""

class VCGFileProcessor:
    VCG_BEGIN = '//VCG_BEGIN'
    VCG_END = '//VCG_END'
    VCG_GEN_BEGIN = '//VCG_GEN_BEGIN'
    VCG_GEN_END = '//VCG_GEN_END'
    
    def __init__(self, macros = None, debug: bool = False):
        self.debug = debug
        self.macros = macros 
        self.logger = get_vcg_logger('FileProcessor')

    def process_file(self, file_path: Path) -> None:
        try:
            set_file_context(file_path)

            self.logger.info(f"Starting to process file: {file_path.name}")

            content = file_path.read_text(encoding='utf-8')

            self.logger.debug(f"File loaded - Size: {len(content)} chars, Lines: {len(content.splitlines())}")
            
            vcg_blocks = self._extract_vcg_blocks_with_position(content)
            
            if not vcg_blocks:
                self.logger.info("No VCG blocks found - skipping file")
                return
            
            self.logger.info(f"Found {len(vcg_blocks)} VCG block(s) to process")
            
            for vcg_block in vcg_blocks:
                self.logger.debug(f"Processing VCG block {vcg_block.block_id} (lines {vcg_block.start_line+1}-{vcg_block.end_line+1})")
                execution_engine = VCGExecutionEngine(macros=self.macros)
                python_code = self._preprocess_vcg_code(vcg_block.code)

                self.logger.debug(f"Preprocessed Python code for block {vcg_block.block_id}:")
                for i, line in enumerate(python_code.split('\n'), 1):
                    self.logger.debug(f"  {i:2d}: {line}")
                
                output = execution_engine.execute(python_code)
                vcg_block.generated_content = output
                
                if self.debug:
                    print(f"VCG Block {vcg_block.block_id} Exec Done")
            
            self.logger.debug("Injecting generated content back to file")
            
            updated_content = self._inject_generated_content_for_blocks(content, vcg_blocks)
            
            file_path.write_text(updated_content, encoding='utf-8')

            original_lines = len(content.split('\n'))
            updated_lines = len(updated_content.split('\n'))
            content_change = updated_lines - original_lines

            self.logger.info(f"File processing completed - Lines: {original_lines} → {updated_lines} ({content_change:+d})")
            
        except Exception as e:
            self.logger.error(f"Error processing file: {e}")
            raise VCGFileError(f"Read file Error {file_path}: {e}")
        finally:
            clear_file_context()
    
    def _extract_vcg_blocks_with_position(self, content: str) -> List[VCGBlock]:
        blocks = []
        lines = content.split('\n')
        
        in_vcg_block = False
        current_block_lines = []
        start_line = -1
        block_id = 0

        self.logger.debug("Scanning file for VCG blocks...")
        
        for line_num, line in enumerate(lines):
            if self.VCG_BEGIN in line:
                in_vcg_block = True
                start_line = line_num
                current_block_lines = []
                self.logger.debug(f"VCG block start found at line {line_num + 1}")
            elif self.VCG_END in line:
                if in_vcg_block:
                    block_code = '\n'.join(current_block_lines)
                    vcg_block = VCGBlock(
                        code=block_code,
                        start_line=start_line,
                        end_line=line_num,
                        block_id=block_id
                    )
                    blocks.append(vcg_block)
                    self.logger.debug(f"VCG block {block_id} extracted: {len(current_block_lines)} lines of Python code")
                    block_id += 1
                in_vcg_block = False
            elif in_vcg_block:
                current_block_lines.append(line)
        
        return blocks
    
    def _preprocess_vcg_code(self, raw_code: str) -> str:
        lines = raw_code.split('\n')
        processed_lines = []
        
        for line in lines:
            cleaned = re.sub(r'^\s*//', '', line)
            if cleaned.strip():  
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
    
    def _inject_generated_content_for_blocks(self, original_content: str, vcg_blocks: List[VCGBlock]) -> str:
        lines = original_content.split('\n')
        result_lines = []
        
        block_content_map = {block.block_id: block.generated_content for block in vcg_blocks}
        
        current_block_id = 0
        in_gen_block = False
        gen_block_id = None
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            if self.VCG_END in line:
                result_lines.append(line)
                
                has_existing_gen_block = False
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if f"{self.VCG_GEN_BEGIN}_{current_block_id}" in next_line:
                        has_existing_gen_block = True
                
                if not has_existing_gen_block:
                    self.logger.debug(f"Creating new generation block for VCG block {current_block_id}")
                    result_lines.append(f"{self.VCG_GEN_BEGIN}_{current_block_id}")
                    if current_block_id in block_content_map:
                        content = block_content_map[current_block_id].rstrip()
                        if content:
                            result_lines.append(content)
                    result_lines.append(f"{self.VCG_GEN_END}_{current_block_id}")
                else:
                    self.logger.debug(f"Updating existing generation block for VCG block {current_block_id}")
                
                current_block_id += 1
            elif self.VCG_GEN_BEGIN in line:
                match = re.search(r'VCG_GEN_BEGIN_(\d+)', line)
                if match:
                    gen_block_id = int(match.group(1))
                    in_gen_block = True
                    result_lines.append(line)
                    if gen_block_id in block_content_map:
                        content = block_content_map[gen_block_id].rstrip()
                        if content:
                            result_lines.append(content)
                else:
                    result_lines.append(line)
                    in_gen_block = True
                    gen_block_id = None
                    
            elif self.VCG_GEN_END in line:
                result_lines.append(line)
                in_gen_block = False
                gen_block_id = None
                
            elif not in_gen_block:
                result_lines.append(line)
            
            i += 1
        
        return '\n'.join(result_lines)
    
def test():
    process = VCGFileProcessor(debug=True)
    file_path = Path("uart.v")
    process.process_file(file_path=file_path)

if __name__ == "__main__":
    test()
