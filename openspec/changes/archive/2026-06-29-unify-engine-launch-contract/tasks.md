## 1. OpenSpec

- [x] 1.1 Create proposal, design, delta specs, and task list for `unify-engine-launch-contract`.
- [x] 1.2 Validate the change with `openspec validate unify-engine-launch-contract --strict`.

## 2. Adapter Launch Contract

- [x] 2.1 Add `launch` schema/profile metadata with `cwd_strategy`, `config_env_var`, and `run_dir_flag`.
- [x] 2.2 Add context-aware `build_execution_env(base_env, ctx, config_path)` and thread `config_path` into process execution.
- [x] 2.3 Update active engine profiles to declare launch behavior.

## 3. Kilo Launch Hardening

- [x] 3.1 Set Kilo `KILO_CONFIG` to the composed run-local config path during execution.
- [x] 3.2 Add `--dir <run_dir>` to Kilo start/resume commands without changing model/session semantics.
- [x] 3.3 Apply the same profile-driven run-dir flag contract to OpenCode so it does not rely on subprocess cwd alone.

## 4. Profile-Driven Skill Roots

- [x] 4.1 Make run-local skill materialization paths derive from adapter profile workspace metadata.
- [x] 4.2 Make interactive resume run-local skill loading use the same profile-derived path.
- [x] 4.3 Make harness project/fixture skill injection use profile-derived target roots.

## 5. Tests

- [x] 5.1 Update/add unit tests for profile launch validation, base execution env, Kilo command/env, run-local materialization, and harness injection.
- [x] 5.2 Run the focused pytest suite from the plan.
