## 1. OpenSpec

- [x] 1.1 Add proposal/design/tasks for `chunked-stdio-journal-and-manual-protocol-rebuild`.
- [x] 1.2 Add delta specs for `run-log-streaming`, `run-audit-contract`, `interactive-run-observability`, `ui-engine-management`, `management-api-surface`.

## 2. Chunk Journal

- [x] 2.1 Extend run audit contract skeleton with `.audit/io_chunks.<attempt>.jsonl`.
- [x] 2.2 Write chunk journal rows in `BaseExecutionAdapter` for stdout/stderr reads (base64 payload, seq, byte range, ts).
- [x] 2.3 Keep existing stdout/stderr plain logs unchanged.

## 3. Manual Protocol Rebuild

- [x] 3.1 Implement strict-replay attempt materialization from audit evidence (`io_chunks + orchestrator + meta`).
- [x] 3.2 Implement backup-before-overwrite at `.audit/rebuild_backups/<timestamp>/attempt-<N>/`.
- [x] 3.3 Add `POST /v1/management/runs/{request_id}/protocol/rebuild` management API.

## 4. Management UI

- [x] 4.1 Add "重构协议" button in Run Observation page.
- [x] 4.2 Add client-side trigger/result rendering and reload protocol panels after success.

## 5. Docs and Tests

- [x] 5.1 Update `docs/api_reference.md` with rebuild API request/response and behavior.
- [x] 5.2 Add/adjust unit tests for io_chunks write, strict replay rebuild/backup, management route, and run detail template hook.

## 6. Forensic Revision

- [x] 6.1 Hard-cut rebuild mode to `strict_replay` only (single path).
- [x] 6.2 Remove rebuild-time compensation injection; only allow replay-natural events.
- [x] 6.3 Enforce strict evidence requirements (`io_chunks + orchestrator + meta`) with per-attempt failure and no overwrite.
- [x] 6.4 Return `mode: strict_replay` and per-attempt `written/reason/source` fields.
- [x] 6.5 Sync OpenSpec/docs wording to strict-replay semantics.
