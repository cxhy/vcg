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
#┌─────────────────────────────────────────────────────────┐
#│                    PLY Parser Layer                     │
#└────────────────────┬────────────────────────────────────┘
#                     │
#                     ▼
#┌─────────────────────────────────────────────────────────┐
#│              VerilogASTBuilder                          │
#│  ┌─────────────────┐      ┌──────────────────┐          │
#│  │ PortDeclaration │      │ ParameterInfo    │          │
#│  └─────────────────┘      └──────────────────┘          │
#└────────────────────┬────────────────────────────────────┘
#                     │ build()
#                     ▼
#              ┌─────────────┐
#              │ PortFactory │ 
#              └─────────────┘
#                     │
#                     ▼
#┌─────────────────────────────────────────────────────────┐
#│                   VerilogAST                            │
#│  ┌──────────────────┐      ┌──────────────────┐         │
#│  │  PortManager     │      │ ParameterManager │         │
#│  │  (PortInfo)      │      │ (ParameterInfo)  │         │
#│  └──────────────────┘      └──────────────────┘         │
#└─────────────────────────────────────────────────────────┘

from typing import List, Optional, Any, Dict, Union
from dataclasses import dataclass, field, fields, replace
from enum import Enum
import re
from sympy import sympify, simplify

from .vcg_logger import get_vcg_logger

_logger = get_vcg_logger('VerilogAST.Calculator')

class PortDirection(Enum):
    INPUT = "input"
    OUTPUT = "output" 
    INOUT = "inout"

class PortType(Enum):
    SIMPLE = "simple"           # 单bit端口
    VECTOR = "vector"          # 向量端口 [msb:lsb]
    ARRAY_2D = "array_2d"     # 二维数组
    ARRAY_3D = "array_3d"     # 三维数组
    INTERFACE = "interface"    # 接口端口(预留)

class ExpressionCalculator:
    
    def __init__(self):
        self.patterns = {
            'token': re.compile(r'(\$[a-zA-Z_]\w*\([^)]*\)|\d+\.?\d*|\w+|[+\-*/()])')
        }
    def parse_width_expression(self, expr: str) -> Union[int, str, float]:
        if not expr or not expr.strip():
            return 0
        
        return self._sympy_parse(expr.strip())
    
    def _sympy_parse(self, expr: str) -> Union[int, str, float]:
        try:
            processed, mapping = self._handle_dollar_funcs(expr)
            result = simplify(sympify(processed))
            return self._format_result(result, mapping)
        except Exception as e:
            _logger.debug(
                "sympy parse failed for expr=%r (type=%s): %s",
                expr, type(e).__name__, e
            )
            return expr
    
    def _handle_dollar_funcs(self, expr: str) -> tuple[str, dict]:
        mapping = {}
        counter = 0
        
        def replace_func(match):
            nonlocal counter
            symbol = f"D{counter}"
            mapping[symbol] = match.group(0)
            counter += 1
            return symbol
        processed = re.sub(r'\$\w+\([^)]*\)', replace_func, expr)
        return processed, mapping
    
    def _format_result(self, result, mapping: dict) -> Union[int, str, float]:
        if result.is_number:
            val = float(result)
            return int(val) if val == int(val) else val
        
        result_str = str(result)
        for symbol, func in mapping.items():
            result_str = result_str.replace(symbol, func)
        
        return result_str.replace(' ', '')

_calculator = ExpressionCalculator()

@dataclass(frozen=True)
class PortDeclaration:
    """端口声明

    Note:
        frozen=True 禁止字段重新赋值。array_dims 字段保留 List[str] 以维持
        对外签名与字面赋值语义，请不要 in-place mutate 该列表——
        Builder 在 add_port 中使用 dataclasses.replace 创建新对象。
    """
    name: str
    direction: Optional[str] = None
    net_type: Optional[str] = None
    msb_expr: Optional[str] = None
    lsb_expr: Optional[str] = None
    array_dims: List[str] = field(default_factory=list)
    interface_type: Optional[str] = None

@dataclass(frozen=True)
class PortInfo:
    """端口信息

    Note:
        frozen=True 禁止字段重新赋值。array_dims 字段保留 List[str]；
        外部不应 in-place mutate 该列表。
    """
    name: str
    direction: Optional[str] = None
    net_type: Optional[str] = None
    msb_expr: Optional[str] = None
    lsb_expr: Optional[str] = None
    array_dims: List[str] = field(default_factory=list)
    interface_type: Optional[str] = None
    
    @property
    def port_type(self) -> PortType:
        if self.interface_type:
            return PortType.INTERFACE
        elif self.array_dims:
            return PortType.ARRAY_3D if len(self.array_dims) >= 3 else PortType.ARRAY_2D
        elif self.msb_expr and self.lsb_expr:
            return PortType.VECTOR
        else:
            return PortType.SIMPLE
    
    @property
    def is_complete(self) -> bool:
        return self.direction is not None
    
    @property
    def width(self) -> Union[int, str, float]:
        if self.port_type == PortType.SIMPLE:
            return 1
        elif self.port_type == PortType.VECTOR:
            return self._calculate_vector_width()
        else:
            return "array"
    
    def _calculate_vector_width(self) -> Union[int, str, float]:
        if not self.msb_expr or not self.lsb_expr:
            return 1
        
        msb_val = _calculator.parse_width_expression(self.msb_expr)
        lsb_val = _calculator.parse_width_expression(self.lsb_expr)
        
        if isinstance(msb_val, int) and isinstance(lsb_val, int):
            return abs(msb_val - lsb_val) + 1

        width_expr = f"({msb_val})-({lsb_val})+1"
        return _calculator.parse_width_expression(width_expr)
    
    @property
    def range_string(self) -> str:
        if self.port_type == PortType.VECTOR:
            return f"[{self.msb_expr}:{self.lsb_expr}]"
        elif self.array_dims:
            base_range = f"[{self.msb_expr}:{self.lsb_expr}]" if self.msb_expr else ""
            array_range = "".join(f"[{dim}]" for dim in self.array_dims)
            return f"{base_range}{array_range}".strip()
        else:
            return ""


@dataclass(frozen=True)
class ParameterInfo:
    """参数信息"""
    name: str
    param_type: str = "parameter"
    default_value: str = ""
    data_type: Optional[str] = None

class PortFactory:
    
    @staticmethod
    def to_info(decl: PortDeclaration) -> PortInfo:
        """将Declaration转换为Info（唯一方法）
        
        这是PLY场景的核心需求：
        - Builder阶段收集Declaration
        - build()时转换为Info
        
        Args:
            decl: 端口声明对象
            
        Returns:
            PortInfo: 端口信息对象
        """
        return PortInfo(
            name=decl.name,
            direction=decl.direction,
            net_type=decl.net_type or "wire",  
            msb_expr=decl.msb_expr,
            lsb_expr=decl.lsb_expr,
            array_dims=decl.array_dims.copy() if decl.array_dims else [],
            interface_type=decl.interface_type
        )

class ParameterManager:
    """参数管理器"""
    def __init__(self):
        self._parameters: Dict[str, ParameterInfo] = {}
        self._parameter_order: List[str] = []
    
    def add_parameter(self, param_name: str, **kwargs) -> None:
        if param_name not in self._parameters:
            self._parameter_order.append(param_name)

        self._parameters[param_name] = ParameterInfo(
            name=param_name,
            param_type=kwargs.get('param_type', 'parameter'),
            default_value=kwargs.get('default_value', ''),
            data_type=kwargs.get('data_type')
        )

    def add_parameter_info(self, param_info: ParameterInfo) -> None:
        if param_info.name not in self._parameters:
            self._parameter_order.append(param_info.name)
        self._parameters[param_info.name] = param_info

    def get_all_parameters(self) -> List[ParameterInfo]:
        return [self._parameters[name] for name in self._parameter_order]

class PortManager:
    def __init__(self):
        self._ports: Dict[str, PortInfo] = {}
        self._port_order: List[str] = []
    
    def add_port_info(self, port_info: PortInfo) -> None:
        if port_info.name not in self._ports:
            self._port_order.append(port_info.name)
        self._ports[port_info.name] = port_info
    
    def get_all_ports(self) -> List[PortInfo]:
        return [self._ports[name] for name in self._port_order]

class VerilogASTBuilder:
    """AST构建器"""
    
    def __init__(self):
        self._module_name: Optional[str] = None
        self._parameters: Dict[str, ParameterInfo] = {}
        self._parameter_order: List[str] = []
        self._port_decls: Dict[str, PortDeclaration] = {}
        self._port_order: List[str] = []
        self._built: bool = False
    
    def set_module_name(self, name: str) -> 'VerilogASTBuilder':
        if self._module_name is not None:
            raise ValueError(f"Module name already set: {self._module_name}")
        self._module_name = name
        return self
    
    def add_parameter(self, name: str, **kwargs) -> 'VerilogASTBuilder':
        if name not in self._parameters:
            self._parameter_order.append(name)
        
        self._parameters[name] = ParameterInfo(
            name=name,
            param_type=kwargs.get('param_type', 'parameter'),
            default_value=kwargs.get('default_value', ''),
            data_type=kwargs.get('data_type')
        )
        return self
    
    def add_port(self, name: str, **kwargs) -> 'VerilogASTBuilder':
        if name not in self._port_decls:
            self._port_order.append(name)
            self._port_decls[name] = PortDeclaration(name=name)

        decl = self._port_decls[name]
        allowed = {f.name for f in fields(decl)}
        update = {
            key: value
            for key, value in kwargs.items()
            if value is not None and key in allowed
        }
        if update:
            self._port_decls[name] = replace(decl, **update)

        return self
    
    def update_port(self, name: str, **kwargs) -> 'VerilogASTBuilder':
        return self.add_port(name, **kwargs)
    
    def build(self) -> 'VerilogAST':
        if self._built:
            raise VerilogASTError("Builder already built")
        
        if not self._module_name:
            raise VerilogASTError("Module name not set")
        
        ast = VerilogAST(self._module_name)
        
        for name in self._parameter_order:
            ast.parameter_manager.add_parameter_info(self._parameters[name])
        
        for name in self._port_order:
            decl = self._port_decls[name]
            port_info = PortFactory.to_info(decl)
            ast.port_manager.add_port_info(port_info)
        
        self._built = True
        return ast
    
    def reset(self) -> 'VerilogASTBuilder':
        self._module_name = None
        self._parameters.clear()
        self._parameter_order.clear()
        self._port_decls.clear()
        self._port_order.clear()
        self._built = False
        return self

class VerilogAST:
    """Verilog AST"""
    def __init__(self, module_name: str = ""):
        self.module_name = module_name
        self.parameter_manager = ParameterManager()
        self.port_manager = PortManager()
    def get_port_info(self) -> List[PortInfo]:
        return self.port_manager.get_all_ports()
    
    def get_parameter_info(self) -> List[ParameterInfo]:
        return self.parameter_manager.get_all_parameters()
    
    def get_module_info(self) -> Dict[str, Any]:
        """获取完整的模块信息
        
        返回包含模块名、参数、端口和统计信息的字典
        
        Returns:
            Dict包含:
            - name: 模块名
            - parameters: 参数列表
            - ports: 端口列表
            - port_summary: 端口统计信息
        """
        return {
            "name": self.module_name,
            "parameters": self.get_parameter_info(),
            "ports": self.get_port_info(),
            "port_summary": self._get_port_summary()
        }
    def _get_port_summary(self) -> Dict[str, int]:
        ports = self.get_port_info()
        summary = {
            "total": len(ports),
            "input": 0,
            "output": 0,
            "inout": 0
        }
        
        for port in ports:
            if port.direction:
                direction = port.direction.lower()
                if direction in summary:
                    summary[direction] += 1
        
        return summary
    
    def __repr__(self) -> str:
        """字符串表示"""
        return (f"VerilogAST(module={self.module_name}, "
                f"params={len(self.get_parameter_info())}, "
                f"ports={len(self.get_port_info())})")

class VerilogASTError(Exception):
    """Verilog AST异常基类"""
    pass

class PortNotFoundError(VerilogASTError):
    """端口未找到异常"""
    pass

class ParameterNotFoundError(VerilogASTError):
    """参数未找到异常"""
    pass

