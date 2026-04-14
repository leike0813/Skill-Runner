## 1. OpenSpec

- [x] 1.1 Create a dedicated OpenSpec change for Codex headless sandbox runtime probe and effective fallback semantics.
- [x] 1.2 Capture the implemented scope without broadening into Codex UI shell launch policy changes.

## 2. Codex Sandbox Governance

- [x] 2.1 Add a Codex-specific sandbox probe sidecar and runtime-unavailable detection for bubblewrap failures.
- [x] 2.2 Route Codex headless command fallback through the persisted probe result so unavailable sandbox runs use `--yolo`.
- [x] 2.3 Route Codex headless config composition through the same probe result so unavailable sandbox runs use `sandbox_mode = "danger-full-access"`.
- [x] 2.4 Upgrade Codex sandbox status collection to report dependency-missing / runtime-unavailable probe results.

## 3. Validation

- [x] 3.1 Add or update unit tests for disabled, dependency-missing, runtime-unavailable, and available probe outcomes.
- [x] 3.2 Add or update command/config regression tests for Codex headless start/resume fallback behavior.
- [x] 3.3 Run targeted pytest and `mypy` on the affected Codex headless sandbox modules.
