## 1. OpenSpec

- [x] 1.1 Add proposal/design/tasks for `live-publisher-single-source-observability-consistency`.
- [x] 1.2 Add delta specs for `interactive-job-api`, `interactive-run-observability`, `ui-engine-management`.

## 2. Live Publisher

- [x] 2.1 Add mirror drain capability for FCMP/RASP mirror writers and publishers.
- [x] 2.2 Add shared `flush_live_audit_mirrors(run_id)` helper.

## 3. Run Observability

- [x] 3.1 Remove `fcmp/rasp` query-time materialize trigger in `list_protocol_history`.
- [x] 3.2 Add terminal-path mirror flush before audit-only read.

## 4. Tests

- [x] 4.1 Add/adjust run_observability tests for terminal flush and no query-time materialize.
- [x] 4.2 Add live publisher mirror drain test to prove audit mirror visibility after flush.
