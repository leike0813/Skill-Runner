# Tasks: refine-in-conversation-auth-method-selection-and-session-timeout

- [x] Update OpenSpec specs for interactive lifecycle, interactive job API, and runtime event payload changes
- [x] Extend interaction/auth models with auth methods, callback URL submission, method-selection payloads, and auth session status response
- [x] Extend run store with pending auth method selection persistence and auth session status aggregation
- [x] Refactor `run_auth_orchestration_service` to support method selection, single-method fast path, backend timeout truth, submission-kind mapping, and busy handling
- [x] Update run interaction/job APIs with auth method selection handling and `GET /v1/jobs/{run_id}/auth/session`
- [x] Update runtime event factories/schema to carry auth phase/method/timeout fields
- [x] Update observability/audit to persist new auth session metadata and busy/timeout diagnostics
- [x] Update e2e client backend/routes to proxy auth session status
- [x] Update `run_observe.html` to use a unified reply area with choice/text widget switching, explicit submit errors, and auth session timeout sync
- [x] Add or update tests for auth method selection, auth session timeout sync, protocol mapping, chat UI semantics, and integration flow
- [x] Run targeted pytest suites and mypy for changed modules
