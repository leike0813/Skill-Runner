## Why

Current skill manifest validation requires `assets/runner.json.engines` to be a non-empty list, which makes simple package authorship and migration harder when a skill should support "all engines except a few". We need a first-class blocklist model so engine compatibility is explicit, validated early, and consistent across installed and temporary skills.

## What Changes

- Make `runner.json.engines` optional; when omitted or empty, default candidate engines to all system-supported engines (`codex`, `gemini`, `iflow`).
- Add optional `runner.json.unsupported_engines` to explicitly block engines.
- Enforce validation rules:
- Reject unknown engine names in either `engines` or `unsupported_engines`.
- Reject overlaps between `engines` and `unsupported_engines`.
- Reject manifests whose effective supported-engine set becomes empty after applying the blocklist.
- Apply the same manifest rules to both skill package install validation and temporary skill validation paths.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `skill-package-install`: Relax and redefine engine declaration validation with optional allowlist + optional blocklist semantics.
- `ephemeral-skill-validation`: Align temporary skill manifest engine validation with install-time semantics, including unknown/overlap/effective-empty rejection.

## Impact

- Affected code: skill manifest validation and runtime engine checks in `server/services/skill_package_validator.py`, `server/services/workspace_manager.py`, `server/routers/jobs.py`, and `server/routers/temp_skill_runs.py`.
- Affected API behavior: error messages and acceptance criteria for skill packages and temporary skill uploads using `runner.json`.
- Affected docs/specs: OpenSpec delta specs for `skill-package-install` and `ephemeral-skill-validation`.
