# Dynamic Output Contract Generation

## Current Model

The runtime output contract now has a single machine source and a single agent-facing text sink:

- Machine truth: `.audit/contracts/target_output_schema.json`
- Agent-facing text sink: runtime-patched `SKILL.md`

Standalone run-scoped Markdown summary artifacts are no longer generated.

For the full governance model, see:

- [output_contract_prompt_injection_ssot.md](/home/joshua/Workspace/Code/Python/Skill-Runner/docs/output_contract_prompt_injection_ssot.md)

## Generation Flow

1. Load the skill business schema from `assets/output.schema.json`
2. Build the canonical final wrapper or interactive union schema
3. Materialize the canonical JSON Schema artifact
4. Optionally translate to an engine-specific compat schema
5. Render dynamic output contract details from the engine-effective schema
6. Inject the result into runtime `SKILL.md`
7. Reuse the same rendered contract text for repair prompts

## Injection Layout

The runtime-patched `SKILL.md` is assembled in this order:

1. Original skill `SKILL.md`
2. `Runtime Enforcement`
3. `Runtime Output Overrides`
4. `Output Format Contract`
5. `Output Contract Details`
6. `Execution Mode`

Only step 5 is schema-derived dynamic content.

## Responsibility Split

### Static templates

- `patch_runtime_enforcement.md`
- `patch_artifact_redirection.md`
- `patch_output_format_contract.md`
- `patch_mode_auto.md`
- `patch_mode_interactive.md`

### Dynamic builder

`server/services/skill/skill_patch_output_schema.py` renders the field-level contract by filling static Markdown templates:

- field table
- required markers
- `additionalProperties` note
- artifact-field guidance
- final example
- interactive pending-branch note and example when applicable

The main static shell is `server/assets/templates/patch_output_contract_details.md`, with optional generic subtemplates for shared note blocks. Engine-specific note text can stay in code when it is not appropriate for the shared template directory.

### Engine translation

`server/runtime/adapter/common/structured_output_pipeline.py` decides whether prompt contract text is rendered from:

- canonical schema
- or engine compat schema

This keeps CLI schema injection and injected prompt wording aligned.

## Interactive Mode Rule

`patch_mode_interactive.md` is policy-only. It does not restate field-level pending schema details. Those details come only from the dynamic output contract section.

## Audit Rule

The retained run-scoped audit asset is the canonical `.json` schema artifact.

The removed run-scoped audit asset is the standalone `.md` prompt summary. Prompt text now lives only in:

- patched `SKILL.md`
- repair prompts derived from the same builder
