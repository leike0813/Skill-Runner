# Design

## Temp Skill Lifecycle

Temp skills are imported once and then become indistinguishable from installed skills during execution:

1. Upload zip
2. Validate and unpack into a temporary import workspace
3. Materialize into `data/runs/<run_id>/.<engine>/skills/<skill_id>/...`
4. Clear import-only temporary paths
5. All attempts and resumes load from the run-local snapshot

Temp staging is no longer a runtime dependency.

## Canonical Files

### State

- `.state/state.json`
- `.state/dispatch.json`

### Terminal

- `result/result.json`

### Audit

- `.audit/request_input.json`
- `.audit/meta.<attempt>.json`
- `.audit/orchestrator_events.<attempt>.jsonl`
- `.audit/events.<attempt>.jsonl`
- `.audit/fcmp_events.<attempt>.jsonl`
- `.audit/stdin.<attempt>.log`
- `.audit/stdout.<attempt>.log`
- `.audit/stderr.<attempt>.log`
- `.audit/pty-output.<attempt>.log`
- `.audit/fs-before.<attempt>.json`
- `.audit/fs-after.<attempt>.json`
- `.audit/fs-diff.<attempt>.json`
- `.audit/parser_diagnostics.<attempt>.jsonl`
- `.audit/protocol_metrics.<attempt>.json`

## Legacy Cutover

The following files are no longer canonical and must not be written for new runs:

- `status.json`
- `current/projection.json`
- `interactions/pending.json`
- `interactions/pending_auth.json`
- `interactions/pending_auth_method_selection.json`
- `interactions/history.jsonl`
- `interactions/runtime_state.json`
- `logs/stdout.txt`
- `logs/stderr.txt`
- `raw/output.json`
- `input.json`

## Recovery Source Order

1. `skill_override`
2. run-local skill snapshot
3. registry fallback only for compatible non-resume flows

Resumed attempts must not rely on temp staging.
