# Proposal: Captured Run Protocol Golden Batch

## Summary

Expand the protocol golden fixture framework from synthetic smoke fixtures to the first real captured-run corpus. This batch adds a machine-readable source-run registry, captured-run fixture extraction, and whole-run / multi-attempt protocol and outcome fixtures derived from 18 real runs recorded in `artifacts/golden_fixture_runs.md`.

## Motivation

The current golden fixture framework proves the contract machinery works, but it still lacks a real corpus that exercises:

- single-attempt success across multiple engines
- whole-run `waiting_user -> succeeded` chains
- rich artifact-bearing success paths
- explicit `success_source` and terminal metadata assertions

Without a captured-run corpus, protocol regressions can still hide behind synthetic smoke coverage.

## Scope

This change will:

- add a machine-readable source-run registry for 18 captured runs
- extend the protocol golden contract to support `captured_run`, `capture_mode`, `attempts`, and `run_artifacts`
- add captured-run extractor support for `protocol_core` and `outcome_core`
- add manifest coverage for 36 fixtures derived from the 18 runs
- add whole-run protocol and outcome smoke coverage

This change will not:

- add parser-only captured fixtures
- add byte-for-byte FCMP/RASP snapshots
- change runtime public protocol types
- add UI-specific bubble or revision semantics to fixture expectations
