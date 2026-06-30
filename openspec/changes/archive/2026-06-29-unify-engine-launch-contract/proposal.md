## Why

Engine execution currently relies on `BaseExecutionAdapter` spawning every CLI with `cwd=run_dir`, but individual CLIs still resolve project roots, config files, and skill directories through engine-specific rules. Kilo exposed this gap: the subprocess cwd was correct, yet config and skill discovery still needed explicit launch anchoring to avoid drift.

## What Changes

- Add a shared engine launch contract that treats `run_dir` as the canonical execution root and makes launch cwd/config/skill root anchoring explicit.
- Add profile-declared launch metadata for cwd strategy, config environment variable, and run directory CLI flag.
- Add a context-aware execution environment hook so adapters can derive env from `AdapterExecutionContext` and composed config path.
- Harden Kilo by launching with `--dir <run_dir>` and `KILO_CONFIG=<run_dir>/.kilo/kilo.jsonc`.
- Make run-local skill materialization and harness skill injection derive target paths from adapter profile workspace metadata instead of `f".{engine}"`.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `engine-adapter-runtime-contract`: adapter launch must explicitly bind cwd/config/project-root semantics to `run_dir` through profile or adapter-local launch behavior.
- `engine-runtime-config-layering`: composed runtime config paths must be available to the launch environment when an engine declares a config env var.
- `temp-skill-run-local-materialization`: run-local skill snapshot paths must be derived from adapter profile workspace metadata.
- `external-runtime-harness-environment-paths`: harness skill injection targets must use the same profile-derived workspace layout as API execution.

## Impact

- Updates adapter profile schema/profile loader, active engine profiles, base adapter launch flow, Kilo command/env behavior, run skill materialization, interactive resume snapshot loading, harness injection, and related tests.
- No public HTTP API, run request DTO, auth API, or model registry API changes.
- Kilo CLI behavior becomes more deterministic by using official `--dir` and `KILO_CONFIG` launch anchors.
