## 1. OpenSpec

- [x] 1.1 Add proposal, design, tasks, and `web-management-ui` delta for the unified run-detail event inspector drawer.

## 2. Management UI

- [x] 2.1 Generalize the existing chat inspector into a shared right-side event inspector in `run_detail.html`.
- [x] 2.2 Route FCMP / RASP / Orchestrator row inspection through the shared drawer and remove inline detail expansion.
- [x] 2.3 Route timeline bubble inspection through the shared drawer and remove inline detail expansion.
- [x] 2.4 Add hover feedback to clickable chat entries without changing existing thinking behavior.

## 3. Validation

- [x] 3.1 Update UI template guards and management page integration tests for unified drawer semantics.
- [x] 3.2 Run targeted pytest coverage for management UI templates/pages.
- [x] 3.3 Run `openspec status --change management-run-detail-unified-event-inspector-drawer-2026-04-15 --json`.
- [x] 3.4 Run `openspec instructions apply --change management-run-detail-unified-event-inspector-drawer-2026-04-15 --json`.
