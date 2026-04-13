## 1. Run Output Schema Builder

- [x] 1.1 Add a run-scoped output schema materialization service that builds `auto` final wrapper schema and `interactive` union schema.
- [x] 1.2 Materialize stable `.audit/contracts/target_output_schema.json` and `.md` artifacts and expose stable run-option fields.
- [x] 1.3 Persist first-attempt request-input audit fields for the materialized schema artifact paths.

## 2. Runtime Integration

- [x] 2.1 Update run skill materialization to consume the new service before patching `SKILL.md`.
- [x] 2.2 Refactor `skill_patcher` so output schema injection consumes materialized markdown instead of raw schema objects.
- [x] 2.3 Wire job execution to propagate stable schema artifact paths through internal `run_options`.

## 3. Validation

- [x] 3.1 Add unit tests for the new output schema service, including `auto`, `interactive`, and missing-schema cases.
- [x] 3.2 Update bootstrapper and skill patcher tests to assert materialized markdown consumption and fixed artifact paths.
- [x] 3.3 Run the targeted unit suites for output schema materialization and patching.
