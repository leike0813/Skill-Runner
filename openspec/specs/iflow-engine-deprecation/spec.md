# iflow-engine-deprecation Specification

## Purpose
TBD - created by archiving change deprecate-iflow-engine-2026-04-16. Update Purpose after archive.
## Requirements
### Requirement: IFlow MUST NOT remain an active supported engine

The system MUST treat `iflow` as a deprecated sealed engine implementation rather than an actively supported engine.

#### Scenario: Active engine catalogs exclude iflow

- **WHEN** the system enumerates supported engines for new runs, model selection, engine management, UI, or e2e forms
- **THEN** `iflow` MUST NOT appear in the supported engine list
- **AND** requests that declare `iflow` as an active engine MUST fail as unsupported

### Requirement: Deprecated iflow code MUST remain sealed in place

The system MUST preserve `server/engines/iflow/` in the repository while removing all active runtime wiring to it.

#### Scenario: Active registries no longer wire iflow

- **WHEN** engine adapters, auth handlers, auth detectors, or engine upgrade paths are registered
- **THEN** `iflow` MUST NOT be registered
- **AND** no active import chain MUST require `server/engines/iflow/`

### Requirement: Historical iflow runs MUST remain readable

The system MUST preserve read-only compatibility for historical runs that already contain `.iflow` workspace data or iflow audit artifacts.

#### Scenario: Old run detail keeps reading .iflow workspace artifacts

- **WHEN** a historical run contains `.iflow` files or old iflow audit data
- **THEN** run detail, file browsing, and read-only audit inspection MUST continue to work
- **AND** the system MUST NOT re-enable any active iflow execution, auth, or upgrade capability

