## 1. Engine Contract Resolution

- [x] 1.1 Add shared manifest engine-resolution validation in `server/services/skill_package_validator.py` for `engines` + `unsupported_engines` with supported set `codex/gemini/iflow`
- [x] 1.2 Enforce rejection for unknown engine names, allowlist/blocklist overlaps, and effective-empty result
- [x] 1.3 Resolve effective engine set when `engines` is missing/empty by defaulting to all supported engines before blocklist subtraction

## 2. Runtime Validation Integration

- [x] 2.1 Ensure installed skill manifest loading uses resolved effective engines in `server/services/skill_registry.py` / model mapping
- [x] 2.2 Replace duplicated run-time engine validation paths in `server/services/workspace_manager.py` and `server/routers/jobs.py` with shared resolution-backed behavior
- [x] 2.3 Align temporary skill staging/execution validation in `server/services/temp_skill_run_manager.py` and `server/routers/temp_skill_runs.py` with the same rules

## 3. Tests and Regression Coverage

- [x] 3.1 Update unit tests for skill package validation to cover default-all behavior, unknown engines, overlap rejection, and effective-empty rejection
- [x] 3.2 Update temporary skill validation and run-route tests to cover new engine contract semantics
- [x] 3.3 Update any run/workspace validation tests that assumed non-empty `engines` was required in manifest input

## 4. Docs and Verification

- [x] 4.1 Update API/dev docs describing `runner.json` engine rules to include optional `engines` and optional `unsupported_engines`
- [x] 4.2 Run `conda run --no-capture-output -n DataProcessing python -u -m mypy server`
- [x] 4.3 Run targeted pytest suites for validator, jobs/temp-run routes, and workspace manager behavior
