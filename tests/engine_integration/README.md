# Engine Integration Tests

This directory now hosts the golden-driven engine integration test surface.

- Main corpus: `tests/fixtures/protocol_golden/manifest.json`
- Source registry: `tests/fixtures/protocol_golden/source_runs.json`
- Pytest tests: `tests/engine_integration/test_*golden*_integration.py`
- Compatibility runner: `tests/engine_integration/run_engine_integration_tests.py`
- Wrapper: `tests/engine_integration/run_engine_integration_tests.sh`

## Current model

- `protocol_core` and `outcome_core` captured-run fixtures are the primary engine integration regression surface.
- Tests replay current protocol/outcome builders against the captured run corpus.
- Old YAML suites under `tests/engine_integration/suites/` are retained only for legacy E2E compatibility and are no longer the engine integration SSOT.

## Recommended usage

Run the full engine integration corpus:

```bash
tests/engine_integration/run_engine_integration_tests.sh
```

Filter by fixture keyword:

```bash
tests/engine_integration/run_engine_integration_tests.sh -k literature
```

Filter by engine:

```bash
tests/engine_integration/run_engine_integration_tests.sh -e codex
```
