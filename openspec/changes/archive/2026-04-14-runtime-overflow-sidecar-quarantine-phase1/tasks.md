## 1. OpenSpec And Docs

- [x] 1.1 Finalize the new change artifacts for overflow sidecar quarantine.
- [x] 1.2 Update run artifact documentation to describe the overflow index and per-line raw sidecars.

## 2. Shared Overflow Quarantine

- [x] 2.1 Add shared overflow quarantine capture support to the NDJSON ingress sanitizer without reintroducing full-line retention in live memory.
- [x] 2.2 Add attempt-scoped overflow sidecar writers and integrate them into adapter process-output capture.
- [x] 2.3 Attach minimal sidecar references to overflow diagnostics while keeping existing sanitized/substituted behavior unchanged.

## 3. Validation

- [x] 3.1 Add or update unit tests for sanitized and substituted overflow sidecar capture and hot-path invariants.
- [x] 3.2 Run targeted runtime tests and `mypy` for the affected overflow and audit modules.
