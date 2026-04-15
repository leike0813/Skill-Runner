## 1. Implementation

- [x] 1.1 Replace the old first-attempt global prefix template with a run-root instruction template.
- [x] 1.2 Render `CLAUDE.md` / `GEMINI.md` / `AGENTS.md` into `run_dir` root during run materialization.
- [x] 1.3 Refactor prompt assembly to `invoke line + body prompt`.
- [x] 1.4 Rename adapter profile prompt-builder fields to the new invoke/body model.
- [x] 1.5 Remove runtime first-attempt prefix injection from `base_execution_adapter`.

## 2. Documentation

- [x] 2.1 Add `docs/prompt_organization_ssot.md`.
- [x] 2.2 Align prompt-related developer docs with the new profile field names.
- [x] 2.3 Clarify `rendered_prompt_first_attempt` semantics in run-artifact docs.

## 3. Validation

- [x] 3.1 Update prompt-builder, profile-loader, and bootstrapper unit tests.
- [x] 3.2 Run targeted pytest coverage for the touched modules.
- [x] 3.3 Run mypy for the touched runtime/orchestration modules.
