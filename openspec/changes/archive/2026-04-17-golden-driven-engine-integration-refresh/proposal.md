# Proposal: Golden-Driven Engine Integration Refresh

## Summary

Refresh `tests/engine_integration` so captured-run protocol golden fixtures become the primary engine integration regression surface. Replace the legacy YAML-driven integration runner with pytest-based golden integration tests, while retaining old suites only for E2E compatibility.

## Motivation

The repository now has a real captured-run golden corpus, but engine integration still points to an older YAML suite runner that no longer reflects the current protocol/outcome testing model. This leaves:

- real captured-run fixtures underused
- engine integration disconnected from the golden framework
- duplicated and stale testing entrypoints

## Scope

This change will:

- add pytest-based engine integration tests driven by captured-run golden fixtures
- move captured-run replay coverage out of `tests/unit`
- convert the engine integration runner into a thin compatibility shim that dispatches to pytest
- document that `tests/engine_integration/suites/*.yaml` remain only for E2E legacy coverage

This change will not:

- change HTTP APIs or runtime protocol types
- remove the legacy suites used by E2E
- add parser-only captured-run integration coverage
