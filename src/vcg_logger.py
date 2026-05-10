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
import logging
import sys
from contextlib import contextmanager
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Iterator, Optional, Union

current_file_context: ContextVar[Optional[str]] = ContextVar('current_file_context', default=None)
_file_context_tokens: ContextVar[tuple[Token, ...]] = ContextVar(
    'file_context_tokens',
    default=(),
)

_VCG_LOGGER = logging.getLogger('VCG')
_console_handler: Optional[logging.Handler] = None
_file_handler: Optional[logging.Handler] = None

class FileContextFormatter(logging.Formatter):

    def format(self, record):
        file_context = current_file_context.get()

        if file_context:
            record.file_context = f"[{file_context}]"
        else:
            record.file_context = ""

        return super().format(record)


_CONSOLE_FORMATTER = FileContextFormatter(
    fmt='[VCG-%(levelname)s] %(file_context)s %(name)s: %(message)s'
)
_FILE_FORMATTER = FileContextFormatter(
    fmt='%(asctime)s [%(levelname)s] %(file_context)s %(name)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
_DETAILED_CONSOLE_FORMATTER = FileContextFormatter(
    fmt='[VCG-%(levelname)s] %(file_context)s %(name)s:%(lineno)d - %(message)s'
)


def _coerce_level(level: Union[int, str]) -> int:
    if isinstance(level, str):
        return getattr(logging, level.upper(), logging.INFO)
    return level


def _close_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def _context_value(file_path: Optional[Union[str, Path]]) -> Optional[str]:
    if file_path:
        return Path(file_path).name
    return None


@contextmanager
def file_context(file_path: Optional[Union[str, Path]]) -> Iterator[None]:
    token = current_file_context.set(_context_value(file_path))
    try:
        yield
    finally:
        current_file_context.reset(token)


def _create_console_handler(level: int, quiet: bool) -> logging.Handler:
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.ERROR if quiet else level)
    if level <= logging.DEBUG:
        handler.setFormatter(_DETAILED_CONSOLE_FORMATTER)
    else:
        handler.setFormatter(_CONSOLE_FORMATTER)
    return handler


def _create_file_handler(log_file: Union[str, Path], mode: str) -> logging.Handler:
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_path, mode=mode, encoding='utf-8')
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(_FILE_FORMATTER)
    return handler


def setup_logger(
    level: Union[int, str] = logging.WARNING,
    log_file: Optional[Union[str, Path]] = None,
    quiet: bool = False,
    file_mode: str = 'a',
) -> None:
    global _console_handler, _file_handler

    resolved_level = _coerce_level(level)
    _close_handlers(_VCG_LOGGER)

    _VCG_LOGGER.setLevel(resolved_level)
    _console_handler = _create_console_handler(resolved_level, quiet)
    _VCG_LOGGER.addHandler(_console_handler)

    _file_handler = None
    if log_file:
        _file_handler = _create_file_handler(log_file, file_mode)
        _VCG_LOGGER.addHandler(_file_handler)


def set_file_context(file_path: Optional[Union[str, Path]] = None) -> None:
    token = current_file_context.set(_context_value(file_path))
    _file_context_tokens.set((*_file_context_tokens.get(), token))


def clear_file_context() -> None:
    tokens = _file_context_tokens.get()
    if tokens:
        _file_context_tokens.set(tokens[:-1])
        current_file_context.reset(tokens[-1])
    else:
        current_file_context.set(None)

def get_vcg_logger(name: str = '') -> logging.Logger:
    return logging.getLogger(f'VCG.{name}' if name else 'VCG')

def setup_vcg_logging(**kwargs):
    return setup_logger(**kwargs)
