# Proposal: Protocol Golden Fixture Framework Foundation

## Summary

Add the first foundation change for protocol-core golden fixtures. This change does not attempt to build a large sample corpus. It establishes a machine-readable fixture contract, shared loader/normalizer/assertion tools, and a minimal smoke path for protocol-core and outcome-core fixtures.

## Motivation

Runtime protocol contracts are now stable enough to support golden fixtures, but the repository still lacks:

- a single machine-readable golden fixture contract
- capability-aware fixture gating tied to parser capability SSOT
- shared normalization rules for unstable protocol fields
- a semantic assertion harness for RASP / FCMP / outcome comparisons

Without that foundation, future mock and integration frameworks would either duplicate ad hoc fixture logic or overfit to current implementation details.

## Scope

This change will:

- add a protocol golden fixture schema and manifest
- add loader, normalizer, and semantic assertion helpers
- support `parser_only`, `protocol_core`, and `outcome_core` fixture layers
- add a minimal `common` outcome smoke fixture and a minimal `codex` protocol smoke fixture
- keep `auth_detection_samples` as raw evidence corpus rather than renaming or migrating it

This change will not:

- add UI / HTML / page snapshot fixtures
- add a large real-run golden corpus
- change FCMP / RASP public event types
- change runtime protocol semantics
