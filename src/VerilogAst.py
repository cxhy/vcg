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

from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict, Union
from dataclasses import dataclass, field
from enum import Enum
import re


class PortDirection(Enum):
    INPUT = "input"
    OUTPUT = "output"
    INOUT = "inout"


class NetType(Enum):
    WIRE = "wire"
    REG = "reg"
    LOGIC = "logic"


class ParameterType(Enum):
    PARAMETER = "parameter"
    LOCALPARAM = "localparam"


@dataclass
class RangeExpression:
    msb_expr: str      
    lsb_expr: str      
    msb_value: Optional[int] = None    
    lsb_value: Optional[int] = None    
    width_expr: Optional[str] = None   
    width_value: Optional[int] = None  
    
    def __post_init__(self):
        if self.width_expr is None:
            self.width_expr = self._calculate_width_expression()
        if self.width_value is None and self.msb_value is not None and self.lsb_value is not None:
            self.width_value = abs(self.msb_value - self.lsb_value) + 1
    
    def _calculate_width_expression(self) -> str:
        if self.msb_expr == self.lsb_expr:
            return "1"
        
        if self.lsb_expr == "0":
            if self.msb_expr.isdigit():
                return str(int(self.msb_expr) + 1)
            else:
                simplified_width = self._simplify_plus_one_expression(self.msb_expr)
                if simplified_width:
                    return simplified_width
                else:
                    return f"{self.msb_expr}+1"
        
        if self.msb_expr.isdigit() and self.lsb_expr.isdigit():
            msb_val = int(self.msb_expr)
            lsb_val = int(self.lsb_expr)
            return str(abs(msb_val - lsb_val) + 1)
        else:
            return f"({self.msb_expr}-{self.lsb_expr}+1)"
    
    def _simplify_plus_one_expression(self, expr: str) -> Optional[str]:
        import re
        
        expr = expr.strip()
        
        pattern = r'^(.+?)\s*-\s*1$'
        match = re.match(pattern, expr)
        
        if match:
            base_expr = match.group(1).strip()
            
            if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', base_expr):
                return base_expr
            
            if base_expr.startswith('(') and base_expr.endswith(')'):
                return base_expr[1:-1]
            
            return base_expr
        
        return None
    
    @property
    def is_parametric(self) -> bool:
        return not (self.msb_expr.isdigit() and self.lsb_expr.isdigit())
    
    @property
    def is_single_bit(self) -> bool:
        return self.msb_expr == self.lsb_expr or (
            self.msb_value is not None and 
            self.lsb_value is not None and 
            self.msb_value == self.lsb_value
        )


@dataclass
class PortInfo:
    name: str  
    direction: str
    net_type: str  
    range_expr: Optional[RangeExpression] = None 
    
    @property
    def width(self) -> Optional[Union[int, str]]:
        if self.range_expr is None:
            return None
        if self.range_expr.width_value is not None:
            return self.range_expr.width_value
        return self.range_expr.width_expr

    @property
    def msb(self) -> Optional[Union[int, str]]:
        if self.range_expr is None:
            return None
        if self.range_expr.msb_value is not None:
            return self.range_expr.msb_value
        return self.range_expr.msb_expr
    
    @property
    def lsb(self) -> Optional[Union[int, str]]:
        if self.range_expr is None:
            return None
        if self.range_expr.lsb_value is not None:
            return self.range_expr.lsb_value
        return self.range_expr.lsb_expr
    
    @property
    def is_vector(self) -> bool:
        if self.range_expr is None:
            return False
        return not self.range_expr.is_single_bit
    
    @property
    def is_parametric(self) -> bool:
        if self.range_expr is None:
            return False
        return self.range_expr.is_parametric
    
    def get_width_description(self) -> str:
        if self.range_expr is None:
            return "1 bit"
        
        if self.range_expr.is_single_bit:
            return "1 bit"
        
        if self.range_expr.width_value is not None:
            return f"{self.range_expr.width_value} bits"
        else:
            return f"{self.range_expr.width_expr} bits"
    
    def get_range_description(self) -> str:
        if self.range_expr is None:
            return "single bit"
        
        if self.range_expr.is_single_bit:
            return "single bit"
        
        return f"[{self.range_expr.msb_expr}:{self.range_expr.lsb_expr}]"

@dataclass
class ParameterInfo:
    name: str       
    param_type: str 
    default_value: str 
    data_type: Optional[str] = None
    
    @property
    def is_localparam(self) -> bool:
        return self.param_type == ParameterType.LOCALPARAM.value


@dataclass
class ModuleInfo:
    name: str
    parameters: List[ParameterInfo] = field(default_factory=list)
    ports: List[PortInfo] = field(default_factory=list)
    body_ignored: bool = True


@dataclass
class Range:
    msb: int
    lsb: int
    
    @property
    def width(self) -> int:
        return abs(self.msb - self.lsb) + 1



class BaseASTNode(ABC):
    
    def __init__(self, node_type: str, source_line: int = 0,
                 source_column: int = 0, source_position: int = 0):
        self.node_type = node_type
        self.source_line = source_line
        self.source_column = source_column
        self.source_position = source_position
        self.parent: Optional[BaseASTNode] = None
        self.children: List[BaseASTNode] = []
        
    def add_child(self, child: 'BaseASTNode') -> None:
        if child is not None:
            child.parent = self
            self.children.append(child)

    def remove_child(self, child: 'BaseASTNode') -> None:
        if child in self.children:
            child.parent = None
            self.children.remove(child)
            
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit(self)
        
    def __str__(self) -> str:
        return f"{self.node_type}@{self.source_line}:{self.source_column}"

class DesignUnit(BaseASTNode):
    
    def __init__(self):
        super().__init__("DesignUnit")
        self.modules: List['ModuleDeclaration'] = []
    def add_module(self, module: 'ModuleDeclaration') -> None:
        self.add_child(module)
        self.modules.append(module)


class Expression(BaseASTNode):
    
    def __init__(self, node_type: str, **kwargs):
        super().__init__(node_type, **kwargs)
        self.value: str = ""


class Identifier(Expression):
    
    def __init__(self, name: str, **kwargs):
        super().__init__("Identifier", **kwargs)
        self.name = name
        self.value = name


class NumericLiteral(Expression):
    
    def __init__(self, value: str, **kwargs):
        super().__init__("NumericLiteral", **kwargs)
        self.value = value


class StringLiteral(Expression):
    
    def __init__(self, value: str, **kwargs):
        super().__init__("StringLiteral", **kwargs)
        self.value = value


class Declaration(BaseASTNode):
    
    def __init__(self, node_type: str, identifier: str, **kwargs):
        super().__init__(node_type, **kwargs)
        self.identifier = identifier


class ParameterDeclaration(Declaration):
    
    def __init__(self, identifier: str, parameter_type: str = "parameter", 
                 default_value: Optional[Expression] = None, 
                 data_type: Optional[str] = None, **kwargs):
        super().__init__("ParameterDeclaration", identifier, **kwargs)
        self.parameter_type = parameter_type
        self.default_value = default_value or StringLiteral("")
        self.data_type = data_type
        if self.default_value:
            self.add_child(self.default_value)
    
    def to_info(self) -> ParameterInfo:
        return ParameterInfo(
            name=self.identifier,
            param_type=self.parameter_type,
            default_value=self.default_value.value if self.default_value else "",
            data_type=self.data_type
        )


class PortDeclaration(Declaration):
    
    def __init__(self, identifier: str, direction: str,
                 net_type: str = "wire", range_expr: Optional[RangeExpression] = None, **kwargs):
        super().__init__("PortDeclaration", identifier, **kwargs)
        self.direction = direction
        self.net_type = net_type
        self.range_expr = range_expr
    def to_info(self) -> PortInfo:
        return PortInfo(
            name=self.identifier,
            direction=self.direction,
            net_type=self.net_type,
            range_expr=self.range_expr
        )


class ModuleDeclaration(BaseASTNode):
    
    def __init__(self, module_name: str, **kwargs):
        super().__init__("ModuleDeclaration", **kwargs)
        self.module_name = module_name
        self.parameters: List[ParameterDeclaration] = []
        self.ports: List[PortDeclaration] = []
        self.internal_declarations: List[Declaration] = []
        self.body_placeholder = True 
        
    def add_parameter(self, parameter: ParameterDeclaration) -> None:
        self.add_child(parameter)
        self.parameters.append(parameter)
        
    def add_port(self, port: PortDeclaration) -> None:
        self.add_child(port)
        self.ports.append(port)
        
    def add_internal_declaration(self, declaration: Declaration) -> None:
        self.add_child(declaration)
        self.internal_declarations.append(declaration)
        
    def to_info(self) -> ModuleInfo:
        return ModuleInfo(
            name=self.module_name,
            parameters=[p.to_info() for p in self.parameters],
            ports=[p.to_info() for p in self.ports],
            body_ignored=self.body_placeholder
        )


class ErrorNode(BaseASTNode):
    
    def __init__(self, error_message: str, recovery_point: str = "", **kwargs):
        super().__init__("ErrorNode", **kwargs)
        self.error_message = error_message
        self.recovery_point = recovery_point

class ExpressionSimplifier:
    
    @staticmethod
    def parse_expression(expr_str: str) -> Optional[int]:
        try:
            expr_str = expr_str.strip()
            if expr_str.isdigit():
                return int(expr_str)
            
            if "'" in expr_str:
                if 'd' in expr_str:
                    return int(expr_str.split('d')[-1])
                elif 'h' in expr_str:
                    return int(expr_str.split('h')[-1], 16)
                elif 'b' in expr_str:
                    return int(expr_str.split('b')[-1], 2)
                elif 'o' in expr_str:
                    return int(expr_str.split('o')[-1], 8)
            
            return None
        except (ValueError, IndexError):
            return None
    
    @staticmethod
    def simplify_numeric_parts(expr_str: str) -> tuple[str, Optional[int]]:
        expr_str = expr_str.strip()
        
        numeric_val = ExpressionSimplifier.parse_expression(expr_str)
        if numeric_val is not None:
            return expr_str, numeric_val
        
        if re.match(r'^[\d+\-*/\(\)\s]+$', expr_str):
            try:
                result = eval(expr_str)
                return str(result), int(result)
            except:
                pass
        
        return expr_str, None
    
    @staticmethod
    def create_range_expression(msb_str: str, lsb_str: str) -> RangeExpression:
        msb_simplified, msb_val = ExpressionSimplifier.simplify_numeric_parts(msb_str)
        lsb_simplified, lsb_val = ExpressionSimplifier.simplify_numeric_parts(lsb_str)
        
        return RangeExpression(
            msb_expr=msb_simplified,
            lsb_expr=lsb_simplified,
            msb_value=msb_val,
            lsb_value=lsb_val
        )

class ASTVisitor(ABC):
    
    def visit(self, node: BaseASTNode) -> Any:
        method_name = f"visit_{node.node_type.lower()}"
        visitor_method = getattr(self, method_name, self.generic_visit)
        return visitor_method(node)
    
    def visit_designunit(self, node: DesignUnit) -> Any:
        return self.generic_visit(node)
    def visit_moduledeclaration(self, node: ModuleDeclaration) -> Any:
        return self.generic_visit(node)
        
    def visit_parameterdeclaration(self, node: ParameterDeclaration) -> Any:
        return self.generic_visit(node)
        
    def visit_portdeclaration(self, node: PortDeclaration) -> Any:
        return self.generic_visit(node)
        
    def visit_identifier(self, node: Identifier) -> Any:
        return self.generic_visit(node)
        
    def visit_numericliteral(self, node: NumericLiteral) -> Any:
        return self.generic_visit(node)
        
    def visit_stringliteral(self, node: StringLiteral) -> Any:
        return self.generic_visit(node)
        
    def visit_errornode(self, node: ErrorNode) -> Any:
        return self.generic_visit(node)
        
    def generic_visit(self, node: BaseASTNode) -> Any:
        for child in node.children:
            self.visit(child)

class ModuleInfoExtractor(ASTVisitor):
    
    def __init__(self):
        self.module_info: Optional[ModuleInfo] = None
        
    def extract_module_info(self, ast:DesignUnit) -> Optional[ModuleInfo]:
        self.module_info = None
        self.visit(ast)
        return self.module_info
        
    def get_module_name(self, ast: DesignUnit) -> Optional[str]:
        info = self.extract_module_info(ast)
        return info.name if info else None
        
    def get_module_ports(self, ast: DesignUnit) -> List[PortInfo]:
        info = self.extract_module_info(ast)
        return info.ports if info else []
        
    def get_module_parameters(self, ast: DesignUnit) -> List[ParameterInfo]:
        info = self.extract_module_info(ast)
        return info.parameters if info else []
        
    def visit_moduledeclaration(self, node: ModuleDeclaration) -> Any:
        if self.module_info is None:
            self.module_info = node.to_info()
        return self.generic_visit(node)


class CodeGenerator(ASTVisitor):
    
    def __init__(self):
        self.indent_level = 0
        self.output_lines: List[str] = []
    def generate_module_header(self, module: ModuleDeclaration) -> str:
        lines = []
        if module.parameters:
            lines.append(f"module {module.module_name} #(")
            param_lines = []
            for param in module.parameters:
                param_str = f"    {param.parameter_type} {param.identifier}"
                if param.default_value and param.default_value.value:
                    param_str += f" = {param.default_value.value}"
                param_lines.append(param_str)
            lines.append(",\n".join(param_lines))
            lines.append(") (")
        else:
            lines.append(f"module {module.module_name} (")
        if module.ports:
            port_lines = []
            for port in module.ports:
                port_str = f"    {port.direction} "
                if port.net_type != "wire": 
                    port_str += f"{port.net_type} "
                if port.range_expr:
                    port_str += f"[{port.range_expr.msb_expr}:{port.range_expr.lsb_expr}] "
                port_str += port.identifier
                port_lines.append(port_str)
            lines.append(",\n".join(port_lines))
        lines.append(");")
        return "\n".join(lines)
        
    def generate_port_list(self, ports: List[PortDeclaration]) -> str:
        if not ports:
            return ""
            
        port_lines = []
        for port in ports:
            port_str = f"{port.direction} "
            if port.net_type != "wire":
                port_str += f"{port.net_type} "
            if port.range_expr:
                port_str += f"[{port.range_expr.msb_expr}:{port.range_expr.lsb_expr}] "
            port_str += port.identifier
            port_lines.append(port_str)
            
        return ",\n    ".join(port_lines)

class VerilogAST:
    def __init__(self, root: DesignUnit):
        self.root = root
        self._info_extractor = ModuleInfoExtractor()
        self._cached_module_info: Optional[ModuleInfo] = None
        
    def _get_module_info(self) -> Optional[ModuleInfo]:
        if self._cached_module_info is None:
            self._cached_module_info = self._info_extractor.extract_module_info(self.root)
        return self._cached_module_info
        
    def invalidate_cache(self) -> None:
        self._cached_module_info = None
    def get_module_name(self) -> Optional[str]:
        info = self._get_module_info()
        return info.name if info else None
        
    def get_module_ports(self) -> List[PortInfo]:
        info = self._get_module_info()
        return info.ports if info else []
        
    def get_module_parameters(self) -> List[ParameterInfo]:
        info = self._get_module_info()
        return info.parameters if info else []
    
    def get_input_ports(self) -> List[PortInfo]:
        return [port for port in self.get_module_ports() 
                if port.direction == PortDirection.INPUT.value]
        
    def get_output_ports(self) -> List[PortInfo]:
        return [port for port in self.get_module_ports() 
                if port.direction == PortDirection.OUTPUT.value]
        
    def get_inout_ports(self) -> List[PortInfo]:
        return [port for port in self.get_module_ports() 
                if port.direction == PortDirection.INOUT.value]

    def find_port_by_name(self, name: str) -> Optional[PortInfo]:
        for port in self.get_module_ports():
            if port.name == name:
                return port
        return None
        
    def find_parameter_by_name(self, name: str) -> Optional[ParameterInfo]:
        for param in self.get_module_parameters():
            if param.name == name:
                return param
        return None
        
    def get_port_count(self) -> Dict[str, int]:
        ports = self.get_module_ports()
        return {
            "total": len(ports),
            "input": len([p for p in ports if p.direction == PortDirection.INPUT.value]),
            "output": len([p for p in ports if p.direction == PortDirection.OUTPUT.value]),
            "inout": len([p for p in ports if p.direction == PortDirection.INOUT.value])
        }
        
    def has_parameters(self) -> bool:
        return len(self.get_module_parameters()) > 0
        
    def is_body_ignored(self) -> bool:
        info = self._get_module_info()
        return info.body_ignored if info else True

class ASTBuilder:
    
    def __init__(self):
        self.current_module: Optional[ModuleDeclaration] = None
        
    def create_design_unit(self) -> DesignUnit:
        return DesignUnit()
        
    def create_module_declaration(self, name: str, **kwargs) -> ModuleDeclaration:
        module = ModuleDeclaration(name, **kwargs)
        self.current_module = module
        return module
        
    def create_parameter(self, identifier: str, parameter_type: str = "parameter", 
                        default_value: str = "", data_type: Optional[str] = None, 
                        **kwargs) -> ParameterDeclaration:
        default_expr = StringLiteral(default_value) if default_value else None
        return ParameterDeclaration(
            identifier=identifier,
            parameter_type=parameter_type,
            default_value=default_expr,
            data_type=data_type,
            **kwargs
        )
        
    def create_port(self, identifier: str, direction: str, net_type: str = "wire",msb_expr: Optional[str] = None, lsb_expr: Optional[str] = None,
                   **kwargs) -> PortDeclaration:
        range_expr = None
        if msb_expr is not None and lsb_expr is not None:
            range_expr = ExpressionSimplifier.create_range_expression(msb_expr, lsb_expr)
        return PortDeclaration(
            identifier=identifier,
            direction=direction,
            net_type=net_type,
            range_expr=range_expr,
            **kwargs
        )
        
    def add_parameter(self, module: ModuleDeclaration, 
                     param: ParameterDeclaration) -> None:
        module.add_parameter(param)
        
    def add_port(self, module: ModuleDeclaration, 
                port: PortDeclaration) -> None:
        module.add_port(port)
        
    def set_body_ignored(self, module: ModuleDeclaration) -> None:
        module.body_placeholder = True
        
    def create_error_node(self, error_message: str, 
                         recovery_point: str = "", **kwargs) -> ErrorNode:
        return ErrorNode(error_message, recovery_point, **kwargs)

class VerilogASTError(Exception):
    pass


class NodeNotFoundError(VerilogASTError):
    pass


class InvalidNodeTypeError(VerilogASTError):
    pass

def create_sample_ast() -> VerilogAST:
    builder = ASTBuilder()
    
    design_unit = builder.create_design_unit()
    
    module = builder.create_module_declaration("test_module")
    
    width_param = builder.create_parameter("WIDTH", "parameter", "8")
    depth_param = builder.create_parameter("DEPTH", "parameter", "16")
    builder.add_parameter(module, width_param)
    builder.add_parameter(module, depth_param)
    
    clk_port = builder.create_port("clk", "input", "wire")
    rst_port = builder.create_port("rst_n", "input", "wire")
    data_in_port = builder.create_port("data_in", "input", "wire", "WIDTH-1", "0")
    data_out_port = builder.create_port("data_out", "output", "reg", "3", "0")
    valid_port = builder.create_port("valid", "output", "wire")
    
    builder.add_port(module, clk_port)
    builder.add_port(module, rst_port)
    builder.add_port(module, data_in_port)
    builder.add_port(module, data_out_port)
    builder.add_port(module, valid_port)
    
    builder.set_body_ignored(module)
    
    design_unit.add_module(module)
    
    return VerilogAST(design_unit)


if __name__ == "__main__":
    ast = create_sample_ast()
    
    print(f"module name : {ast.get_module_name()}")
    print(f"Ports counts: {ast.get_port_count()}")
    print(f"Has parameter: {ast.has_parameters()}")
    print(f"body is ignore: {ast.is_body_ignored()}")
    
    print("\n=== All ports ===")
    for port in ast.get_module_ports():
        width_info = f"[{port.width}]" if port.is_vector else ""
        print(f"{port.direction} {port.net_type} {width_info} {port.name}")
    
    print("\n=== All Parameters ===")
    for param in ast.get_module_parameters():
        print(f"{param.param_type} {param.name} = {param.default_value}")
    
    clk_port = ast.find_port_by_name("clk")
    if clk_port:
        print(f"\nclk ports: {clk_port.name} ({clk_port.direction})")
    
    width_param = ast.find_parameter_by_name("WIDTH")
    if width_param:
        print(f"find width: {width_param.name} = {width_param.default_value}")
    
