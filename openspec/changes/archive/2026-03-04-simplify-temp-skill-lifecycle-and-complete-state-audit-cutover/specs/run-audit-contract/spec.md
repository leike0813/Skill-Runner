## ADDED Requirements

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
