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
import argparse
import sys
from pathlib import Path

from src.vcg_file_processor import VCGFileProcessor
from src.vcg_exceptions import VCGError, VCGFileError
from src.vcg_logger import get_vcg_logger, setup_vcg_logging


def parse_macros_argument(macros_str: str | None) -> dict[str, str] | None:
    if macros_str is None or not macros_str.strip():
        return None

    macros: dict[str, str] = {}
    for macro in macros_str.split(','):
        macro = macro.strip()
        if not macro:
            continue

        if '=' in macro:
            key, value = macro.split('=', 1)
            macros[key.strip()] = value.strip()
        else:
            macros[macro] = ""

    return macros or None


def _create_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='VCG - Verilog Code Generator')
    parser.add_argument('file', help='Verilog Path')
    parser.add_argument('--debug', action='store_true', help='Debug Mode')
    parser.add_argument('--macros', type=str, help='Verilog macros (format: MACRO1,MACRO2 or MACRO1=val1,MACRO2=val2)')
    log_group = parser.add_argument_group('Logging Options')
    log_group.add_argument('--log-level',
                          choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                          default=None,
                          help='Set logging level (default: WARNING)')
    log_group.add_argument('--log-file', type=str,
                          help='Write logs to file')
    log_group.add_argument('--quiet', action='store_true',
                          help='Quiet mode: only show errors on console')
    return parser


def _resolve_log_level(debug: bool, log_level: str | None) -> str:
    if log_level is not None:
        return log_level
    if debug:
        return 'DEBUG'
    return 'WARNING'


def main(argv: list[str] | None = None) -> int:
    parser = _create_arg_parser()
    args = parser.parse_args(argv)
    log_level = _resolve_log_level(args.debug, args.log_level)
    logger = None

    try:
        setup_vcg_logging(
            level=log_level,
            log_file=args.log_file,
            quiet=args.quiet
        )

        logger = get_vcg_logger('Main')
        logger.info(f"Starting VCG with log level: {log_level}")

        file_path = Path(args.file)
        if not file_path.exists():
            raise VCGFileError("File missing", path=file_path)

        macros = parse_macros_argument(args.macros)

        processor = VCGFileProcessor(macros=macros)
        processor.process_file(file_path)
        logger.info("VCG generation completed successfully")

        print(f"VCG generation done: {file_path}")
        return 0

    except VCGError as e:
        if logger is not None:
            logger.error(f"VCG Error: {e}")
        print(f"VCG Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        if logger is not None and log_level == 'DEBUG':
            logger.exception("Unknown CLI error")
        print(f"Unknown Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
