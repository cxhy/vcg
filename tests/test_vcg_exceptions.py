from pathlib import Path
import os
import sys


project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src import vcg_exceptions
from src.vcg_exceptions import (
    VCGError,
    VCGFileError,
    VCGParseError,
    VCGSyntaxError,
    VCGRuntimeError,
)


class TestVCGErrorCompatibility:
    def test_plain_message_str_remains_unchanged(self):
        """Existing message-only exceptions keep the historical string output."""
        error = VCGFileError("missing file")

        assert str(error) == "missing file"
        assert error.args == ("missing file",)
        assert error.message == "missing file"
        assert error.location is None

    def test_subclasses_are_caught_by_base_class(self):
        """All public domain errors remain catchable through VCGError."""
        errors = [
            VCGFileError("file"),
            VCGParseError("parse"),
            VCGSyntaxError("syntax"),
            VCGRuntimeError("runtime"),
        ]

        assert all(isinstance(error, VCGError) for error in errors)


class TestVCGErrorContext:
    def test_pathlike_lineno_column_and_snippet_are_preserved(self, tmp_path):
        """Structured context fields are stored and included in string output."""
        source_path = tmp_path / "top.v"

        error = VCGSyntaxError(
            "unexpected token",
            path=source_path,
            lineno=12,
            column=7,
            snippet="assign = ;",
        )

        assert error.path == str(source_path)
        assert error.lineno == 12
        assert error.column == 7
        assert error.snippet == "assign = ;"
        assert error.location == f"{source_path}:12:7"
        assert str(error) == f"unexpected token [{source_path}:12:7] snippet: assign = ;"

    def test_path_without_line_formats_location(self):
        """A path-only error still has a useful location string."""
        error = VCGFileError("cannot read", path="rtl/top.v")

        assert error.location == "rtl/top.v"
        assert str(error) == "cannot read [rtl/top.v]"

    def test_line_without_path_uses_unknown_location(self):
        """Line-only parse errors keep location shape without inventing a path."""
        error = VCGParseError("bad marker", lineno=4)

        assert error.location == "<unknown>:4"
        assert str(error) == "bad marker [<unknown>:4]"

    def test_column_without_path_or_line_uses_placeholder_line(self):
        """Column-only syntax context remains deterministic."""
        error = VCGSyntaxError("bad character", column=2)

        assert error.location == "<unknown>:?:2"
        assert str(error) == "bad character [<unknown>:?:2]"

    def test_path_argument_accepts_pathlike(self):
        """PathLike inputs are normalized to strings for downstream consumers."""
        path = Path("rtl") / "sub.v"

        error = VCGFileError("missing", path=path)

        assert error.path == str(path)


class TestPublicExports:
    def test_all_exports_match_exception_hierarchy(self):
        """The module explicitly exports the full VCG exception hierarchy."""
        assert set(vcg_exceptions.__all__) == {
            "VCGError",
            "VCGFileError",
            "VCGParseError",
            "VCGSyntaxError",
            "VCGRuntimeError",
        }
        assert all(hasattr(vcg_exceptions, name) for name in vcg_exceptions.__all__)

    def test_all_exported_values_are_error_classes(self):
        """Every public export is an exception class in the VCG hierarchy."""
        for name in vcg_exceptions.__all__:
            exported = getattr(vcg_exceptions, name)
            assert issubclass(exported, VCGError)
