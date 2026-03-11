## 1. OpenSpec Artifacts

- [x] 1.1 Create proposal/design/tasks and delta specs for this change.

## 2. Runtime Debug Flag Removal

- [x] 2.1 Remove `debug` from runtime option policy and E2E run form parsing/rendering.
- [x] 2.2 Remove runtime debug option labels/docs/tests while keeping debug bundle routes and buttons unchanged.

## 3. Harness Container Wrapper

- [x] 3.1 Add a supported host-side wrapper script that forwards to `docker compose exec api agent-harness`.
- [x] 3.2 Document local vs container harness entrypoints without changing the native `agent-harness` CLI semantics.

## 4. Scripts Prune

- [x] 4.1 Create `deprecated/scripts/` and `artifacts/scripts/` destinations and move non-supported scripts to their chosen homes.
- [x] 4.2 Update repo references, docs, and tests so no supported path points at migrated scripts.

## 5. Validation

- [x] 5.1 Run targeted tests for E2E runtime option handling, harness behavior, and affected docs/spec references.
- [x] 5.2 Run targeted mypy for touched Python modules.
