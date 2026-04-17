## ADDED Requirements

### Requirement: captured-run golden fixtures MUST drive engine integration coverage

Captured-run golden fixtures MUST be executable through the engine integration test surface rather than living only in unit smoke tests.

#### Scenario: engine integration replay is executed

- **WHEN** engine integration tests are run
- **THEN** they MUST enumerate captured-run `protocol_core` and `outcome_core` fixtures from the golden manifest
- **AND** they MUST assert current protocol/outcome semantics using the shared golden replay harness

### Requirement: engine integration entrypoints MUST no longer depend on YAML suites as their primary truth source

Engine integration entrypoints MUST use the golden fixture corpus as their primary truth source.

#### Scenario: compatibility runner is invoked

- **WHEN** the engine integration compatibility runner is executed
- **THEN** it MUST dispatch to pytest-based golden integration tests
- **AND** it MUST NOT depend on `tests/engine_integration/suites/*.yaml` for engine integration case selection
- **AND** legacy suites MAY remain in the repository only for other consumers such as E2E
