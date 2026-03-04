# Proposal

This change completes the `.state/.audit/result` cutover and simplifies temporary skill execution so that a skill belongs to the run immediately after create-run.

## Summary

- Temp skills are materialized directly into the run-local skill snapshot during create-run.
- Resumed attempts load only from run-local skill snapshots.
- Runtime no longer depends on temp staging paths after run creation.
- Legacy runtime state/output files stop being written for new runs.
- Request input snapshots move from `input.json` to `.audit/request_input.json`.

## Motivation

Recent failures showed that temp-skill resumed attempts can still fail with `Skill not found` because runtime recovery depended on temp staging or registry fallback instead of the run directory. At the same time, new runs continue to emit legacy files that were already removed from the canonical runtime contract.

## Scope

- Temp skill run-local materialization
- State/audit/result file contract completion
- Legacy state/output file write cutover
- Projection-first reads for new runs

## Non-Goals

- No new top-level runtime states
- No redesign of resume tickets
- No new auth or interaction features
