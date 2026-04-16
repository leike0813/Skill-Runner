# Proposal

## Why

`server/services/orchestration/run_store.py` currently combines sqlite bootstrap, schema migration, request/run registry, cache persistence, projection/state persistence, recovery metadata, interactive runtime, interaction history, pending auth, and resume ticket workflows in a single 2300+ line class. This makes persistence changes high-risk and keeps `tests/unit/test_run_store.py` as a monolithic regression surface.

## What Changes

- Introduce a dedicated `run-store-modularization` capability for staged `RunStore` decomposition.
- Keep `RunStore` as the public orchestration persistence façade during the full refactor.
- Extract internal store subdomains behind gray, test-first delegation boundaries.
- Split `test_run_store.py` into focused persistence test files as each subdomain becomes stable.

## Safety

- Keep sqlite schema, table names, column names, and persisted JSON payloads compatible.
- Keep `RunStore` public methods and production wiring stable.
- Apply the refactor in staged TDD loops so each extraction lands with dedicated tests plus existing regression coverage.
