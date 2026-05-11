#!/usr/bin/env python3
"""
Parser-facing Verilog declaration models.

These immutable dataclasses are internal frontend handoff objects used by
VerilogParser grammar actions before values are written to VerilogASTBuilder.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RangeSpec:
    msb_expr: str
    lsb_expr: str


@dataclass(frozen=True)
class PortDeclarator:
    name: str


@dataclass(frozen=True)
class PortDeclarationGroup:
    direction: str | None
    net_type: str | None
    range_spec: RangeSpec | None
    declarators: tuple[PortDeclarator, ...]


@dataclass(frozen=True)
class AnsiPortHeaderElement:
    direction: str | None
    net_type: str | None
    range_spec: RangeSpec | None
    declarator: PortDeclarator


@dataclass(frozen=True)
class ParameterDeclarator:
    name: str
    default_value: str


@dataclass(frozen=True)
class ParameterHeaderElement:
    param_type: str | None
    data_type: str | None
    declarator: ParameterDeclarator


@dataclass(frozen=True)
class ParameterDeclarationGroup:
    param_type: str
    data_type: str | None
    declarators: tuple[ParameterDeclarator, ...]
