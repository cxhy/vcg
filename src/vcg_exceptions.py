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
from os import PathLike

__all__ = [
    "VCGError",
    "VCGFileError",
    "VCGParseError",
    "VCGSyntaxError",
    "VCGRuntimeError",
]


class VCGError(Exception):
    """Base class for all VCG domain errors.

    The plain ``VCGError("message")`` form is kept compatible with the
    historical API. Optional context fields are available for structured
    logging, CLI presentation, and tests that need machine-readable location
    data.
    """

    def __init__(
        self,
        message: str,
        *,
        path: str | PathLike[str] | None = None,
        lineno: int | None = None,
        column: int | None = None,
        snippet: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.path = str(path) if path is not None else None
        self.lineno = lineno
        self.column = column
        self.snippet = snippet

    @property
    def location(self) -> str | None:
        """Return a compact location string, if any location data exists."""
        if self.path is None and self.lineno is None and self.column is None:
            return None

        location = self.path or "<unknown>"
        if self.lineno is not None:
            location = f"{location}:{self.lineno}"
            if self.column is not None:
                location = f"{location}:{self.column}"
        elif self.column is not None:
            location = f"{location}:?:{self.column}"
        return location

    def __str__(self) -> str:
        parts = [self.message]
        if self.location is not None:
            parts.append(f"[{self.location}]")
        if self.snippet is not None:
            parts.append(f"snippet: {self.snippet}")
        return " ".join(parts)


class VCGFileError(VCGError):
    """File-system or file-content access failure."""


class VCGParseError(VCGError):
    """Failure while converting Verilog or VCG source into internal data."""


class VCGSyntaxError(VCGError):
    """Source syntax error with optional line, column, and snippet context."""


class VCGRuntimeError(VCGError):
    """Runtime failure during VCG DSL execution or code generation."""
