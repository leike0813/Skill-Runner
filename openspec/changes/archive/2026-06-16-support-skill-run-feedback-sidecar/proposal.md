## Why

Zotero-Skills needs a run-local feedback sidecar so agents can leave maintenance notes after a successful skill run without changing the primary `result.json` output contract. The runner already owns workspace reuse and namespaced result directories, but it does not yet expose a runtime option to request feedback, inject the required instruction, diagnose the sidecar, or include it in normal run bundles.

## What Changes

- Add `runtime_options.collect_skill_run_feedback?: boolean`.
- Include the option in cache keys only when it is `true`.
- Inject the exact feedback sidecar instruction into the tail of the run-local materialized `SKILL.md` only when the option is `true`.
- Keep the source skill package and run-root instruction files unchanged.
- Treat `_skill_run_feedback.md` as an optional sidecar next to the actual `result.json`.
- Log sidecar presence/missing/empty/read failures on successful runs without changing terminal status.
- Include an existing sidecar in normal bundles while leaving `result.json` and business artifacts unchanged.

## Capabilities

### Modified Capabilities
- `interactive-job-api`: Adds the request-level runtime option and validation.
- `skill-patch-modular-injection`: Adds the optional tail patch section and exact text contract.
- `run-file-contract`: Defines the feedback sidecar path, optional status semantics, and bundle inclusion.
- `job-orchestrator-modularization`: Documents successful-run sidecar diagnostics as non-terminal behavior.

## Impact

- API: `POST /v1/jobs` accepts `runtime_options.collect_skill_run_feedback`.
- Cache: `true` requests do not collide with default/false requests.
- Runtime materialization: installed and temp-upload skill snapshots can receive the feedback patch.
- Bundles: normal bundle includes `_skill_run_feedback.md` when present beside a bundled `result.json`.
- Tests/docs: add focused coverage for validation, patch injection, cache key, finalization diagnostics, and bundle content.
