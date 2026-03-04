## 1. Canonical Auth Completion Contract

- [x] 1.1 Update SSOT contracts so `auth.completed` and `waiting_auth -> queued` require canonical auth completion only.
- [x] 1.2 Retire `auth_ready` from runtime docs, schema docs, API docs, and main OpenSpec specs.
- [x] 1.3 Add explicit invariants for waiting-auth idempotence, no-resume-until-auth-complete, and single-method busy recovery.

## 2. Runtime and Orchestration Cleanup

- [x] 2.1 Remove `auth_ready` from engine auth session runtime models and session lifecycle code.
- [x] 2.2 Refactor waiting-auth reconciliation and resume issuance so non-terminal challenge snapshots cannot trigger queued/running transitions.
- [x] 2.3 Tighten FCMP/order-gate/protocol mappings so readiness-like signals never translate into `auth.completed`.

## 3. Engine Observability Cleanup

- [x] 3.1 Replace engine static `auth_ready` observability with `credential_state`.
- [x] 3.2 Update engine/auth models, routes, and related docs/tests to use non-completion credential observability.

## 4. Regression Guards

- [x] 4.1 Add contract tests for canonical auth completion and retired `auth_ready` semantics.
- [x] 4.2 Add runtime/orchestration tests for waiting-auth polling idempotence and single-method busy recovery.
- [x] 4.3 Add integration regressions ensuring no resume occurs until explicit auth completion.
