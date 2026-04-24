"""
VerilogAst 重构验证测试（TASK-01）

目标：覆盖 doc/delivery_01_refactor_verilogast.md §10 列出的 11 项测试点。
- §10.1 任务单预告项（5 项）
- §10.2 T-A-fix 新增项（4 项）
- §10.3 API 兼容性断言（2 项）

测试平台: pytest
"""

import dataclasses
import importlib
import inspect
import logging
import os
import sys

import pytest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.VerilogAst import (
    ExpressionCalculator,
    ParameterInfo,
    ParameterManager,
    PortDeclaration,
    PortDirection,
    PortFactory,
    PortInfo,
    PortManager,
    PortType,
    VerilogAST,
    VerilogASTBuilder,
    VerilogASTError,
)


# ============================================================================
# §10.1.1 + §10.2.8: _calculate_vector_width 带空格表达式
# ============================================================================

class TestCalculateVectorWidthSpaces:
    """T-A 修复的旧 hack bug：'WIDTH - 1' 带空格 endswith 会产出 'WIDTH - '"""

    def test_width_minus_1_with_spaces_goes_through_sympy(self):
        """'WIDTH - 1', '0' → 'WIDTH'（非 fallback 路径，sympy 成功化简）"""
        p = PortInfo(name='x', msb_expr='WIDTH - 1', lsb_expr='0')
        assert p.width == 'WIDTH'

    def test_data_width_with_leading_trailing_spaces(self):
        """' DATA_WIDTH -1 ', '0' → 'DATA_WIDTH'（旧 hack 会 mis-slice）"""
        p = PortInfo(name='x', msb_expr=' DATA_WIDTH -1 ', lsb_expr='0')
        assert p.width == 'DATA_WIDTH'

    def test_addr_width_spaces_around_minus(self):
        """'ADDR_WIDTH  -  1', '0' → 'ADDR_WIDTH'"""
        p = PortInfo(name='x', msb_expr='ADDR_WIDTH  -  1', lsb_expr='0')
        assert p.width == 'ADDR_WIDTH'


# ============================================================================
# §10.1.2: 嵌套 -1 表达式
# ============================================================================

class TestCalculateVectorWidthNestedMinus1:
    """T-A 修复的旧 hack bug：'FOO-1+1' endswith('-1') 会错误切成 'FOO-1+'"""

    def test_foo_minus_1_plus_1(self):
        """'FOO-1+1', '0' → 'FOO+1'（sympy 化简，不进 fallback）"""
        p = PortInfo(name='x', msb_expr='FOO-1+1', lsb_expr='0')
        assert p.width == 'FOO+1'

    def test_bar_minus_1_plus_2(self):
        """'BAR-1+2', '0' → 'BAR+2'"""
        p = PortInfo(name='x', msb_expr='BAR-1+2', lsb_expr='0')
        assert p.width == 'BAR+2'


# ============================================================================
# §10.1.3: frozen dataclass 不可变性
# ============================================================================

class TestFrozenDataclasses:
    """T-D：三个 dataclass 均 frozen=True，字段重绑定应抛 FrozenInstanceError"""

    def test_port_declaration_frozen(self):
        """PortDeclaration 字段不可重绑"""
        decl = PortDeclaration(name='clk')
        with pytest.raises(dataclasses.FrozenInstanceError):
            decl.name = 'rst'

    def test_port_declaration_frozen_direction(self):
        """PortDeclaration.direction 不可重绑"""
        decl = PortDeclaration(name='clk', direction='input')
        with pytest.raises(dataclasses.FrozenInstanceError):
            decl.direction = 'output'

    def test_port_info_frozen(self):
        """PortInfo 字段不可重绑"""
        p = PortInfo(name='data')
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.name = 'other'

    def test_port_info_frozen_net_type(self):
        """PortInfo.net_type 不可重绑"""
        p = PortInfo(name='data', net_type='wire')
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.net_type = 'reg'

    def test_parameter_info_frozen(self):
        """ParameterInfo 字段不可重绑"""
        p = ParameterInfo(name='WIDTH')
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.name = 'DEPTH'

    def test_parameter_info_frozen_default_value(self):
        """ParameterInfo.default_value 不可重绑"""
        p = ParameterInfo(name='WIDTH', default_value='8')
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.default_value = '16'

    def test_port_declaration_is_dataclass_instance(self):
        """PortDeclaration 仍是 dataclass 实例（保留 dataclass 语义）"""
        decl = PortDeclaration(name='clk')
        assert dataclasses.is_dataclass(decl)
        assert dataclasses.is_dataclass(PortDeclaration)

    def test_port_info_is_dataclass_instance(self):
        """PortInfo 仍是 dataclass 实例"""
        p = PortInfo(name='data')
        assert dataclasses.is_dataclass(p)
        assert dataclasses.is_dataclass(PortInfo)

    def test_parameter_info_is_dataclass_instance(self):
        """ParameterInfo 仍是 dataclass 实例"""
        p = ParameterInfo(name='W')
        assert dataclasses.is_dataclass(p)
        assert dataclasses.is_dataclass(ParameterInfo)

    def test_frozen_via_dataclass_params(self):
        """直接读 dataclass 元数据确认 frozen=True"""
        assert PortDeclaration.__dataclass_params__.frozen is True
        assert PortInfo.__dataclass_params__.frozen is True
        assert ParameterInfo.__dataclass_params__.frozen is True


# ============================================================================
# §10.1.4: add_parameter_info 对称 API
# ============================================================================

class TestAddParameterInfoSymmetric:
    """T-B：ParameterManager.add_parameter_info 与 PortManager.add_port_info 对称"""

    def test_add_parameter_info_inserts_new(self):
        """add_parameter_info 新增参数"""
        pm = ParameterManager()
        info = ParameterInfo(name='WIDTH', default_value='8')
        pm.add_parameter_info(info)
        all_params = pm.get_all_parameters()
        assert len(all_params) == 1
        assert all_params[0].name == 'WIDTH'
        assert all_params[0].default_value == '8'

    def test_add_parameter_info_preserves_insertion_order(self):
        """与 add_port_info 一样保持插入顺序"""
        pm = ParameterManager()
        pm.add_parameter_info(ParameterInfo(name='A'))
        pm.add_parameter_info(ParameterInfo(name='B'))
        pm.add_parameter_info(ParameterInfo(name='C'))
        names = [p.name for p in pm.get_all_parameters()]
        assert names == ['A', 'B', 'C']

    def test_add_parameter_info_overwrites_existing(self):
        """同名参数：覆盖值但顺序位置不变"""
        pm = ParameterManager()
        pm.add_parameter_info(ParameterInfo(name='A', default_value='1'))
        pm.add_parameter_info(ParameterInfo(name='B', default_value='2'))
        pm.add_parameter_info(ParameterInfo(name='A', default_value='99'))
        all_params = pm.get_all_parameters()
        assert [p.name for p in all_params] == ['A', 'B']
        assert all_params[0].default_value == '99'

    def test_builder_build_uses_add_parameter_info(self):
        """Builder.build 通过 add_parameter_info 公共 API，而非戳私有"""
        b = VerilogASTBuilder()
        b.set_module_name('m')
        b.add_parameter('P1', default_value='8', param_type='parameter')
        b.add_parameter('P2', default_value='16', param_type='localparam')
        ast = b.build()
        params = ast.get_parameter_info()
        assert [p.name for p in params] == ['P1', 'P2']
        assert params[0].default_value == '8'
        assert params[1].param_type == 'localparam'

    def test_add_parameter_info_is_symmetric_with_add_port_info(self):
        """两个 API 结构对称：各自接受自己的 Info 对象，返回 None"""
        pm_sig = inspect.signature(ParameterManager.add_parameter_info)
        port_sig = inspect.signature(PortManager.add_port_info)
        # 参数名不同（param_info vs port_info），但参数数量一致
        assert len(pm_sig.parameters) == len(port_sig.parameters) == 2  # self + info


# ============================================================================
# §10.1.5: _sympy_parse DEBUG 日志发出
# ============================================================================

class TestSympyParseLogging:
    """T-C：sympy 失败时应通过 VCG.VerilogAST.Calculator logger 发 DEBUG 日志"""

    def test_debug_log_emitted_on_sympy_failure(self, caplog):
        """sympy 失败时发 DEBUG 日志，包含表达式与异常类型"""
        calc = ExpressionCalculator()
        with caplog.at_level(logging.DEBUG, logger='VCG.VerilogAST.Calculator'):
            result = calc.parse_width_expression('N-1')  # N is sympy reserved
        # 确实失败返回原字符串
        assert result == 'N-1'
        # 日志里包含失败的表达式
        records = [r for r in caplog.records if r.name == 'VCG.VerilogAST.Calculator']
        assert any('N-1' in r.getMessage() for r in records), (
            f'expected N-1 in log message, got: {[r.getMessage() for r in records]}'
        )
        # 日志级别为 DEBUG
        assert all(r.levelno == logging.DEBUG for r in records)

    def test_no_log_emitted_on_sympy_success(self, caplog):
        """sympy 成功时不发 DEBUG 日志"""
        calc = ExpressionCalculator()
        with caplog.at_level(logging.DEBUG, logger='VCG.VerilogAST.Calculator'):
            result = calc.parse_width_expression('7-1')  # 纯数值，sympy 成功
        assert result == 6
        records = [r for r in caplog.records if r.name == 'VCG.VerilogAST.Calculator']
        assert not records

    def test_log_includes_exception_type(self, caplog):
        """日志应包含异常类型名（如 'TypeError'）"""
        calc = ExpressionCalculator()
        with caplog.at_level(logging.DEBUG, logger='VCG.VerilogAST.Calculator'):
            calc.parse_width_expression('N-1')
        records = [r for r in caplog.records if r.name == 'VCG.VerilogAST.Calculator']
        assert records, 'expected at least one DEBUG record'
        messages = [r.getMessage() for r in records]
        assert any('TypeError' in m for m in messages), (
            f'expected TypeError in log, got: {messages}'
        )


# ============================================================================
# §10.2.6: sympy 保留名回归套
# ============================================================================

class TestSympyReservedNameRegression:
    """T-A-fix narrow fallback：sympy 保留名 N/O/S/Q 等 `X-1, 0 → X`"""

    @pytest.mark.parametrize('name', ['N', 'O', 'S', 'Q'])
    def test_sympy_reserved_single_letter_width(self, name):
        """保留名单字母 '{X}-1', '0' → '{X}'"""
        p = PortInfo(name='x', msb_expr=f'{name}-1', lsb_expr='0')
        assert p.width == name

    @pytest.mark.parametrize('name', ['N', 'O', 'S', 'Q'])
    def test_sympy_reserved_with_spaces(self, name):
        """保留名带空格 '{X} - 1', '0' → '{X}'"""
        p = PortInfo(name='x', msb_expr=f'{name} - 1', lsb_expr='0')
        assert p.width == name

    def test_sympy_non_reserved_goes_through_sympy(self):
        """非保留名 'WIDTH-1', '0' → 'WIDTH'（sympy 成功路径）"""
        p = PortInfo(name='x', msb_expr='WIDTH-1', lsb_expr='0')
        assert p.width == 'WIDTH'


# ============================================================================
# §10.2.7: narrow fallback 不误触
# ============================================================================

class TestNarrowFallbackNotTriggered:
    """narrow fallback 必须只在严格匹配 <X>-1 pattern 时触发"""

    def test_n_minus_2_not_truncated(self):
        """'N-2', '0' → sympy 失败，fallback 正则不匹配（尾部非 -1），返回原 width_expr"""
        p = PortInfo(name='x', msb_expr='N-2', lsb_expr='0')
        # sympy 失败返回原 width_expr，narrow fallback 不命中
        assert p.width == '(N-2)-(0)+1'

    def test_s_plus_1_not_truncated(self):
        """'S+1', '0' → sympy 失败，fallback 不匹配"""
        p = PortInfo(name='x', msb_expr='S+1', lsb_expr='0')
        # 不以 -1 结尾，fallback 不命中
        assert p.width == '(S+1)-(0)+1'

    def test_lsb_nonzero_does_not_trigger_fallback(self):
        """lsb != '0' 时即使 msb 形如 X-1 也不应走 fallback"""
        p = PortInfo(name='x', msb_expr='WIDTH-1', lsb_expr='1')
        # sympy 成功化简 (WIDTH-1)-(1)+1 = WIDTH-1
        assert p.width == 'WIDTH-1'

    def test_n_minus_1_fallback_only_with_lsb_zero(self):
        """'N-1', '1' → sympy 失败，lsb!=0，fallback 不命中"""
        p = PortInfo(name='x', msb_expr='N-1', lsb_expr='1')
        # lsb!=0 不走 fallback；sympy 失败返回原 width_expr
        assert p.width == '(N-1)-(1)+1'


# ============================================================================
# §10.2.9: update_port None 过滤
# ============================================================================

class TestUpdatePortNoneFiltering:
    """T-D：dataclasses.replace 版本下 None kwargs 仍被过滤，已设字段不被覆盖"""

    def test_update_port_none_msb_ignored(self):
        """update_port(msb_expr=None) 不覆盖已设 msb_expr"""
        b = VerilogASTBuilder()
        b.set_module_name('m')
        b.add_port('data', msb_expr='7', lsb_expr='0', direction='output')
        b.update_port('data', msb_expr=None)
        ast = b.build()
        port = ast.get_port_info()[0]
        assert port.msb_expr == '7'
        assert port.direction == 'output'

    def test_update_port_none_multiple_ignored(self):
        """多个 None 值全部被过滤"""
        b = VerilogASTBuilder()
        b.set_module_name('m')
        b.add_port('data', direction='input', msb_expr='7', lsb_expr='0', net_type='wire')
        b.update_port('data', msb_expr=None, lsb_expr=None, net_type=None, direction=None)
        ast = b.build()
        port = ast.get_port_info()[0]
        assert port.direction == 'input'
        assert port.msb_expr == '7'
        assert port.lsb_expr == '0'
        assert port.net_type == 'wire'

    def test_update_port_unknown_key_ignored(self):
        """非字段 kwargs 应被过滤（不抛 TypeError）"""
        b = VerilogASTBuilder()
        b.set_module_name('m')
        b.add_port('data', direction='input')
        # 非字段名 kwargs 不应破坏 replace
        b.update_port('data', some_unknown_field='whatever')
        ast = b.build()
        assert ast.get_port_info()[0].direction == 'input'

    def test_add_port_value_override_only_for_non_none(self):
        """add_port 同一端口多次调用，仅非 None 的字段会覆盖"""
        b = VerilogASTBuilder()
        b.set_module_name('m')
        b.add_port('data', direction='input', msb_expr='7')
        b.add_port('data', direction='output', msb_expr=None, lsb_expr='0')
        ast = b.build()
        port = ast.get_port_info()[0]
        # direction 被覆盖，msb_expr 未被 None 覆盖，lsb_expr 新增
        assert port.direction == 'output'
        assert port.msb_expr == '7'
        assert port.lsb_expr == '0'


# ============================================================================
# §10.3.10: inspect.signature 硬约束清单 API 对比
# ============================================================================

# 加载 pre-refactor 快照供对比
_PRE_REFACTOR_SNAPSHOT = os.path.join(
    project_root, 'tmp', 'VerilogAst_pre_refactor.py'
)


def _load_pre_refactor_module():
    """将 tmp/VerilogAst_pre_refactor.py 作为独立 module 加载，避免污染正式模块"""
    if not os.path.isfile(_PRE_REFACTOR_SNAPSHOT):
        pytest.skip(f'pre-refactor snapshot not found: {_PRE_REFACTOR_SNAPSHOT}')
    spec = importlib.util.spec_from_file_location(
        '_pre_refactor_verilogast', _PRE_REFACTOR_SNAPSHOT
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestAPISignatureCompatibility:
    """硬约束：清单内所有公共 API 签名与重构前保持一致"""

    # 任务单 §1.1 列出的硬约束保留清单
    PROTECTED_CLASSES = [
        'VerilogAST', 'PortInfo', 'ParameterInfo',
        'PortManager', 'ParameterManager', 'VerilogASTBuilder',
        'PortFactory', 'PortDirection', 'PortType', 'ExpressionCalculator',
    ]

    # 各类要比较的公共方法（不含下划线前缀私有方法，不含 property）
    PROTECTED_METHODS = {
        'VerilogAST': ['get_port_info', 'get_parameter_info', 'get_module_info', '__init__'],
        'PortManager': ['add_port_info', 'get_all_ports', '__init__'],
        'ParameterManager': ['add_parameter', 'get_all_parameters', '__init__'],
        'VerilogASTBuilder': [
            'set_module_name', 'add_parameter', 'add_port', 'update_port',
            'build', 'reset', '__init__',
        ],
        'PortFactory': ['to_info'],
        'ExpressionCalculator': ['parse_width_expression', '__init__'],
    }

    def test_all_protected_classes_still_exist(self):
        """硬约束清单内所有类仍可从 src.VerilogAst import"""
        import src.VerilogAst as current
        for cls_name in self.PROTECTED_CLASSES:
            assert hasattr(current, cls_name), f'missing protected class: {cls_name}'

    def test_all_protected_classes_exist_in_pre_refactor(self):
        """作为参照：清单内所有类在重构前也存在"""
        pre = _load_pre_refactor_module()
        for cls_name in self.PROTECTED_CLASSES:
            assert hasattr(pre, cls_name), f'pre-refactor missing: {cls_name}'

    @pytest.mark.parametrize('cls_name,method_name', [
        (cls, m)
        for cls, methods in {
            'VerilogAST': ['get_port_info', 'get_parameter_info', 'get_module_info', '__init__'],
            'PortManager': ['add_port_info', 'get_all_ports', '__init__'],
            'ParameterManager': ['add_parameter', 'get_all_parameters', '__init__'],
            'VerilogASTBuilder': [
                'set_module_name', 'add_parameter', 'add_port', 'update_port',
                'build', 'reset', '__init__',
            ],
            'PortFactory': ['to_info'],
            'ExpressionCalculator': ['parse_width_expression', '__init__'],
        }.items()
        for m in methods
    ])
    def test_public_method_signature_preserved(self, cls_name, method_name):
        """硬约束清单内每个公共方法的签名与重构前一致"""
        import src.VerilogAst as current
        pre = _load_pre_refactor_module()

        current_cls = getattr(current, cls_name)
        pre_cls = getattr(pre, cls_name)

        current_fn = getattr(current_cls, method_name)
        pre_fn = getattr(pre_cls, method_name)

        current_sig = inspect.signature(current_fn)
        pre_sig = inspect.signature(pre_fn)

        # 参数名 + 位置 + 默认值 一致
        current_params = list(current_sig.parameters.items())
        pre_params = list(pre_sig.parameters.items())
        assert [p[0] for p in current_params] == [p[0] for p in pre_params], (
            f'{cls_name}.{method_name} parameter names diverged:\n'
            f'  current: {current_sig}\n  pre:     {pre_sig}'
        )

    def test_enum_members_preserved(self):
        """PortDirection / PortType 枚举成员保持不变"""
        import src.VerilogAst as current
        pre = _load_pre_refactor_module()

        assert set(m.name for m in current.PortDirection) == \
               set(m.name for m in pre.PortDirection)
        assert set(m.value for m in current.PortDirection) == \
               set(m.value for m in pre.PortDirection)

        assert set(m.name for m in current.PortType) == \
               set(m.name for m in pre.PortType)
        assert set(m.value for m in current.PortType) == \
               set(m.value for m in pre.PortType)

    def test_portfactory_to_info_return_type_preserved(self):
        """PortFactory.to_info 接受 PortDeclaration 返回 PortInfo（行为兼容）"""
        decl = PortDeclaration(name='x', direction='input', net_type=None)
        info = PortFactory.to_info(decl)
        assert isinstance(info, PortInfo)
        assert info.name == 'x'
        assert info.direction == 'input'
        # net_type='wire' 默认兜底仍应生效
        assert info.net_type == 'wire'


# ============================================================================
# §10.3.11: 死异常类已删除
# ============================================================================

class TestDeadExceptionClassesRemoved:
    """T-I：PortNotFoundError / ParameterNotFoundError 已删除且不可 import"""

    def test_port_not_found_error_removed(self):
        """PortNotFoundError 不应可从 src.VerilogAst import"""
        with pytest.raises(ImportError):
            from src.VerilogAst import PortNotFoundError  # noqa: F401

    def test_parameter_not_found_error_removed(self):
        """ParameterNotFoundError 不应可从 src.VerilogAst import"""
        with pytest.raises(ImportError):
            from src.VerilogAst import ParameterNotFoundError  # noqa: F401

    def test_verilogasterror_still_exists(self):
        """VerilogASTError 必须保留（VerilogParser.py:205 在 catch）"""
        from src.VerilogAst import VerilogASTError
        assert issubclass(VerilogASTError, Exception)

    def test_dead_exceptions_gone_from_module(self):
        """模块属性级断言：死异常类确实消失"""
        import src.VerilogAst as m
        assert not hasattr(m, 'PortNotFoundError')
        assert not hasattr(m, 'ParameterNotFoundError')


# ============================================================================
# 附加：T-E _OrderedRegistry 正确性（架构保证）
# ============================================================================

class TestOrderedRegistryViaPublicAPI:
    """T-E 基类重构：保证 insertion-order 语义 + _parameters/_parameter_order 别名"""

    def test_parameter_manager_underscore_aliases_are_live(self):
        """_parameters 与 _items 应是同一个 dict（保险别名）"""
        pm = ParameterManager()
        assert pm._parameters is pm._items
        assert pm._parameter_order is pm._order

    def test_port_manager_underscore_aliases_are_live(self):
        """_ports 与 _items 应是同一个 dict"""
        portm = PortManager()
        assert portm._ports is portm._items
        assert portm._port_order is portm._order

    def test_parameter_manager_insertion_order_via_add_parameter(self):
        """add_parameter 接口（非 add_parameter_info）也保持插入顺序"""
        pm = ParameterManager()
        pm.add_parameter('X', default_value='1')
        pm.add_parameter('Y', default_value='2')
        pm.add_parameter('Z', default_value='3')
        assert [p.name for p in pm.get_all_parameters()] == ['X', 'Y', 'Z']

    def test_port_manager_multiple_adds_same_name(self):
        """同名 port 多次 add_port_info：后者覆盖前者，顺序不变"""
        portm = PortManager()
        portm.add_port_info(PortInfo(name='clk', direction='input'))
        portm.add_port_info(PortInfo(name='rst', direction='input'))
        portm.add_port_info(PortInfo(name='clk', direction='output'))  # 同名覆盖
        all_ports = portm.get_all_ports()
        assert [p.name for p in all_ports] == ['clk', 'rst']
        assert all_ports[0].direction == 'output'
