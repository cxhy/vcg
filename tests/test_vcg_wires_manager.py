"""Tests for WiresManager behavior and TASK-08 refactor contracts."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.vcg_exceptions import VCGFileError, VCGParseError, VCGRuntimeError, VCGSyntaxError
from src.vcg_rule_manager import VCGRuleManager
from src.vcg_wires_manager import WiresManager


@pytest.fixture
def mock_rule_manager():
    """Create a mock rule manager matching WiresManager's dependency contract."""
    return Mock(spec=VCGRuleManager)


@pytest.fixture
def wires_manager(mock_rule_manager):
    """Create a WiresManager with a mock rule manager."""
    return WiresManager(mock_rule_manager)


@pytest.fixture
def sample_verilog_file(tmp_path):
    """Create a valid Verilog module for parser smoke tests."""
    file_path = tmp_path / "test_module.v"
    file_path.write_text(
        """
module test_module (
    input wire clk,
    input wire rst_n,
    input wire [7:0] data_in,
    output wire [15:0] data_out,
    output wire valid,
    inout wire [3:0] bidir_port
);
endmodule
"""
    )
    return str(file_path)


@pytest.fixture
def empty_module_file(tmp_path):
    """Create a valid module with no ports."""
    file_path = tmp_path / "empty_module.v"
    file_path.write_text("module empty_module (); endmodule\n")
    return str(file_path)


def make_port(name="port", direction="input", width=None, range_string=""):
    """Create a minimal port object matching the WiresManager contract."""
    return SimpleNamespace(
        name=name,
        direction=direction,
        width=width,
        range_string=range_string,
    )


def use_ports(wires_manager, ports):
    """Replace the parser instance with a mock AST provider."""
    mock_ast = Mock()
    mock_ast.get_port_info.return_value = ports

    wires_manager.parser = Mock()
    wires_manager.parser.parse_file.return_value = mock_ast
    return mock_ast


class TestFileParsingFeatures:
    """File parsing and parser error behavior."""

    def test_parse_valid_file_with_real_parser(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """A real parsed module should produce greedy wires for all parsed ports."""
        mock_rule_manager.resolve_wire_generation.return_value = (None, None, None, False)

        result = wires_manager.generate_wires_def(sample_verilog_file, "test_module")

        assert result.splitlines() == [
            "wire           clk;",
            "wire           rst_n;",
            "wire [7:0]     data_in;",
            "wire [15:0]    data_out;",
            "wire           valid;",
            "wire [3:0]     bidir_port;",
        ]

    def test_file_not_exists_raises_vcg_file_error(self, wires_manager):
        """A missing file should surface as VCGFileError."""
        with pytest.raises(VCGFileError):
            wires_manager.generate_wires_def("/non/existent/path/file.v", "test_module")

    def test_vcg_parse_error_is_not_wrapped(self, wires_manager, sample_verilog_file):
        """VCG parse errors from parser must propagate unchanged."""
        parse_error = VCGParseError("parse failed")
        wires_manager.parser = Mock()
        wires_manager.parser.parse_file.side_effect = parse_error

        with pytest.raises(VCGParseError) as exc_info:
            wires_manager.generate_wires_def(sample_verilog_file, "test_module")

        assert exc_info.value is parse_error

    def test_vcg_syntax_error_is_not_wrapped(self, wires_manager, sample_verilog_file):
        """VCG syntax errors from parser must propagate unchanged."""
        syntax_error = VCGSyntaxError("syntax failed")
        wires_manager.parser = Mock()
        wires_manager.parser.parse_file.side_effect = syntax_error

        with pytest.raises(VCGSyntaxError) as exc_info:
            wires_manager.generate_wires_def(sample_verilog_file, "test_module")

        assert exc_info.value is syntax_error

    def test_unknown_exception_is_wrapped_as_runtime_error(self, wires_manager, sample_verilog_file):
        """Unexpected parser failures should preserve cause under VCGRuntimeError."""
        original = TypeError("bad port object")
        wires_manager.parser = Mock()
        wires_manager.parser.parse_file.side_effect = original

        with pytest.raises(VCGRuntimeError) as exc_info:
            wires_manager.generate_wires_def(sample_verilog_file, "test_module")

        assert exc_info.value.__cause__ is original

    def test_macros_are_passed_to_parser(self, mock_rule_manager):
        """Macros passed to WiresManager should be visible on the parser preprocessor."""
        macros = {"WIDTH": "8", "DEPTH": "16"}

        manager = WiresManager(mock_rule_manager, macros=macros)

        assert manager.macros == macros
        assert manager.parser.preprocessor.macros == macros


class TestPortDirectionFiltering:
    """Port direction filtering behavior."""

    @pytest.fixture
    def ports(self):
        """Create representative ports for direction filtering."""
        return [
            make_port(name="clk", direction="input"),
            make_port(name="data_in", direction="input", width=8, range_string="[7:0]"),
            make_port(name="data_out", direction="output", width=16, range_string="[15:0]"),
            make_port(name="valid", direction="output"),
            make_port(name="bidir", direction="inout", width=4, range_string="[3:0]"),
        ]

    @pytest.mark.parametrize(
        ("direction", "expected_lines"),
        [
            (
                None,
                [
                    "wire           clk;",
                    "wire [7:0]     data_in;",
                    "wire [15:0]    data_out;",
                    "wire           valid;",
                    "wire [3:0]     bidir;",
                ],
            ),
            (
                "INPUT",
                [
                    "wire           clk;",
                    "wire [7:0]     data_in;",
                ],
            ),
            (
                "Output",
                [
                    "wire [15:0]    data_out;",
                    "wire           valid;",
                ],
            ),
            ("inout", ["wire [3:0]     bidir;"]),
        ],
    )
    def test_filters_ports_by_direction(
        self,
        wires_manager,
        sample_verilog_file,
        mock_rule_manager,
        ports,
        direction,
        expected_lines,
    ):
        """Direction filter should be case-insensitive and preserve greedy output."""
        mock_rule_manager.resolve_wire_generation.return_value = (None, None, None, False)
        use_ports(wires_manager, ports)

        result = wires_manager.generate_wires_def(
            sample_verilog_file,
            "test_module",
            port_direction=direction,
        )

        assert result.splitlines() == expected_lines

    def test_invalid_direction_raises_value_error(self, wires_manager, sample_verilog_file):
        """Invalid port_direction values should be rejected."""
        with pytest.raises(ValueError):
            wires_manager.generate_wires_def(
                sample_verilog_file,
                "test_module",
                port_direction="invalid_direction",
            )


class TestGenerationPatterns:
    """Greedy and lazy generation mode behavior."""

    @pytest.mark.parametrize(
        ("pattern", "wire_name", "rule_matched", "expected"),
        [
            ("greedy", "rule_sig", True, "wire           rule_sig;"),
            ("greedy", "", True, ""),
            ("greedy", None, False, "wire           data;"),
            ("lazy", "rule_sig", True, "wire           rule_sig;"),
            ("lazy", "", True, ""),
            ("lazy", None, False, ""),
        ],
    )
    def test_generation_pattern_matrix(
        self,
        wires_manager,
        sample_verilog_file,
        mock_rule_manager,
        pattern,
        wire_name,
        rule_matched,
        expected,
    ):
        """Greedy/lazy behavior is defined by rule match and resolved wire name."""
        mock_rule_manager.resolve_wire_generation.return_value = (
            wire_name,
            None,
            None,
            rule_matched,
        )
        use_ports(wires_manager, [make_port(name="data")])

        result = wires_manager.generate_wires_def(
            sample_verilog_file,
            "test_module",
            pattern=pattern,
        )

        assert result == expected

    def test_invalid_pattern_raises_value_error(self, wires_manager, sample_verilog_file):
        """Invalid generation patterns should be rejected."""
        with pytest.raises(ValueError):
            wires_manager.generate_wires_def(
                sample_verilog_file,
                "test_module",
                pattern="invalid_pattern",
            )


class TestWidthFormatting:
    """Width formatting behavior."""

    @pytest.mark.parametrize(
        ("width_input", "expected"),
        [
            (None, ""),
            ("", ""),
            (0, ""),
            (1, ""),
            (8, "[7:0]"),
            ("1", ""),
            ("32", "[31:0]"),
            ("[15:0]", "[15:0]"),
            ("[7:0][3:0]", "[7:0][3:0]"),
            ("[7:0] [3:0]", "[7:0] [3:0]"),
            ("[7:0]\t[3:0]", "[7:0]\t[3:0]"),
            ("WIDTH", "[WIDTH-1:0]"),
            ("N+1", "[(N+1)-1:0]"),
            ("N-1", "[(N-1)-1:0]"),
            ("N*2", "[(N*2)-1:0]"),
            ("(N+M)/2", "[((N+M)/2)-1:0]"),
            ("(A+B)*C-1", "[((A+B)*C-1)-1:0]"),
        ],
    )
    def test_format_wire_width(self, wires_manager, width_input, expected):
        """Supported width inputs should map to stable Verilog range text."""
        assert wires_manager._format_wire_width(width_input) == expected

    def test_rule_width_overrides_port_width(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """Explicit rule width has priority over parsed port width."""
        mock_rule_manager.resolve_wire_generation.return_value = ("sig", "4", None, True)
        use_ports(
            wires_manager,
            [make_port(name="data", width=8, range_string="[7:0]")],
        )

        result = wires_manager.generate_wires_def(sample_verilog_file, "test_module")

        assert result == "wire [3:0]     sig;"

    def test_empty_rule_width_falls_back_to_port_width(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """Empty rule width should not erase a vector port width."""
        mock_rule_manager.resolve_wire_generation.return_value = ("sig", "", None, True)
        use_ports(
            wires_manager,
            [make_port(name="data", width=8, range_string="[7:0]")],
        )

        result = wires_manager.generate_wires_def(sample_verilog_file, "test_module")

        assert result == "wire [7:0]     sig;"

    def test_simple_port_width_does_not_render_range(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """Scalar port width should not render [0:0]."""
        mock_rule_manager.resolve_wire_generation.return_value = ("sig", None, None, True)
        use_ports(wires_manager, [make_port(name="sig", width=1)])

        result = wires_manager.generate_wires_def(sample_verilog_file, "test_module")

        assert result == "wire           sig;"


class TestExpressionAndAlignment:
    """Expression rendering and alignment behavior."""

    @pytest.mark.parametrize(
        ("width", "name", "expression", "expected"),
        [
            (8, "data", None, "wire [7:0]     data;"),
            (None, "valid", "1'b0", "wire           valid = 1'b0;"),
            (16, "counter", "16'd0", "wire [15:0]    counter = 16'd0;"),
            ("[127:0]", "wide", None, "wire [127:0]   wide;"),
        ],
    )
    def test_render_wire_declaration_exact_output(
        self,
        wires_manager,
        sample_verilog_file,
        mock_rule_manager,
        width,
        name,
        expression,
        expected,
    ):
        """Wire declarations should preserve existing spacing and expression format."""
        mock_rule_manager.resolve_wire_generation.return_value = (name, None, expression, True)
        use_ports(
            wires_manager,
            [make_port(name=name, width=width, range_string="[7:0]" if width else "")],
        )

        result = wires_manager.generate_wires_def(sample_verilog_file, "test_module")

        assert result == expected

    def test_custom_spacing_affects_rendered_output(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """set_base_spacing should change the target name column."""
        wires_manager.set_base_spacing(20)
        mock_rule_manager.resolve_wire_generation.return_value = ("sig", None, None, True)
        use_ports(wires_manager, [make_port(name="sig", width=4, range_string="[3:0]")])

        result = wires_manager.generate_wires_def(sample_verilog_file, "test_module")

        assert result == "wire [3:0]          sig;"
        assert wires_manager.get_base_spacing() == 20

    def test_long_prefix_uses_single_space(self, wires_manager, sample_verilog_file, mock_rule_manager):
        """A prefix at or beyond the name column should still separate the name."""
        mock_rule_manager.resolve_wire_generation.return_value = ("sig", None, None, True)
        use_ports(wires_manager, [make_port(name="sig", width="[1048575:0]", range_string="[1048575:0]")])

        result = wires_manager.generate_wires_def(sample_verilog_file, "test_module")

        assert result == "wire [1048575:0] sig;"

    def test_zero_or_negative_spacing_remains_allowed(self, wires_manager):
        """Spacing setter keeps historical permissive behavior."""
        wires_manager.set_base_spacing(0)
        assert wires_manager.get_base_spacing() == 0

        wires_manager.set_base_spacing(-5)
        assert wires_manager.get_base_spacing() == -5


class TestBoundaryConditions:
    """Boundary and special naming behavior."""

    def test_empty_file_path_raises_vcg_file_error(self, wires_manager):
        """An empty path should be treated as an invalid file path."""
        with pytest.raises(VCGFileError):
            wires_manager.generate_wires_def("", "test_module")

    def test_empty_module_name_is_only_used_for_logging(
        self,
        wires_manager,
        sample_verilog_file,
        mock_rule_manager,
    ):
        """module_name is not used to filter the parsed AST in current API."""
        mock_rule_manager.resolve_wire_generation.return_value = (None, None, None, False)
        use_ports(wires_manager, [make_port(name="data")])

        result = wires_manager.generate_wires_def(sample_verilog_file, "")

        assert result == "wire           data;"

    def test_empty_port_list_returns_empty_string(self, wires_manager, empty_module_file, mock_rule_manager):
        """A module with no ports should produce no wire declarations."""
        mock_rule_manager.resolve_wire_generation.return_value = (None, None, None, False)
        use_ports(wires_manager, [])

        result = wires_manager.generate_wires_def(empty_module_file, "empty_module")

        assert result == ""

    @pytest.mark.parametrize("wire_name", ["data_valid", "port0", "sig$name"])
    def test_special_wire_names_are_preserved(
        self,
        wires_manager,
        sample_verilog_file,
        mock_rule_manager,
        wire_name,
    ):
        """WiresManager should render resolved names without additional validation."""
        mock_rule_manager.resolve_wire_generation.return_value = (wire_name, None, None, True)
        use_ports(wires_manager, [make_port(name="port")])

        result = wires_manager.generate_wires_def(sample_verilog_file, "test_module")

        assert result == f"wire           {wire_name};"
