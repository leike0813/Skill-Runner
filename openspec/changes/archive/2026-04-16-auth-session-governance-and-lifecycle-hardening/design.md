# Design

## Durable auth session truth

Add a durable auth session record owned by the run-store auth subsystem. The durable record is the canonical truth for:

- session owner (`request_id`, `run_id`)
- scope key (`engine`, `provider_id`)
- auth lifecycle state
- TTL (`created_at`, `updated_at`, `expires_at`)
- challenge metadata (`auth_method`, `challenge_kind`, `transport`, `driver`)
- terminal reason / last error

Existing `request_auth_sessions` and `request_auth_method_selection` remain request-scoped read models for waiting-auth projection, but they no longer act as the source of truth for session ownership.

## Scope-aware mutual exclusion

Replace global `_active_session_id` semantics with scope-aware active lookup keyed by `engine + provider_id`.

Rules:

- one active auth session per `engine + provider_id`
- same-owner retry recovers the active challenge
- cross-owner conflict stays visible as a structured busy condition
- different providers do not block one another

## Cleanup and reconciliation

Run cancellation and terminal transitions must reconcile auth session state:

- canceling a run cancels any active durable auth session owned by that request
- terminal run cleanup marks owned active auth sessions as canceled or superseded
- startup / reconciliation logic expires orphaned or stale sessions and clears waiting-auth read models

## UI-facing waiting_auth behavior

Single-method auth routes must not regress to method selection when a compatible active session can be recovered. Method selection remains valid only when:

- multiple methods exist, or
- recovery is not possible and the system needs to surface a scoped busy error

