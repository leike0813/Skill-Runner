## Why

The current output-contract prompt chain still spreads one logical contract across multiple places: run-scoped Markdown summary artifacts, mode templates that restate schema details, and repair prompts that can drift from `SKILL.md`. That duplication makes the wording unstable, increases audit surface without adding truth, and risks engine-specific schema transport diverging from agent-visible instructions.

## What Changes

- Remove run-scoped prompt-facing `.md` output-contract artifacts and keep only canonical machine `.json` schema artifacts.
- Make runtime-patched `SKILL.md` the only agent-facing text contract sink.
- Introduce a single dynamic output-contract builder that is reused by both `SKILL.md` injection and repair prompts.
- Re-scope `patch_mode_interactive.md` so it expresses interactive behavior policy only and no longer duplicates pending-branch field details.
- Formalize the structured-output pipeline so engine compat translation governs both CLI schema injection and prompt-contract rendering.
- Add a dedicated SSOT doc describing contract truth, composition order, execution-mode variation, engine translation, and the final runtime `SKILL.md` layout.

## Capabilities

### New Capabilities
- `engine-structured-output-compat-pipeline`: Declare the runtime pipeline that translates canonical schema into engine-effective machine schema and matching prompt-contract text.

### Modified Capabilities
- `skill-patch-modular-injection`: The patch plan and injected `SKILL.md` layout now use a single dynamic output-contract details section and remove repeated mode-level schema detail blocks.
- `engine-adapter-runtime-contract`: Adapter/runtime contract now requires prompt-contract selection to stay aligned with engine-effective schema injection.
- `output-json-repair`: Repair prompts now reuse the same dynamic output-contract source used for runtime `SKILL.md` injection.
- `run-audit-contract`: Run audit keeps canonical `.json` schema artifacts but no longer persists prompt-facing `.md` contract artifacts.

## Impact

- Affected code: `run_output_schema_service`, `structured_output_pipeline`, `skill_patch_output_schema`, `skill_patcher`, `run_output_convergence_service`, run bootstrap/materialization wiring, static patch templates.
- Affected docs: new `docs/output_contract_prompt_injection_ssot.md`, plus aligned updates in `docs/misc/GUIDE_output_schema_generation.md` and `docs/dev_guide.md`.
- Affected tests: schema materialization, structured-output pipeline, skill patcher, bootstrap, and convergence prompt generation.
