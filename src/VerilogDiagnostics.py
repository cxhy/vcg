#!/usr/bin/env python3
"""
Frontend diagnostics shared by the Verilog lexer and parser.
"""

from dataclasses import dataclass
from typing import Literal, Optional


DiagnosticSeverity = Literal["error", "warning"]
DiagnosticStage = Literal["preprocess", "lexer", "parser", "ast"]
DiagnosticKind = Literal["recognized_unsupported", "invalid", "syntax", "semantic"]


@dataclass(frozen=True)
class SourceLocation:
    line: int
    column: int
    lexpos: Optional[int] = None


@dataclass(frozen=True)
class FrontendDiagnostic:
    code: str
    message: str
    severity: DiagnosticSeverity
    stage: DiagnosticStage
    kind: DiagnosticKind
    location: Optional[SourceLocation] = None
    spelling: str = ""

    @property
    def is_error(self) -> bool:
        return self.severity == "error"

    def format(self) -> str:
        location = ""
        if self.location is not None:
            location = f" at line {self.location.line}, column {self.location.column}"
        return f"{self.code}{location}: {self.message}"


def format_diagnostics(diagnostics: tuple[FrontendDiagnostic, ...]) -> str:
    errors = [diagnostic for diagnostic in diagnostics if diagnostic.is_error]
    if not errors:
        return ""
    lines = [f"Parse failed with {len(errors)} diagnostics:"]
    lines.extend(f"- {diagnostic.format()}" for diagnostic in errors)
    return "\n".join(lines)
