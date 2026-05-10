"""Tests for VCG file processor refactor behavior."""

from dataclasses import FrozenInstanceError, fields, is_dataclass
import os
import sys
from textwrap import dedent
from unittest.mock import Mock, patch

import pytest


project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.vcg_exceptions import VCGFileError, VCGParseError, VCGRuntimeError
from src.vcg_file_processor import ExecutedBlock, VCGBlock, VCGFileProcessor


def make_processor_with_outputs(outputs: dict[int, str]) -> VCGFileProcessor:
    """Create a processor whose execution phase returns configured block output."""
    processor = VCGFileProcessor()

    def execute_blocks(blocks: list[VCGBlock], base_dir):
        return [
            ExecutedBlock(block=block, generated_content=outputs[block.block_id])
            for block in blocks
        ]

    processor._execute_blocks = execute_blocks
    return processor


def write_vcg_file(tmp_path, content: str):
    """Write a temporary VCG file with normalized indentation."""
    file_path = tmp_path / "top.v"
    file_path.write_text(dedent(content).lstrip(), encoding="utf-8")
    return file_path


class TestVCGBlockStructure:
    """Structural tests for immutable block data."""

    def test_vcg_block_is_frozen_and_has_no_generated_content_field(self):
        """VCGBlock is a frozen dataclass and execution output is not stored on it."""
        assert is_dataclass(VCGBlock)
        assert VCGBlock.__dataclass_params__.frozen is True
        assert "generated_content" not in {field.name for field in fields(VCGBlock)}

        block = VCGBlock(code="print('x')", start_line=1, end_line=3, block_id=0)
        with pytest.raises(FrozenInstanceError):
            block.code = "print('changed')"


class TestPreprocess:
    """Tests for VCG Python block preprocessing."""

    def test_preprocess_vcg_code_preserves_blank_lines(self):
        """Blank lines inside VCG blocks are preserved after comment stripping."""
        processor = VCGFileProcessor()
        raw_code = "\n".join(
            [
                "//print('first')",
                "//",
                "//if True:",
                "//    print('nested')",
                "//",
                "//print('last')",
            ]
        )

        result = processor._preprocess_vcg_code(raw_code)

        assert result.split("\n") == [
            "print('first')",
            "",
            "if True:",
            "    print('nested')",
            "",
            "print('last')",
        ]


class TestGeneratedContentInjection:
    """Tests for inserting and updating generated Verilog blocks."""

    def test_process_file_inserts_new_generated_block_when_missing(self, tmp_path):
        """A VCG block without generated output receives matching begin/end markers."""
        file_path = write_vcg_file(
            tmp_path,
            """
            module top;
            //VCG_BEGIN
            //print("wire inserted;")
            //VCG_END
            endmodule
            """,
        )
        processor = make_processor_with_outputs({0: "wire inserted;"})

        processor.process_file(file_path)

        assert file_path.read_text(encoding="utf-8") == dedent(
            """
            module top;
            //VCG_BEGIN
            //print("wire inserted;")
            //VCG_END
            //VCG_GEN_BEGIN_0
            wire inserted;
            //VCG_GEN_END_0
            endmodule
            """
        ).lstrip()

    def test_process_file_replaces_existing_generated_block_without_duplicate(self, tmp_path):
        """Repeated processing updates existing generated block content only once."""
        file_path = write_vcg_file(
            tmp_path,
            """
            module top;
            //VCG_BEGIN
            //print("wire fresh;")
            //VCG_END
            //VCG_GEN_BEGIN_0
            wire stale;
            //VCG_GEN_END_0
            endmodule
            """,
        )
        processor = make_processor_with_outputs({0: "wire fresh;"})

        processor.process_file(file_path)
        processor.process_file(file_path)
        result = file_path.read_text(encoding="utf-8")

        assert result.count("//VCG_GEN_BEGIN_0") == 1
        assert result.count("//VCG_GEN_END_0") == 1
        assert "wire fresh;" in result
        assert "wire stale;" not in result

    def test_process_file_updates_out_of_order_generated_blocks_by_explicit_id(self, tmp_path):
        """Generated blocks are matched by explicit id, not by encounter order."""
        file_path = write_vcg_file(
            tmp_path,
            """
            module top;
            //VCG_BEGIN
            //print("block zero")
            //VCG_END
            //VCG_BEGIN
            //print("block one")
            //VCG_END
            //VCG_GEN_BEGIN_1
            stale one
            //VCG_GEN_END_1
            //VCG_GEN_BEGIN_0
            stale zero
            //VCG_GEN_END_0
            endmodule
            """,
        )
        processor = make_processor_with_outputs({0: "fresh zero", 1: "fresh one"})

        processor.process_file(file_path)
        result = file_path.read_text(encoding="utf-8")

        assert result.index("//VCG_GEN_BEGIN_1\nfresh one") < result.index(
            "//VCG_GEN_BEGIN_0\nfresh zero"
        )
        assert "stale one" not in result
        assert "stale zero" not in result


class TestMarkerErrors:
    """Tests for malformed VCG marker handling."""

    @pytest.mark.parametrize(
        ("content", "message"),
        [
            (
                """
                //VCG_BEGIN
                //VCG_BEGIN
                //VCG_END
                """,
                "nested VCG_BEGIN",
            ),
            ("//VCG_END\n", "orphan VCG_END"),
            ("//VCG_BEGIN\n//print('x')\n", "unterminated VCG_BEGIN"),
            (
                """
                //VCG_BEGIN
                //print('x')
                //VCG_END
                //VCG_GEN_BEGIN
                generated
                //VCG_GEN_END_0
                """,
                "malformed VCG_GEN_BEGIN",
            ),
            (
                """
                //VCG_BEGIN
                //print('x')
                //VCG_END
                //VCG_GEN_END_0
                """,
                "orphan VCG_GEN_END",
            ),
            (
                """
                //VCG_BEGIN
                //print('x')
                //VCG_END
                //VCG_GEN_BEGIN_0
                generated
                """,
                "unterminated VCG_GEN_BEGIN_0",
            ),
            (
                """
                //VCG_BEGIN
                //print('x')
                //VCG_END
                //VCG_GEN_BEGIN_0
                //VCG_GEN_BEGIN_0
                //VCG_GEN_END_0
                """,
                "nested VCG_GEN_BEGIN",
            ),
            (
                """
                //VCG_BEGIN
                //print('x')
                //VCG_END
                //VCG_GEN_BEGIN_0
                generated
                //VCG_GEN_END
                """,
                "malformed VCG_GEN_END",
            ),
        ],
    )
    def test_extract_vcg_blocks_rejects_malformed_markers(self, content, message):
        """Invalid VCG or VCG_GEN marker structure raises VCGParseError."""
        processor = VCGFileProcessor()

        with pytest.raises(VCGParseError, match=message):
            processor._extract_vcg_blocks(dedent(content).lstrip())


class TestExceptionHandling:
    """Tests for file and runtime exception semantics."""

    def test_process_file_missing_file_raises_vcg_file_error_with_os_cause(self, tmp_path):
        """Missing input files are wrapped as VCGFileError with the OSError cause preserved."""
        processor = VCGFileProcessor()
        missing_file = tmp_path / "missing.v"

        with pytest.raises(VCGFileError) as exc_info:
            processor.process_file(missing_file)

        assert isinstance(exc_info.value.__cause__, (OSError, FileNotFoundError))

    def test_process_file_propagates_vcg_runtime_error_from_execution_engine(self, tmp_path):
        """VCGRuntimeError from the execution phase is not wrapped as VCGFileError."""
        file_path = write_vcg_file(
            tmp_path,
            """
            //VCG_BEGIN
            //print('x')
            //VCG_END
            """,
        )
        processor = VCGFileProcessor()
        runtime_error = VCGRuntimeError("engine failed")
        processor._execute_blocks = Mock(side_effect=runtime_error)

        with pytest.raises(VCGRuntimeError) as exc_info:
            processor.process_file(file_path)

        assert exc_info.value is runtime_error


class TestRelativePathDSL:
    """End-to-end tests for DSL path resolution."""

    def test_instance_relative_path_resolves_from_processed_file_directory(self, tmp_path, monkeypatch):
        """Instance('sub.v', ...) resolves relative to the processed VCG file, not cwd."""
        submodule = tmp_path / "sub.v"
        submodule.write_text(
            dedent(
                """
                module sub (
                    input wire clk,
                    output wire done
                );
                endmodule
                """
            ).lstrip(),
            encoding="utf-8",
        )
        top = write_vcg_file(
            tmp_path,
            """
            module top;
            //VCG_BEGIN
            //Instance("sub.v", "sub", "u_sub")
            //VCG_END
            endmodule
            """,
        )
        other_cwd = tmp_path / "other"
        other_cwd.mkdir()
        monkeypatch.chdir(other_cwd)

        VCGFileProcessor().process_file(top)
        result = top.read_text(encoding="utf-8")

        assert "sub u_sub (" in result
        assert ".clk" in result
        assert ".done" in result

    def test_wires_def_relative_path_resolves_from_processed_file_directory(self, tmp_path, monkeypatch):
        """WiresDef('sub.v', ...) resolves relative to the processed VCG file, not cwd."""
        submodule = tmp_path / "sub.v"
        submodule.write_text(
            dedent(
                """
                module sub (
                    input wire clk,
                    output wire [3:0] data_out,
                    output wire done
                );
                endmodule
                """
            ).lstrip(),
            encoding="utf-8",
        )
        top = write_vcg_file(
            tmp_path,
            """
            module top;
            //VCG_BEGIN
            //WiresDef("sub.v", "sub", "output")
            //VCG_END
            endmodule
            """,
        )
        other_cwd = tmp_path / "other"
        other_cwd.mkdir()
        monkeypatch.chdir(other_cwd)

        VCGFileProcessor().process_file(top)
        result = top.read_text(encoding="utf-8")

        assert "wire [3:0]" in result
        assert "data_out;" in result
        assert "wire           done;" in result
