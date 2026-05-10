# VCG Refactor Archive: 2026-05-10

This archive contains the review reports, handoff documents, verification
records, and decisions for the refactor wave that covered the original
`doc/review/00_INDEX.md` audit through TASK-08.

## Layout

| Directory | Contents |
|-----------|----------|
| `review/` | Original Linus-style review reports for the 12 Python source files. |
| `handoff/` | Task, delivery, verification, check, feedback, backlog, and bugfix progress documents. |
| `decisions/` | Decision records that were part of this refactor wave. |

## Completed Scope

- TASK-01: `src/VerilogAst.py`
- TASK-02: `src/vcg_file_processor.py`
- TASK-03: `src/VerilogPreprocess.py`
- TASK-04: `src/vcg_execution_engine.py`
- TASK-05: `src/vcg_exceptions.py`
- TASK-06: root CLI entry `vcg.py`
- TASK-07: `src/vcg_instance_manager.py`
- TASK-08: `src/vcg_wires_manager.py`
- Manual refactors: `src/vcg_logger.py`, `src/vcg_rule_manager.py`

## Deferred

- TASK-09 candidate: `src/VerilogLexer.py` token / syntax-error strategy.
- TASK-10 candidate: `src/VerilogParser.py` exception semantics follow-up.

Both are intentionally deferred and should be reopened with new task documents
instead of extending this archive in place.

## Current Working Changes In This Commit

The final code change in this archive wave is the TASK-08 WiresManager refactor:

- `src/vcg_wires_manager.py`
- `tests/test_vcg_wires_manager.py`
- archived handoff documents under `handoff/*08*`

Validation recorded for TASK-08:

```text
uv run pytest tests/test_vcg_wires_manager.py -q
uv run pytest tests/test_vcg_wires_manager.py tests/test_vcg_instance_manager.py tests/test_vcg_rule_manager.py -q
```
