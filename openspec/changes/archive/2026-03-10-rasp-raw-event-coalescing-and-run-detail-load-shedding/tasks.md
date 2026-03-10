## 1. OpenSpec

- [ ] 1.1 Add proposal/design/tasks for `rasp-raw-event-coalescing-and-run-detail-load-shedding`.
- [ ] 1.2 Add delta specs for `interactive-job-api`, `ui-engine-management`, `interactive-run-observability`.

## 2. Backend - RASP Coalescing

- [ ] 2.1 Implement raw row coalescer in RASP event build pipeline.
- [ ] 2.2 Preserve block-level `raw_ref` and append coalescing diagnostic code.
- [ ] 2.3 Add unit tests for boundary splitting and byte-range correctness.

## 3. Backend - API Load Shedding

- [ ] 3.1 Add optional `limit` to management protocol history route/service (default 200, max 1000).
- [ ] 3.2 Add timeline history aggregation cache keyed by run audit file signatures.
- [ ] 3.3 Add tests for limit semantics and timeline cache-hit behavior.

## 4. Frontend - Run Detail

- [ ] 4.1 Make timeline lazy-loaded when panel is expanded.
- [ ] 4.2 Skip timeline polling while collapsed.
- [ ] 4.3 Send `limit=200` on protocol history requests and guard overlapping polls.
- [ ] 4.4 Add/adjust UI route semantics tests.

## 5. Docs & Validation

- [x] 5.1 Update `docs/api_reference.md` for `protocol/history` `limit` parameter and raw coalesced line note.
- [x] 5.2 Run targeted pytest and `openspec validate` for this change.

## 6. Strong Consistency Replay Alignment

- [x] 6.1 Make `protocol/history(stream=rasp|fcmp)` terminal path audit-only (no live merge).
- [x] 6.2 Reuse shared raw canonicalizer in live publish path to avoid line-by-line drift.
- [x] 6.3 Add tests for terminal audit-only source and live raw block coalescing behavior.
