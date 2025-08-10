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
"""
VCG (Verilog Code Generator)
"""

import sys
import argparse
from pathlib import Path
from vcg_file_processor import VCGFileProcessor
from vcg_exceptions import VCGError
from vcg_logger import setup_vcg_logging, get_vcg_logger

def parse_macros_argument(macros_str: str):
    if not macros_str:
        return None
    
    macros_list = [macro.strip() for macro in macros_str.split(',')]
    
    has_assignment = any('=' in macro for macro in macros_list)
    
    if has_assignment:
        macros_dict = {}
        for macro in macros_list:
            if '=' in macro:
                key, value = macro.split('=', 1)
                macros_dict[key.strip()] = value.strip()
            else:
                macros_dict[macro] = ""
        return macros_dict
    else:
        return macros_list

def main():
    parser = argparse.ArgumentParser(description='VCG - Verilog Code Generator')
    parser.add_argument('file', help='Verilog Path')
    parser.add_argument('--debug', action='store_true', help='Debug Mode')
    parser.add_argument('--macros', type=str, help='Verilog macros (format: MACRO1,MACRO2 or MACRO1=val1,MACRO2=val2)')
    log_group = parser.add_argument_group('Logging Options')
    log_group.add_argument('--log-level', 
                          choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                          default='WARNING', 
                          help='Set logging level (default: WARNING)')
    log_group.add_argument('--log-file', type=str, 
                          help='Write logs to file')
    log_group.add_argument('--quiet', action='store_true',
                          help='Quiet mode: only show errors on console')
    
    
    args = parser.parse_args()
    
    try:
        file_path = Path(args.file)
        if not file_path.exists():
            raise VCGError(f"File Missing: {file_path}")
        
        setup_vcg_logging(
            level=args.log_level,
            log_file=args.log_file,
            quiet=args.quiet
        )

        logger = get_vcg_logger('Main')
        logger.info(f"Starting VCG with log level: {args.log_level}")
        

        macros = parse_macros_argument(args.macros) if args.macros else None
        
        processor = VCGFileProcessor(macros=macros)
        processor.process_file(file_path)
        logger.info("VCG generation completed successfully")
        
        print(f"VCG generate Done: {file_path}")
        
    except VCGError as e:
        print(f"VCG Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unknow Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
