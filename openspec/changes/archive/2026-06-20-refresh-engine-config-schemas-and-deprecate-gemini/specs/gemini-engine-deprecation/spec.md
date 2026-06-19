## ADDED Requirements

### Requirement: Gemini MUST NOT remain an active supported engine

The system MUST treat `gemini` as a deprecated sealed engine implementation rather than an actively supported engine.

#### Scenario: Active engine catalogs exclude Gemini
- **WHEN** the system enumerates supported engines for new runs, model selection, engine management, UI, CLI bootstrap, or e2e forms
- **THEN** `gemini` MUST NOT appear in the supported engine list
- **AND** requests that declare `gemini` as an active engine MUST fail as unsupported

### Requirement: Deprecated Gemini code MUST remain sealed in place

The system MUST preserve `server/engines/gemini/` in the repository while removing active runtime wiring to it.

#### Scenario: Active registries no longer wire Gemini
- **WHEN** engine adapters, auth handlers, auth detectors, model catalogs, or engine upgrade paths are registered
- **THEN** `gemini` MUST NOT be registered
- **AND** no active import chain MUST require `server/engines/gemini/`

### Requirement: Historical Gemini runs MUST remain readable

The system MUST preserve read-only compatibility for historical runs that already contain `.gemini` workspace data or Gemini audit artifacts.

#### Scenario: Old run detail keeps reading .gemini workspace artifacts
- **WHEN** a historical run contains `.gemini` files or old Gemini audit data
- **THEN** run detail, file browsing, and read-only audit inspection MUST continue to work
- **AND** the system MUST NOT re-enable any active Gemini execution, auth, model, or upgrade capability
