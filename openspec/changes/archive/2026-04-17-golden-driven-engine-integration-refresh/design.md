# Design: Golden-Driven Engine Integration Refresh

## Integration Truth Source

Engine integration now reads from:

- `tests/fixtures/protocol_golden/manifest.json`
- `tests/fixtures/protocol_golden/source_runs.json`

Only captured-run fixtures are part of the integration corpus. Synthetic smoke fixtures remain in unit coverage.

## Test Structure

`tests/engine_integration` becomes a pytest package with:

- protocol-core parameterized replay tests
- outcome-core parameterized semantic assertion tests
- corpus completeness coverage

The fixture list is resolved through a small shared registry helper so engine filtering can be applied consistently from the compatibility runner.

## Legacy Compatibility

`tests/engine_integration/run_engine_integration_tests.py` stays as a compatibility shim, but it only launches pytest against the new engine integration package. It no longer reads YAML suites or uses the deleted harness fixture.

`tests/engine_integration/suites/*.yaml` remain in the repository because E2E runners still depend on them. They are no longer the engine integration SSOT.
