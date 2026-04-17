# Design: Captured Run Protocol Golden Batch

## Source of Truth

`artifacts/golden_fixture_runs.md` remains a human-readable campaign note. Automation reads only:

- `tests/fixtures/protocol_golden/source_runs.json`
- `data/runs/<run_id>/...`

## Fixture Strategy

Each captured run yields two fixtures:

- `protocol_core`
- `outcome_core`

Multi-attempt runs remain whole-run fixtures. The corpus does not split them into per-attempt fixture IDs.

## Protocol Expectations

Captured `protocol_core` fixtures do not reuse historical FCMP/RASP files as golden snapshots. Instead they derive stable semantic expectations from:

- attempt `meta.N.json`
- attempt `pending_context`
- terminal `completion`

This keeps the fixture aligned with the current replay harness while avoiding unstable historical diagnostics such as engine deprecation warnings or overflow repair counts.

Stable protocol assertions are limited to:

- run status lifecycle
- completion state / reason / source
- waiting-user interaction requirements
- FCMP state transitions and terminal completion source

## Outcome Expectations

Captured `outcome_core` fixtures assert semantic subsets derived from:

- `result/result.json`
- final `meta.N.json`
- `.state/state.json`

The fixtures capture:

- final status
- result status
- `success_source`
- category-specific result payload fields
- artifacts
- validation warnings
- terminal completion reason/source
