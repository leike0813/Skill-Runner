## Why

The latest structured-output work no longer fits inside a narrow engine-specific hotfix. Runtime now has a shared compatibility pipeline, adapter-profile strategy surface, engine-specific transport artifacts, and post-parse canonicalization. Without a dedicated OpenSpec change, the repository would keep implementation knowledge in code and tests only, which is exactly where SSOT drift starts.

This change records the governance model for structured-output compatibility so future work does not reintroduce scattered Codex/Claude branches, prompt/schema drift, or transport-specific payload leakage into orchestration.

## What Changes

- Add a new OpenSpec change for the structured-output compatibility pipeline and adapter-profile governance model.
- Introduce a new capability that defines fixed runtime pipeline components for:
  - canonical schema passthrough
  - engine-specific compatibility schema translation
  - prompt-contract artifact selection
  - parsed payload canonicalization
- Declare structured-output strategy in `adapter_profile.json` instead of letting command builders and patch injection decide behavior ad hoc.
- Define Codex compatibility artifacts as run-scoped derived transport assets that are generated from the canonical schema without changing the canonical SSOT.
- Define prompt contract selection and schema CLI injection as one coordinated pipeline decision so machine schema and agent-facing summary do not drift apart.
- Keep public HTTP/FCMP/RASP shapes unchanged and keep the canonical `.audit/contracts/target_output_schema.json` as the only machine-truth contract.

## Capabilities

### New Capabilities
- `engine-structured-output-compat-pipeline`: Runtime provides a fixed, profile-driven structured-output compatibility pipeline that can translate engine transport artifacts and canonicalize parsed payloads back to the canonical contract.

### Modified Capabilities
- `engine-adapter-runtime-contract`: Adapter command construction and parsed payload handling now route structured-output behavior through the shared runtime pipeline instead of engine-local special cases.
- `engine-command-profile-defaults`: Adapter profiles now declare structured-output strategies and schema-CLI gating behavior in addition to command defaults.
- `skill-patch-modular-injection`: Output schema patch injection now consumes the pipeline-selected prompt contract artifact instead of assuming the canonical summary is always the correct agent-facing contract.
- `run-audit-contract`: Run-scoped audit assets now allow engine-compatible schema artifacts under `.audit/contracts/` as derived transport/audit files while preserving canonical artifacts as the SSOT.

## Impact

- New OpenSpec change artifacts under `openspec/changes/structured-output-compat-pipeline-profile-governance-2026-04-14/`
- Shared runtime additions in `server/runtime/adapter/common/structured_output_pipeline.py`
- Adapter-profile schema and loader changes
- Codex and Claude command-builder integration through the shared pipeline
- Prompt/schema materialization integration in run bootstrap and skill patch injection
- New pipeline-focused tests and updated command-profile / adapter / bootstrapper regression coverage
- No public API, FCMP, RASP, or `PendingInteraction` shape changes in this slice
