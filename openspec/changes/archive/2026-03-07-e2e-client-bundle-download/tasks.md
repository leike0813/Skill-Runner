## 1. OpenSpec Artifacts

- [x] 1.1 Finalize proposal/design/tasks for E2E bundle download.
- [x] 1.2 Add delta specs for `builtin-e2e-example-client` and `interactive-job-api`.

## 2. E2E Backend Proxy

- [x] 2.1 Add `/api/runs/{request_id}/bundle/download` route in `e2e_client/routes.py`.
- [x] 2.2 Ensure route returns zip attachment headers and binary payload from backend bundle API.
- [x] 2.3 Keep backend/network exception mapping aligned with existing E2E proxy error policy.

## 3. E2E UI Integration

- [x] 3.1 Add “Download bundle” action to `run_observe` file panel.
- [x] 3.2 Wire action to the new E2E proxy download route.
- [x] 3.3 Add i18n keys/messages for download label and failure hints.

## 4. Tests and Validation

- [x] 4.1 Add/adjust unit tests for E2E proxy bundle download route.
- [x] 4.2 Update E2E UI semantics tests to assert download action exists.
- [x] 4.3 Run `openspec validate --changes e2e-client-bundle-download`.
