## Why

Current NDJSON overflow handling protects the live path by sanitizing or substituting oversized
non-message rows, but it destructively drops the original oversized line once that substitution
occurs. That makes production failures hard to debug because the runtime can no longer inspect the
actual row that triggered overflow.

## What Changes

- Preserve the original decoded text of overflowed non-message NDJSON lines in dedicated audit
  sidecar files.
- Keep the existing live-path overflow behavior: repaired rows still flow downstream as repaired
  JSON, and unrecoverable rows still flow downstream as runtime diagnostic stubs.
- Add an attempt-scoped overflow index so audit and debugging tools can locate the quarantined raw
  line without rereading `stdout.log` or `io_chunks`.
- Attach minimal sidecar references to overflow diagnostics without changing public protocol event
  types.
- Document the new overflow audit assets in the run artifact contract.

## Capabilities

### New Capabilities

- `runtime-overflow-sidecar-quarantine`: Preserve overflowed NDJSON raw lines in sidecar audit
  files while keeping the live parser on the sanitized or substituted hot path.

### Modified Capabilities

- `engine-adapter-runtime-contract`: Oversized non-message NDJSON ingress behavior now preserves the
  original decoded line in sidecar audit assets instead of destructively dropping it after
  sanitization or substitution.
- `run-audit-contract`: Attempt audit assets now include an overflow index and per-line overflow raw
  sidecars.

## Impact

- Affected code: shared NDJSON ingress sanitizer, adapter process-output capture, runtime audit
  writing, and overflow-related tests.
- Affected docs/specs: engine adapter runtime contract, run audit contract, and `docs/run_artifacts.md`.
- Public APIs, FCMP, and RASP wire shapes remain unchanged.
