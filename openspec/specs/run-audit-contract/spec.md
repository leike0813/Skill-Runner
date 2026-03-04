# run-audit-contract Specification

## Purpose
TBD - created by archiving change simplify-temp-skill-lifecycle-and-complete-state-audit-cutover. Update Purpose after archive.
## Requirements
### Requirement: Request Input Snapshot Is Audit-Only

New runs MUST persist request input snapshots at `.audit/request_input.json`.

#### Scenario: New run request snapshot
- WHEN a run is created
- THEN the request payload snapshot is written to `.audit/request_input.json`
- AND no root-level `input.json` is written for that run

### Requirement: Legacy Output Files Are Not Written

New runs MUST NOT write `logs/stdout.txt`, `logs/stderr.txt`, or `raw/output.json`.

#### Scenario: Canonical output paths only
- WHEN a new run produces stdout, stderr, or terminal output
- THEN stdout and stderr are written only to `.audit/stdout.<attempt>.log` and `.audit/stderr.<attempt>.log`
- AND terminal output is written only to `result/result.json`
- AND legacy `logs/stdout.txt`, `logs/stderr.txt`, and `raw/output.json` are absent

### Requirement: Attempt Audit Files Are History Only

Attempt-scoped audit files under `.audit/` MUST be append-only history and MUST NOT be treated as current truth.

#### Scenario: missing audit logs do not change current state
- **WHEN** an attempt audit log is missing
- **THEN** the system MAY emit diagnostics
- **BUT** it MUST keep `.state/state.json` authoritative for current status

### Requirement: Attempt Audit Skeleton Exists Before Turn Started

The runtime MUST initialize the attempt audit skeleton before emitting `lifecycle.run.started`.

#### Scenario: worker claimed before attempt start
- **WHEN** a worker claims dispatch for attempt N
- **THEN** `.audit/meta.N.json`, `.audit/stdout.N.log`, and `.audit/stderr.N.log` MUST exist before `turn.started`

