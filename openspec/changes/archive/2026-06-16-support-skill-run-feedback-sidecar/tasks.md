## 1. OpenSpec

- [x] 1.1 Add and validate OpenSpec artifacts for Skill Run Feedback.

## 2. Runtime Option and Cache

- [x] 2.1 Add `collect_skill_run_feedback` to the runtime option allowlist.
- [x] 2.2 Validate the option as boolean when present.
- [x] 2.3 Add true-only feedback token to cache key construction and call sites.

## 3. Patch Injection

- [x] 3.1 Add the exact feedback patch template.
- [x] 3.2 Extend `SkillPatcher` to append feedback as the final `SKILL.md` section only when enabled.
- [x] 3.3 Pass the option through installed and temp-upload run materialization paths.

## 4. Sidecar Diagnostics and Bundle

- [x] 4.1 Add successful-run feedback sidecar diagnostics without changing terminal status.
- [x] 4.2 Include present feedback sidecars in normal bundle candidates beside result files.

## 5. Tests

- [x] 5.1 Add option policy and cache key tests.
- [x] 5.2 Add patch exact-text, tail-position, idempotency, and bootstrap propagation tests.
- [x] 5.3 Add finalization diagnostics tests for present, missing, empty, and read/stat failure cases.
- [x] 5.4 Add bundle inclusion tests for namespaced and legacy sidecars.
- [x] 5.5 Run targeted validation and OpenSpec strict validation.
