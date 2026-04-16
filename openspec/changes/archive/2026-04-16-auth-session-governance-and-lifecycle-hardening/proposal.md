# auth-session-governance-and-lifecycle-hardening-2026-04-16

Current in-conversation auth behavior still relies on an implicit mix of:

- process-local active auth session state in `engine_auth_flow_manager`
- request-scoped waiting-auth read models in `run_store`
- UI assumptions about whether a method-selection card means a real auth challenge exists

That leaves three concrete problems:

- canceling a run in `waiting_auth` does not guarantee cleanup of the underlying engine auth session
- auth session mutual exclusion is currently global, so an old session can block unrelated runs
- auth session lifecycle, ownership, and TTL semantics are not governed by a durable machine-readable contract

This change introduces a durable auth session governance layer and hardens lifecycle behavior without changing the canonical run state set or public runtime protocol surface.

## Why

We need auth sessions to be governed as first-class runtime objects rather than incidental side effects of waiting-auth orchestration.

Specifically:

1. auth session ownership must survive beyond process-local memory
2. mutual exclusion must be scoped to `engine + provider_id`, not the whole process
3. cancel, terminal cleanup, and TTL expiration must be explicit and testable
4. single-method auth flows must recover an existing compatible challenge instead of regressing to method selection

