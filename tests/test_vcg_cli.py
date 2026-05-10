"""Tests for the VCG CLI entrypoint."""

import os
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest


project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import vcg


class TestParseMacrosArgument:
    def test_empty_macros_return_none(self):
        """Missing or blank macro arguments produce no macro mapping."""
        assert vcg.parse_macros_argument(None) is None
        assert vcg.parse_macros_argument("") is None
        assert vcg.parse_macros_argument("   ") is None

    def test_macro_names_return_empty_string_values(self):
        """Macros without values use an empty string sentinel."""
        assert vcg.parse_macros_argument("WIDTH,DEPTH") == {
            "WIDTH": "",
            "DEPTH": "",
        }

    def test_macro_assignments_return_dict(self):
        """Assigned macro values are parsed into a stable mapping."""
        assert vcg.parse_macros_argument("WIDTH=8,DEPTH=16") == {
            "WIDTH": "8",
            "DEPTH": "16",
        }

    def test_mixed_macro_forms_return_dict(self):
        """Mixed assigned and unassigned macros still return a dict."""
        assert vcg.parse_macros_argument("SIM,WIDTH=8,,DEPTH") == {
            "SIM": "",
            "WIDTH": "8",
            "DEPTH": "",
        }


class TestMain:
    def test_success_path_processes_file_and_returns_zero(self, tmp_path, monkeypatch, capsys):
        """Successful CLI execution initializes logging and processes the file."""
        source = tmp_path / "top.v"
        source.write_text("module top; endmodule\n", encoding="utf-8")
        setup_logging = Mock()
        logger = Mock()
        processor = Mock()
        processor_class = Mock(return_value=processor)
        monkeypatch.setattr(vcg, "setup_vcg_logging", setup_logging)
        monkeypatch.setattr(vcg, "get_vcg_logger", Mock(return_value=logger))
        monkeypatch.setattr(vcg, "VCGFileProcessor", processor_class)

        exit_code = vcg.main([str(source), "--macros", "SIM,WIDTH=8"])

        assert exit_code == 0
        setup_logging.assert_called_once_with(level="WARNING", log_file=None, quiet=False)
        processor_class.assert_called_once_with(macros={"SIM": "", "WIDTH": "8"})
        processor.process_file.assert_called_once_with(source)
        assert capsys.readouterr().out.strip() == f"VCG generation done: {source}"

    def test_missing_file_returns_one_and_reports_vcg_file_error(self, tmp_path, monkeypatch, capsys):
        """Missing input files are reported through the VCG error path."""
        missing = tmp_path / "missing.v"
        setup_logging = Mock()
        monkeypatch.setattr(vcg, "setup_vcg_logging", setup_logging)
        monkeypatch.setattr(vcg, "get_vcg_logger", Mock(return_value=Mock()))
        monkeypatch.setattr(vcg, "VCGFileProcessor", Mock())

        exit_code = vcg.main([str(missing)])

        assert exit_code == 1
        setup_logging.assert_called_once_with(level="WARNING", log_file=None, quiet=False)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "VCG Error: File missing" in captured.err
        assert str(missing) in captured.err
        vcg.VCGFileProcessor.assert_not_called()

    def test_debug_sets_debug_log_level_when_log_level_not_explicit(self, tmp_path, monkeypatch):
        """--debug maps to DEBUG when --log-level is not explicitly supplied."""
        source = tmp_path / "top.v"
        source.write_text("module top; endmodule\n", encoding="utf-8")
        setup_logging = Mock()
        monkeypatch.setattr(vcg, "setup_vcg_logging", setup_logging)
        monkeypatch.setattr(vcg, "get_vcg_logger", Mock(return_value=Mock()))
        monkeypatch.setattr(vcg, "VCGFileProcessor", Mock(return_value=Mock()))

        assert vcg.main([str(source), "--debug"]) == 0

        setup_logging.assert_called_once_with(level="DEBUG", log_file=None, quiet=False)

    def test_explicit_log_level_overrides_debug(self, tmp_path, monkeypatch):
        """An explicit --log-level keeps priority over --debug."""
        source = tmp_path / "top.v"
        source.write_text("module top; endmodule\n", encoding="utf-8")
        setup_logging = Mock()
        monkeypatch.setattr(vcg, "setup_vcg_logging", setup_logging)
        monkeypatch.setattr(vcg, "get_vcg_logger", Mock(return_value=Mock()))
        monkeypatch.setattr(vcg, "VCGFileProcessor", Mock(return_value=Mock()))

        assert vcg.main([str(source), "--debug", "--log-level", "ERROR"]) == 0

        setup_logging.assert_called_once_with(level="ERROR", log_file=None, quiet=False)

    def test_unknown_error_reports_fixed_spelling(self, tmp_path, monkeypatch, capsys):
        """Unexpected failures use the corrected Unknown Error spelling."""
        source = tmp_path / "top.v"
        source.write_text("module top; endmodule\n", encoding="utf-8")
        processor = Mock()
        processor.process_file.side_effect = RuntimeError("boom")
        monkeypatch.setattr(vcg, "setup_vcg_logging", Mock())
        monkeypatch.setattr(vcg, "get_vcg_logger", Mock(return_value=Mock()))
        monkeypatch.setattr(vcg, "VCGFileProcessor", Mock(return_value=processor))

        exit_code = vcg.main([str(source)])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Unknown Error: boom" in captured.err
        assert "Unknow Error" not in captured.err

    def test_unknown_error_logs_traceback_in_debug(self, tmp_path, monkeypatch):
        """DEBUG mode keeps traceback details in the logger for unknown failures."""
        source = tmp_path / "top.v"
        source.write_text("module top; endmodule\n", encoding="utf-8")
        logger = Mock()
        processor = Mock()
        processor.process_file.side_effect = RuntimeError("boom")
        monkeypatch.setattr(vcg, "setup_vcg_logging", Mock())
        monkeypatch.setattr(vcg, "get_vcg_logger", Mock(return_value=logger))
        monkeypatch.setattr(vcg, "VCGFileProcessor", Mock(return_value=processor))

        exit_code = vcg.main([str(source), "--debug"])

        assert exit_code == 1
        logger.exception.assert_called_once_with("Unknown CLI error")
