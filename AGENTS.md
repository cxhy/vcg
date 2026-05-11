# Codex Agent Guide

This file is the Codex-facing project guide for VCG. It intentionally includes
the shared project rules Codex needs, so Codex does not need to read
`CLAUDE.md` as a second source of truth. Claude-specific behavior stays in
`CLAUDE.md`.

## Project Summary

VCG (Verilog Code Generator) embeds Python scripts in Verilog files to generate
module instances, signal connections, and wire declarations automatically.
Technical architecture and long-term decisions are recorded in `PROJECT.md`.

## Tech Stack

- Python >=3.14 (`pyproject.toml`)
- PLY >=3.11 for lexing and parsing
- sympy for expression evaluation
- pytest >=9.0.3 for tests
- uv for package management; do not use `pip install`

## Development Commands

```bash
# Run all tests
uv run pytest tests/ -v

# Run a single test module
uv run pytest tests/test_VerilogParser.py -v

# Run VCG on a Verilog file
uv run python vcg.py <verilog_file> --log-level DEBUG
```

CLI options:

- `--debug`: debug mode
- `--macros M1=v1,M2`: pass macro definitions
- `--log-level {DEBUG|INFO|WARNING|ERROR|CRITICAL}`: logging level
- `--log-file FILE`: write logs to file
- `--quiet`: quiet mode, errors only

## Coding Standards

### Immutability

- Create new objects instead of mutating existing objects.
- Prefer `frozen=True` dataclasses when the data model allows it.
- Builders create new AST objects; they do not mutate existing AST objects.

### File and Function Size

- Keep files under 800 lines.
- Keep functions under 50 lines.
- Prefer multiple focused small files over one large file.

### Exceptions

- Use the VCG exception hierarchy:
  `VCGError` -> `VCGFileError` / `VCGParseError` / `VCGSyntaxError` /
  `VCGRuntimeError`.
- Do not use broad `except Exception` blocks that swallow semantic exceptions.
  Catch meaningful exception types first and re-raise when appropriate.

### Logging

- Use `get_vcg_logger('ModuleName')`.
- Logger names are hierarchical under `VCG.ModuleName`.

### Naming

- Module files use either `vcg_` snake_case or `Verilog` PascalCase prefixes.
- Classes use PascalCase.
- Functions and variables use snake_case.
- Constants and VCG parameters use UPPER_CASE.
- Verilog instance names use `u_<name>`.
- Verilog signals use snake_case.
- Verilog output registers use the `_r` suffix.

### Tests

- Test files are named `test_<module_name>.py` and live under `tests/`.
- For mocks, replace instance attributes directly instead of patching classes
  already instantiated in `__init__`.
- `Mock(name=...)` uses `name` as a Mock reserved field; create the Mock first
  and then assign `.name`.
- Use `Mock(spec=RealClass)` when interface consistency matters.

## VCG Role Mapping

The project defines four VCG role skills:

| VCG role | Codex execution |
|----------|-----------------|
| `vcg-architect` | Main session owns architecture, planning, task documents, and integration decisions. Use `explorer` only for bounded parallel codebase investigation. |
| `vcg-python-dev` | Use `worker` for implementation tasks with a clear file ownership boundary. |
| `vcg-python-tester` | Use `worker` for writing or updating tests, running validation, and producing verification reports. |
| `vcg-verilog-checker` | Use `explorer` for read-only Verilog/AST investigation; use `worker` when writing check reports, tests, or scripts. |

## Document Protocol

Use `doc/` as the handoff surface between roles:

- Task document: `doc/task_<NN>_<slug>.md`
- Design document: `doc/design_<NN>_<slug>.md`
- Delivery document: `doc/delivery_<NN>_<slug>.md`
- Verification report: `doc/verification_<NN>_<slug>.md`
- Verilog / AST check report: `doc/check_<NN>_<slug>.md`
- Feedback document: `doc/feedback_<NN>_<slug>.md`
- Progress JSON for multi-task waves: `doc/<wave>_tasks.json`

When a multi-task wave uses a progress JSON file, that JSON is the machine
readable status source. Every phase transition must update the related task
entry with status, artifact paths, validation evidence, blockers if any, and a
history record. Do not mark a task done until the required handoff documents and
user final confirmation are recorded.

Escalation direction:

- tester -> dev for implementation fixes
- checker -> architect for architecture or generated-Verilog risk assessment

## Memory System

| Layer | File | Content | Update timing |
|-------|------|---------|---------------|
| Long-term | `PROJECT.md` | Technical decisions, architecture, module dependencies | After milestones or major decisions |
| Detail | `doc/decisions/YYYY-MM-DD_<slug>.md` | Concrete technical decisions from a session or refactor wave | When a decision affects later work |

- `AGENTS.md`: Codex-facing project rules and workflow.
- `CLAUDE.md`: Claude-facing project rules.
- `PROJECT.md`: technical architecture and decision history.
- When `doc/decisions/` exceeds 10 active files or a milestone completes,
  distill stable conclusions into `PROJECT.md` and move raw records into
  `doc/decisions/archive/YYYY-MM/` or the relevant wave archive.

## Dispatch Rules

- Do not start Codex subagents unless the user explicitly asks for parallel agents, subagents, delegation, or multiple agents working at once.
- Keep architecture and cross-module decisions in the main session unless the user explicitly requests delegation.
- When dispatching `worker` agents, assign disjoint file ownership and tell them not to revert unrelated work.
- Use `explorer` agents only for concrete, read-only questions that can run in parallel without blocking the main path.
- Continue using `doc/` as the handoff surface for task, delivery, verification, check, and feedback records.

## Role Handoff Discipline

Codex may execute all VCG roles in the main session when the user has not
explicitly requested subagents, but the roles must still be separated by
document handoffs. Do not collapse architecture, implementation, and
verification into one unstructured pass.

For planned refactors, parser/AST/interface changes, security-sensitive fixes,
or changes that affect more than one module, use this sequence:

1. `vcg-architect`: inspect existing code and write `doc/task_<NN>_<slug>.md`.
   The task document must list the required refactor function points, current
   problems and evidence, scope boundaries, interface constraints,
   compatibility requirements, validation gates, and known risks. Do not modify
   `src/` or `tests/` in this phase.
2. User architecture review gate: wait for the user to approve the task document
   unless the user explicitly says to execute without another checkpoint.
3. Design phase: after user approval, write `doc/design_<NN>_<slug>.md`. The
   design document must map every architect-required function point to concrete
   file changes, data structures, interfaces, error flows, compatibility
   handling, and tests. This phase may be performed in the main session or by a
   design agent if the user explicitly requests agent delegation. Do not modify
   `src/` or `tests/` in this phase.
4. Design review gate: wait for the user or architect to approve the design
   document before implementation.
5. `vcg-python-dev`: implement only the approved task and design scope. Write
   `doc/delivery_<NN>_<slug>.md` describing changed files, validation points,
   downstream impact, and any deviations from the task.
6. `vcg-python-tester`: read the task, design, and delivery documents. Add or
   update tests as
   needed, run focused validation before broader regression, and write
   `doc/verification_<NN>_<slug>.md`. If validation finds a product-code issue,
   write `doc/feedback_<NN>_<slug>.md` instead of silently folding fixes into the
   same phase.
7. `vcg-architect`: read verification results and confirm that the original
   function points, design constraints, compatibility requirements, and progress
   JSON are satisfied. For changes that affect generated Verilog, parser AST
   semantics, or downstream instance/wire output, also run the
   `vcg-verilog-checker` role and write `doc/check_<NN>_<slug>.md`.
8. User final confirmation gate: present the delivery, verification, and check
   result to the user. Only after user confirmation may the task be committed
   and marked `done`.

The main session may perform the phases sequentially, but it must announce the
active role, read the previous phase's handoff document, and keep each phase's
edits within that role's responsibility. This prevents context pollution and
keeps the audit trail reconstructable from `doc/`.

Small local fixes may skip the full task/delivery/verification chain only when
all of these are true:

- the user directly asks for an immediate fix;
- the change is confined to one module;
- no public interface, parser grammar, generated Verilog, or security boundary
  changes;
- the final response states which workflow steps were intentionally skipped and
  why.
