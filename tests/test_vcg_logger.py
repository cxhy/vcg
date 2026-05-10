"""
vcg_logger.py unit tests.
"""

import logging
import os
import sys
from pathlib import Path

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.vcg_logger import (
    clear_file_context,
    current_file_context,
    file_context,
    get_vcg_logger,
    set_file_context,
    setup_vcg_logging,
)


def test_file_context_restores_nested_context():
    current_file_context.set(None)

    with file_context("outer.v"):
        assert current_file_context.get() == "outer.v"

        with file_context("inner.v"):
            assert current_file_context.get() == "inner.v"

        assert current_file_context.get() == "outer.v"

    assert current_file_context.get() is None


def test_legacy_set_clear_file_context_restores_previous_context():
    current_file_context.set(None)

    set_file_context("outer.v")
    set_file_context("inner.v")
    assert current_file_context.get() == "inner.v"

    clear_file_context()
    assert current_file_context.get() == "outer.v"

    clear_file_context()
    assert current_file_context.get() is None


def test_setup_vcg_logging_closes_replaced_file_handler(tmp_path: Path):
    first_log = tmp_path / "first.log"
    second_log = tmp_path / "second.log"

    setup_vcg_logging(level=logging.INFO, log_file=first_log, quiet=True)
    old_handlers = list(get_vcg_logger().handlers)
    old_file_handlers = [
        handler for handler in old_handlers
        if isinstance(handler, logging.FileHandler)
    ]
    assert len(old_file_handlers) == 1

    setup_vcg_logging(level=logging.INFO, log_file=second_log, quiet=True)

    assert old_file_handlers[0].stream is None


def test_log_file_appends_existing_content(tmp_path: Path):
    log_path = tmp_path / "vcg.log"
    log_path.write_text("previous run\n", encoding="utf-8")

    setup_vcg_logging(level=logging.INFO, log_file=log_path, quiet=True)
    logger = get_vcg_logger("LoggerTest")
    logger.info("current run")

    log_text = log_path.read_text(encoding="utf-8")
    assert "previous run" in log_text
    assert "current run" in log_text
