# auth-session-governance Specification

## ADDED Requirements

### Requirement: Auth session governance MUST use durable ownership truth

The system MUST persist a durable auth session record that captures ownership, scope, lifecycle status, and TTL metadata.

#### Scenario: auth session created for waiting_auth
- **WHEN** the backend creates a challenge-active auth session
- **THEN** it MUST persist `request_id`, `run_id`, `engine`, `provider_id`, `auth_session_id`, `status`, `auth_method`, `transport`, `created_at`, `updated_at`, and `expires_at`
- **AND** waiting-auth read models MUST reference that durable session rather than inventing a separate ownership truth

### Requirement: Active auth session mutual exclusion MUST be scoped by engine and provider

The system MUST limit active auth session exclusivity to `engine + provider_id`, not the whole process.

#### Scenario: different providers do not block each other
- **GIVEN** one active auth session exists for provider A
- **WHEN** another auth session starts for the same engine but provider B
- **THEN** the second session MAY start

#### Scenario: same scope conflict is visible
- **GIVEN** one active auth session exists for a given `engine + provider_id`
- **WHEN** a different owner tries to start another auth session in the same scope
- **THEN** the backend MUST surface a structured busy condition

### Requirement: Same-owner single-method auth MUST recover active challenge

Single-method auth routes MUST recover a compatible active challenge instead of degrading to method selection.

#### Scenario: recoverable single-method challenge
- **GIVEN** a run in `waiting_auth`
- **AND** its engine/provider only supports one auth method
- **AND** a compatible active auth session already exists for the same owner and scope
- **WHEN** the backend rebuilds waiting-auth state
- **THEN** it MUST re-project `waiting_auth.challenge_active`
- **AND** it MUST NOT demote the run to `waiting_auth.method_selection`

### Requirement: Canceling or terminalizing a run MUST clean owned auth sessions

Run terminal transitions MUST reconcile and clean owned active auth sessions.

#### Scenario: cancel run clears owned auth session
- **GIVEN** a run owns an active auth session
- **WHEN** the run is canceled
- **THEN** the backend MUST cancel or supersede the owned auth session
- **AND** it MUST clear pending auth read models for that request

#### Scenario: terminal run cannot leave orphan active auth session
- **GIVEN** a run reaches `succeeded`, `failed`, or `canceled`
- **WHEN** it still owns an active auth session
- **THEN** the backend MUST reconcile that auth session into a terminal durable state

### Requirement: Auth session TTL MUST be durable and enforceable

Auth session timeout MUST be durably recorded and consistently enforced.

#### Scenario: auth session status exposes TTL truth
- **WHEN** a client reads auth session status
- **THEN** the backend MUST return durable `created_at`, `expires_at`, and current session status

#### Scenario: expired auth session is reconciled
- **GIVEN** an auth session passes its expiry time
- **WHEN** reconciliation runs
- **THEN** the durable session MUST become `expired`
- **AND** waiting-auth state MUST no longer remain challenge-active for that expired session
