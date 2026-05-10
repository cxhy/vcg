"""Tests for VCG execution engine refactor behavior."""

import os
import sys
from unittest.mock import Mock

import pytest


project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.vcg_exceptions import VCGFileError, VCGParseError, VCGRuntimeError
from src.vcg_execution_engine import OrderedOutputManager, VCGExecutionEngine


class TestOrderedOutputManager:
    """Output collector behavior."""

    def test_add_preserves_order_and_empty_lines(self):
        """Output manager stores already-normalized output segments in order."""
        manager = OrderedOutputManager()

        manager.add("first")
        manager.add("")
        manager.add("second")

        assert manager.get_final_output() == "first\n\nsecond"

    def test_clear_removes_previous_output(self):
        """Clear resets collected output before the next execution."""
        manager = OrderedOutputManager()
        manager.add("first")

        manager.clear()

        assert manager.get_final_output() == ""


class TestExecutionPrint:
    """Print wrapper behavior."""

    def test_execute_collects_print_output_with_blank_lines(self):
        """print output keeps order and blank lines."""
        engine = VCGExecutionEngine()

        result = engine.execute("print('alpha')\nprint()\nprint('omega', end='')")

        assert result == "alpha\n\nomega"

    def test_execute_clears_previous_run_output(self):
        """Each execute call starts with an empty output manager."""
        engine = VCGExecutionEngine()

        assert engine.execute("print('first')") == "first"
        assert engine.execute("print('second')") == "second"

    def test_print_with_file_argument_bypasses_output_collection(self, capsys):
        """print(..., file=...) uses native print and is not collected."""
        engine = VCGExecutionEngine()

        result = engine.execute("import sys\nprint('side', file=sys.stderr)")

        assert result == ""
        assert capsys.readouterr().err.strip() == "side"


class TestExecutionExceptions:
    """Exception boundary behavior."""

    def test_execute_wraps_unknown_python_exception_with_cause(self):
        """Unexpected script exceptions become VCGRuntimeError with cause."""
        engine = VCGExecutionEngine()

        with pytest.raises(VCGRuntimeError) as exc_info:
            engine.execute("raise ValueError('bad input')")

        assert "Exec Error: bad input" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, ValueError)

    @pytest.mark.parametrize(
        "exception_code, exception_type",
        [
            ("VCGFileError('missing')", VCGFileError),
            ("VCGParseError('parse failed')", VCGParseError),
            ("VCGRuntimeError('runtime failed')", VCGRuntimeError),
        ],
    )
    def test_execute_passes_through_vcg_exceptions(self, exception_code, exception_type):
        """VCG exceptions keep their original type across execute()."""
        engine = VCGExecutionEngine()
        code = (
            "from src.vcg_exceptions import VCGFileError, VCGParseError, VCGRuntimeError\n"
            f"raise {exception_code}"
        )

        with pytest.raises(exception_type) as exc_info:
            engine.execute(code)

        assert type(exc_info.value) is exception_type


class TestPathExpansion:
    """Path expansion and fail-fast behavior."""

    def test_expand_path_returns_existing_absolute_path(self, tmp_path):
        """Existing paths are expanded and resolved to absolute paths."""
        source = tmp_path / "module.v"
        source.write_text("module m; endmodule", encoding="utf-8")
        engine = VCGExecutionEngine()

        result = engine.expand_path(str(source))

        assert result == str(source.resolve())

    def test_expand_path_rejects_empty_path(self):
        """Empty file paths fail before downstream managers run."""
        engine = VCGExecutionEngine()

        with pytest.raises(VCGFileError, match="Empty file path"):
            engine.expand_path("  ")

    def test_expand_path_rejects_missing_path(self, tmp_path):
        """Missing files fail in expand_path with VCGFileError."""
        missing = tmp_path / "missing.v"
        engine = VCGExecutionEngine()

        with pytest.raises(VCGFileError, match="File not found"):
            engine.expand_path(str(missing))


class TestDslBindings:
    """DSL context binding behavior."""

    def test_connect_bindings_register_rules_without_output(self):
        """Connect, ConnectParam and WiresRule register rules only."""
        engine = VCGExecutionEngine()

        result = engine.execute(
            "Connect('clk', 'sys_clk')\n"
            "ConnectParam('WIDTH', '8')\n"
            "WiresRule('data', 'w_data', '8')"
        )

        assert result == ""
        assert len(engine.rule_manager.rules["signal_rules"]) == 1
        assert len(engine.rule_manager.rules["param_rules"]) == 1
        assert len(engine.rule_manager.rules["wire_rules"]) == 1

    def test_instance_adds_output_and_resets_rules(self, tmp_path):
        """Instance output is collected and rules reset after generation."""
        source = tmp_path / "sub.v"
        source.write_text("module sub; endmodule", encoding="utf-8")
        engine = VCGExecutionEngine()
        engine.instance_manager = Mock()
        engine.instance_manager.generate_instance.return_value = "sub u_sub ();"

        result = engine.execute(f"Connect('clk', 'sys_clk')\nInstance(r'{source}', 'sub', 'u_sub')")

        engine.instance_manager.generate_instance.assert_called_once_with(
            str(source.resolve()), "sub", "u_sub"
        )
        assert result == "sub u_sub ();"
        assert engine.rule_manager.rules["signal_rules"] == []

    def test_wires_def_adds_output_and_resets_rules(self, tmp_path):
        """WiresDef output is collected and rules reset after generation."""
        source = tmp_path / "sub.v"
        source.write_text("module sub; endmodule", encoding="utf-8")
        engine = VCGExecutionEngine()
        engine.wires_manager = Mock()
        engine.wires_manager.generate_wires_def.return_value = "wire done;"

        result = engine.execute(f"WiresRule('*', 'w_*')\nWiresDef(r'{source}', 'sub', 'output')")

        engine.wires_manager.generate_wires_def.assert_called_once_with(
            str(source.resolve()), "sub", "output", "greedy"
        )
        assert result == "wire done;"
        assert engine.rule_manager.rules["wire_rules"] == []

    def test_instance_missing_path_fails_before_manager_call(self):
        """Missing Instance paths raise VCGFileError before manager generation."""
        engine = VCGExecutionEngine()
        engine.instance_manager = Mock()

        with pytest.raises(VCGFileError):
            engine.execute("Instance('missing_task04.v', 'sub', 'u_sub')")

        engine.instance_manager.generate_instance.assert_not_called()
