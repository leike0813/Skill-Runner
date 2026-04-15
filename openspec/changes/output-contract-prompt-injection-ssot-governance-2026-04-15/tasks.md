## 1. Implementation

- [x] 1.1 Remove run-scoped prompt-facing `.md` output-contract artifacts from schema materialization and structured-output pipeline types.
- [x] 1.2 Replace prompt-summary path handling with in-memory prompt contract text resolution.
- [x] 1.3 Update `skill_patcher` to inject a single dynamic output contract details section and remove interactive pending placeholder logic.
- [x] 1.4 Rewrite `patch_mode_interactive.md` as policy-only while preserving the intent of the current static templates.
- [x] 1.5 Reuse the same dynamic contract builder in `run_output_convergence_service` repair prompts.

## 2. Documentation

- [x] 2.1 Add `docs/output_contract_prompt_injection_ssot.md` describing truth sources, composition order, execution-mode behavior, engine translation, and repair prompt reuse.
- [x] 2.2 Align `docs/misc/GUIDE_output_schema_generation.md` with the new no-`.md` artifact model.
- [x] 2.3 Align `docs/dev_guide.md` output-contract wording with the new model.

## 3. Validation

- [x] 3.1 Update targeted unit tests for schema materialization, structured-output pipeline, skill patching, bootstrap, and repair prompt wiring.
- [x] 3.2 Run targeted pytest coverage for the affected modules.
- [x] 3.3 Run mypy for the touched orchestration/runtime/skill patch modules.
