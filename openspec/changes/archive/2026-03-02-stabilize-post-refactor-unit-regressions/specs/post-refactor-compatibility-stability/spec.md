## ADDED Requirements

### Requirement: Asyncified store callchains MUST remain await-consistent
All services, routers, background tasks, and tests MUST use `await` when interacting with asyncified stores and managers.

#### Scenario: Async store values are consumed correctly
- **WHEN** code or tests call async store methods such as `get_request`, `get_cached_run`, or `get_pending_interaction`
- **THEN** they MUST await the returned coroutine
- **AND** they MUST NOT treat coroutine objects as already-materialized values

### Requirement: Extracted orchestration lifecycle MUST preserve behavior without compatibility shims
The system MUST preserve orchestration behavior after lifecycle extraction without adding wrapper shims to emulate legacy internals.

#### Scenario: Cancel requested before execution
- **WHEN** a run has `cancel_requested=true` before adapter execution starts
- **THEN** the canonical lifecycle pipeline MUST short-circuit before adapter execution
- **AND** the run MUST transition to `canceled`

#### Scenario: Cancel running run
- **WHEN** `cancel_run` is invoked for a running run
- **THEN** the canonical cancel flow MUST persist `cancel_requested`
- **AND** it MUST update terminal artifacts and status consistently with current public behavior

### Requirement: Engine version reads MUST remain cache-backed
Engine version reads MUST continue using the persisted cache instead of probing CLIs on read paths.

#### Scenario: Model registry resolves version from cache
- **WHEN** `model_registry` resolves a version for engine manifests
- **THEN** it MUST read from `engine_status_cache_service`
- **AND** it MUST NOT invoke probe-on-read detection

### Requirement: Runtime-facing ports MUST be runtime-neutral
Runtime-facing observability modules MUST depend only on runtime-neutral or shared port definitions.

#### Scenario: Runtime import boundary
- **WHEN** runtime observability modules import the job-control protocol
- **THEN** they MUST import it from a runtime-neutral module
- **AND** they MUST NOT import `server.services.orchestration.*`

### Requirement: Stabilization tests MUST reflect current UI behavior
Stabilization changes MUST update stale tests to the current user-facing behavior rather than restoring obsolete contracts.

#### Scenario: E2E observation agent messages
- **WHEN** the observation client receives `agent_message`
- **THEN** tests MUST accept that it appears in chat bubbles
- **AND** they MUST NOT require filtering of the last structured done message
