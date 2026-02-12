## 1. Trust Manager Service

- [x] 1.1 Add `server/services/run_folder_trust_manager.py` with Codex and Gemini trust add/remove APIs.
- [x] 1.2 Implement path normalization (`Path.resolve()`) and engine-aware trust backends (`codex`, `gemini`, no-op for `iflow`).
- [x] 1.3 Implement lock-protected atomic read-modify-write for `~/.codex/config.toml`.
- [x] 1.4 Implement lock-protected atomic read-modify-write for `~/.gemini/trustedFolders.json`.
- [x] 1.5 Add parse/format repair helpers for malformed trust config files with backup behavior.

## 2. Execution Lifecycle Integration

- [x] 2.1 Integrate trust registration hook in job orchestration before adapter CLI execution.
- [x] 2.2 Integrate trust cleanup hook in a guaranteed finally path after adapter execution.
- [x] 2.3 Ensure cleanup errors do not overwrite run terminal status and are logged.
- [x] 2.4 Add stale-trust cleanup entrypoint in periodic maintenance (best-effort retry path).

## 3. Container Bootstrap

- [x] 3.1 Update `scripts/entrypoint.sh` to ensure `~/.gemini/trustedFolders.json` exists as a JSON object.
- [x] 3.2 Update `scripts/entrypoint.sh` to pre-register parent runs directory trust for Gemini.
- [x] 3.3 Update `scripts/entrypoint.sh` to pre-register parent runs directory trust for Codex (`projects.<path>.trust_level=trusted`).
- [x] 3.4 Keep startup logic idempotent and safe on repeated restarts.

## 4. Tests

- [x] 4.1 Add unit tests for Codex trust add/remove mutation behavior.
- [x] 4.2 Add unit tests for Gemini trustedFolders add/remove mutation behavior.
- [x] 4.3 Add unit tests for malformed config auto-repair and backup behavior.
- [x] 4.4 Add orchestrator tests covering register-before-run and cleanup-after-run (success/failure).
- [x] 4.5 Add container startup script tests (or integration assertions) for trust bootstrap idempotency.

## 5. Documentation

- [x] 5.1 Update `docs/containerization.md` with startup trust bootstrap behavior.
- [x] 5.2 Update `docs/execution_flow.md` with per-run trust lifecycle.
- [x] 5.3 Update `docs/adapter_design.md` to document trust lifecycle responsibilities.
