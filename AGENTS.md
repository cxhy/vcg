# Codex Agent Guide

This file is for Codex-specific collaboration rules. Claude-specific behavior
stays in `CLAUDE.md`.

## VCG Role Mapping

The project defines four VCG role skills:

| VCG role | Codex execution |
|----------|-----------------|
| `vcg-architect` | Main session owns architecture, planning, task documents, and integration decisions. Use `explorer` only for bounded parallel codebase investigation. |
| `vcg-python-dev` | Use `worker` for implementation tasks with a clear file ownership boundary. |
| `vcg-python-tester` | Use `worker` for writing or updating tests, running validation, and producing verification reports. |
| `vcg-verilog-checker` | Use `explorer` for read-only Verilog/AST investigation; use `worker` when writing check reports, tests, or scripts. |

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
   The task document must define scope, interface constraints, compatibility
   requirements, validation gates, and known risks. Do not modify `src/` or
   `tests/` in this phase.
2. User confirmation gate: wait for the user to approve the task document unless
   the user explicitly says to execute without another checkpoint.
3. `vcg-python-dev`: implement only the approved task scope. Write
   `doc/delivery_<NN>_<slug>.md` describing changed files, validation points,
   downstream impact, and any deviations from the task.
4. `vcg-python-tester`: read the delivery document, add or update tests as
   needed, run focused validation before broader regression, and write
   `doc/verification_<NN>_<slug>.md`. If validation finds a product-code issue,
   write `doc/feedback_<NN>_<slug>.md` instead of silently folding fixes into the
   same phase.
5. `vcg-verilog-checker`: use for changes that affect generated Verilog, parser
   AST semantics, or downstream instance/wire output. Write
   `doc/check_<NN>_<slug>.md`.

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
