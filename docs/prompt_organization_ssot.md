# Prompt Organization SSOT

## Overview

This document defines the long-term source of truth for prompt organization in Skill Runner.

The model now has two distinct layers:

1. Run-root instruction files carry engine-agnostic global execution constraints.
2. Skill invocation prompts carry per-attempt skill call intent and body instructions.

These layers are intentionally separate. Global execution constraints are no longer injected as a first-attempt prompt prefix.

## Run-Root Instruction Files

Global execution constraints are rendered during run provisioning and written into the run root:

- `claude` → `CLAUDE.md`
- `gemini` → `GEMINI.md`
- `codex` / `opencode` / `qwen` → `AGENTS.md`

These files are rendered from:

- static source: `server/assets/templates/run_execution_instructions.md.j2`
- dynamic context:
  - `run_dir`
  - `engine_workspace_dir`
  - `engine_skills_dir`
  - `skill`
  - `skill_id`

They are written only to `run_dir` root and are not duplicated into engine workspace subdirectories.

Their responsibility is intentionally narrow:

- they carry engine-agnostic global execution discipline
- they explain the run workspace and engine workspace layout
- they do not restate output-contract or execution-mode details that already belong to the runtime-patched `SKILL.md`

This design relies on a stable runtime assumption:

- headless engine subprocesses run with `cwd=run_dir`

That makes the run-root instruction file discoverable to the engine without polluting the per-attempt skill prompt.

## Skill Prompt Assembly

The skill prompt is assembled in two parts:

1. `skill invoke line`
2. `skill body prompt`

The final assembled prompt is always:

```text
<invoke line>
<body prompt>
```

If the body prompt is empty, the final prompt contains only the invoke line.

### Invoke Line

The invoke line is declared in each engine's `adapter_profile.json` under:

- `prompt_builder.skill_invoke_line_template`

Current engine mappings:

- `codex`: `${{ skill.id }}`
- `claude`: `/{{ skill.id }}`
- `opencode`: `/skills {{ skill.id }}`
- `qwen`: `Invoke skill named {{ skill.id }}`
- `gemini`: `/{{ skill.id }} invoke`

The invoke line is always rendered as the first line of the final prompt.
This table is a documentation projection of each engine profile. If there is any conflict,
`adapter_profile.json -> prompt_builder.skill_invoke_line_template` is the authoritative source.

### Body Prompt

The body prompt carries the actual task context after the skill has been invoked.

Resolution order is fixed:

1. `runner.json.entrypoint.prompts[engine]`
2. `runner.json.entrypoint.prompts.common`
3. adapter profile `body_prefix_extra_block`
4. common body template `server/assets/templates/prompt_body_common.j2`
5. adapter profile `body_suffix_extra_block`

When engine/common prompts are absent, the runtime renders a single shared body template and optionally wraps it with profile-level prefix/suffix extra blocks. The body prompt is responsible only for post-invocation instructions. It must not be the place where the runtime decides how to call the skill.

## Adapter Profile Truth

`adapter_profile.json` is the single configuration source for engine-specific prompt assembly behavior.

Relevant `prompt_builder` fields are:

- `skill_invoke_line_template`
- `body_prefix_extra_block`
- `body_suffix_extra_block`

Prompt builder no longer injects compatibility variables such as `params_json`, `input_prompt`, `input_file`, or `skill_dir`.

## Unified Runtime Pipeline

The prompt organization pipeline is:

1. create-run / run skill materialization
2. render run-root instruction file
3. materialize run-local skill snapshot
4. patch runtime `SKILL.md`
5. assemble invoke line + body prompt
6. pass the final assembled prompt to the engine

The same run-root instruction file remains in effect for:

- first attempt
- resumed attempts
- repair rounds

No extra first-attempt prompt prefix is injected anymore.

## Final `SKILL.md` Composition

Runtime-patched `SKILL.md` is still the only agent-facing sink for skill-local runtime policy and output-contract text.

Its composition order remains:

1. original skill-authored `SKILL.md`
2. `Runtime Enforcement`
3. `Runtime Output Overrides`
4. `Output Format Contract`
5. `Output Contract Details`
6. `Execution Mode`

Prompt assembly and `SKILL.md` patching are related but not the same thing:

- run-root instruction file = global execution constraints
- patched `SKILL.md` = runtime skill-local instructions
- final prompt = invoke line + body prompt

## Audit Semantics

`.audit/request_input.json` continues to store:

- `rendered_prompt_first_attempt`

Its meaning is now narrower:

- it records only the final assembled skill prompt
- it no longer includes any global first-attempt prefix text

If prompt audit fallback is needed, `.audit/prompt.1.txt` stores the same assembled prompt.

## Why the Old Prefix Model Was Removed

The old `global_first_attempt_prefix.j2` model mixed two concerns:

- global engine-agnostic execution constraints
- per-attempt skill invocation prompt

That made prompt auditing less clear and forced a first-attempt special case into adapter runtime code.

The new model removes that coupling:

- global constraints live in run-root instruction files
- skill prompts are assembled uniformly across attempts
- resume and repair rounds reuse the same filesystem-visible instruction file instead of a hidden prefix
