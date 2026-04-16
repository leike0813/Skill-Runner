## Why

Sample run `8ed4484f-7a9d-4f7f-a203-b2c231369424` showed that engine-native failure semantics are already present in raw runtime evidence but are not being promoted into canonical runtime events. The audit trail contained a semantic `turn.failed` row with the real usage-limit message, yet the terminal projection, `result.json`, and user-facing chat replay all degraded to `Exit code 1`.

The same sample also showed that generic engine rows such as `type:"error"` and `item.type:"error"` are valuable diagnostics, but they should not be treated as lifecycle truth. Today they remain only as raw rows, which leaves no structured, cross-engine diagnostic surface for downstream audit, observability, or UI diagnostics.

## What Changes

- Add `agent.turn_failed` as a canonical RASP turn marker.
- Promote engine-native `turn.failed` rows into `agent.turn_failed` while preserving raw evidence.
- Govern generic engine error-like rows by emitting `diagnostic.warning` with cross-engine pattern metadata, without treating them as terminal lifecycle truth.
- Prefer semantic turn-failure messages over generic non-zero-exit summaries when computing terminal error text.

## Capabilities

### Added Capabilities

- `runtime-turn-failure-governance`: runtime protocol and parser normalization now recognize semantic turn failure and structured engine-error diagnostics separately.

## Impact

- Affected code: runtime protocol schema/invariants/docs, Codex parser normalization, runtime event protocol/live publishing, terminal error summarization, and observability/chat replay derivation.
- Affected tests: runtime protocol, adapter parsing, outcome summarization, chat replay derivation, observability, and protocol-state alignment.
