## 1. OpenSpec Artifacts

- [x] 1.1 Create proposal, design, and delta specs for the structured-output compatibility pipeline slice.
- [x] 1.2 Capture the new runtime pipeline capability together with the modified adapter/profile/patch/audit capabilities.

## 2. Runtime Pipeline Governance

- [x] 2.1 Add a shared structured-output pipeline that resolves the effective machine schema artifact, prompt contract artifact, and parsed payload canonicalization path.
- [x] 2.2 Keep canonical target output schema artifacts as the SSOT and materialize engine-compatible transport artifacts only as derived `.audit/contracts/` assets.
- [x] 2.3 Route Codex and Claude command builders through the shared pipeline for schema CLI argument selection instead of engine-local special-case helpers.
- [x] 2.4 Apply payload canonicalization in the shared adapter runtime so engine transport shims do not leak into orchestration-visible payloads.

## 3. Adapter Profile And Patch Integration

- [x] 3.1 Extend adapter profile schema and loader with declarative structured-output strategy fields and the schema-CLI gate.
- [x] 3.2 Update run skill materialization / skill patch injection so prompt contract selection comes from the shared pipeline rather than assuming canonical summary text.
- [x] 3.3 Keep noop passthrough behavior for engines that do not declare compatibility translation.

## 4. Validation

- [x] 4.1 Add and update targeted tests for profile loading, structured-output pipeline behavior, command builders, adapters, and run bootstrap integration.
- [x] 4.2 Run targeted pytest coverage for the touched structured-output pipeline and adapter integration surfaces.
- [x] 4.3 Run `mypy` on the touched runtime pipeline, command builders, adapter runtime, and schema materialization modules.
- [x] 4.4 Run `openspec status --change structured-output-compat-pipeline-profile-governance-2026-04-14 --json`.
- [x] 4.5 Run `openspec instructions apply --change structured-output-compat-pipeline-profile-governance-2026-04-14 --json`.
