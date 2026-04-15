## Context

Prompt organization now spans three runtime surfaces:

1. run-root engine instruction files discovered from `cwd=run_dir`
2. runtime-patched `SKILL.md`
3. the actual CLI prompt string passed to the engine

The old model handled (1) by hiding it inside a first-attempt prompt prefix. That was workable, but it created an unnecessary runtime special case and blurred the line between global execution policy and the actual skill call prompt.

## Goals / Non-Goals

**Goals**

- Move engine-agnostic global constraints to run-root instruction files.
- Make skill invocation syntax explicit and adapter-owned.
- Keep the skill body prompt resolution order stable.
- Remove first-attempt global prefix logic from adapter runtime code.
- Keep `rendered_prompt_first_attempt` audit narrow and predictable.

**Non-Goals**

- Do not batch-edit builtin or installed skill `runner.json` files in this change.
- Do not change public HTTP / FCMP / RASP / `PendingInteraction` shapes.
- Do not alter runtime `SKILL.md` patch composition beyond prompt-organization related documentation.

## Decisions

### 1. Run-root instruction files replace the first-attempt prefix

Global execution constraints are rendered once during run materialization into:

- `CLAUDE.md` for Claude
- `GEMINI.md` for Gemini
- `AGENTS.md` for all other engines

This keeps the engine-visible global policy filesystem-based instead of string-prepended.

### 2. Adapter profile owns the invoke line

Each engine declares `skill_invoke_line_template`, making the first line of the final prompt explicit and stable. This removes duplicated “please call the skill” wording from fallback templates and reduces drift between engines.

### 3. Body prompts remain skill/body specific

The existing resolution order is retained for the body prompt:

1. `entrypoint.prompts[engine]`
2. `entrypoint.prompts.common`
3. adapter body default template
4. adapter body fallback inline

The body prompt is now strictly “post-invocation instructions”.

### 4. Prompt audit records only the assembled prompt

`rendered_prompt_first_attempt` still records the first prompt, but only the final assembled skill prompt. Run-root instruction files are no longer folded into that audit field.

## Risks / Trade-offs

- Existing templates and tests still assume the old prefix. Mitigation: update prompt-related assertions and keep prompt assembly deterministic.
- Skill-authored prompts may still contain legacy “please call skill” wording until manually cleaned. Mitigation: this change does not auto-migrate `runner.json`, and the new invoke line still keeps runtime behavior correct.

## Migration Plan

1. Update adapter profile schema and per-engine profiles to the invoke-line + body model.
2. Refactor prompt builder common code to assemble prompts from the new model.
3. Remove runtime first-attempt global prefix logic.
4. Render run-root instruction files during run materialization.
5. Update docs and tests.
