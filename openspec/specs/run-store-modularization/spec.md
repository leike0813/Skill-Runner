# run-store-modularization Specification

## Requirements

### Requirement: RunStore MUST remain a stable orchestration persistence façade

The system MUST preserve `RunStore` as the public orchestration persistence façade while internal persistence logic is decomposed into dedicated sub-stores.

#### Scenario: Existing callers keep using RunStore

- **WHEN** orchestrator, routers, auth services, interaction services, or observability code need persistence
- **THEN** they MUST continue to call `RunStore`
- **AND** the refactor MUST NOT require broad caller migration during the decomposition change

### Requirement: RunStore decomposition MUST preserve sqlite compatibility

The system MUST preserve the current sqlite schema, table names, column names, and persisted JSON payload shapes throughout the decomposition.

#### Scenario: Database initialization remains compatible

- **WHEN** `RunStore` initializes or reconnects after the sqlite file is deleted
- **THEN** it MUST recreate the existing schema
- **AND** existing read/write behavior MUST remain compatible

#### Scenario: Legacy interactive runtime rows still migrate

- **WHEN** a legacy `request_interactive_runtime` table shape is encountered
- **THEN** the system MUST migrate it into the canonical schema
- **AND** existing session timeout and session handle information MUST be preserved

### Requirement: Dedicated persistence sub-stores MUST preserve request, run, and cache behavior

The system MUST provide dedicated internal stores for request/run registry and cache persistence without changing existing outward behavior.

#### Scenario: Request and run lookup remain stable

- **WHEN** a request is created, bound to a run, and later queried
- **THEN** `RunStore` MUST return the same request/run data shape as before the refactor

#### Scenario: Regular and temp cache remain isolated

- **WHEN** both regular cache and temp-upload cache use the same cache key
- **THEN** the system MUST keep those cache sources isolated
- **AND** `get_cached_run_for_source` MUST continue selecting the correct backing store

### Requirement: Run-store tests MUST shift to subdomain ownership

The system MUST progressively move persistence behavior tests out of the monolithic `tests/unit/test_run_store.py` file and into subdomain-specific test modules.

#### Scenario: Database and request/cache behaviors have dedicated tests

- **WHEN** database bootstrap/migration or request/cache behavior is modified
- **THEN** the primary assertions MUST live in dedicated `run_store_*` test modules
- **AND** `test_run_store.py` MUST trend toward façade smoke and compatibility coverage
