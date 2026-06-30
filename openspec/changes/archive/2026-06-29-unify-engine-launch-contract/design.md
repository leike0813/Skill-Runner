## Context

The current runtime execution path composes config, validates the run folder, renders the prompt, and finally spawns the engine CLI with `cwd=run_dir`. That ensures process cwd, but it does not guarantee that the engine's own project root, config file, and skill discovery root are all anchored to the same run directory.

Kilo makes the gap visible because it supports both project config discovery and explicit launch overrides:

- `kilo run --dir <path>` selects the run/project directory.
- `KILO_CONFIG=<file>` loads a specific config file.
- `skills.paths` in `kilo.jsonc` can explicitly add run-local skill roots.

The fix should be a shared contract rather than a one-off Kilo patch.

## Design Decisions

1. **`run_dir` remains the canonical execution root**
   The base adapter continues to spawn with `cwd=run_dir`. This change does not introduce alternative cwd strategies.

2. **Launch anchoring is profile-declared**
   Adapter profiles gain a `launch` block. The shared loader validates it and exposes it as typed profile metadata. The first supported `cwd_strategy` is `run_dir`; engines may additionally declare a config env var and a CLI flag used to pass `run_dir`.

3. **Execution env becomes context-aware**
   `EngineExecutionAdapter` keeps `build_subprocess_env(base_env)` for compatibility, and adds `build_execution_env(base_env, ctx, config_path)`. The default implementation delegates to the old method. Engines that need config-path-aware env can override the new hook.

4. **Kilo uses both project and config anchors**
   Kilo command builders receive `AdapterExecutionContext` and insert `--dir <run_dir>` after `run`. Kilo execution env sets `KILO_CONFIG` to the composed `.kilo/kilo.jsonc` path. Existing explicit `skills.paths` injection stays because it stabilizes skill discovery independent of Kilo's hidden-directory glob behavior.

5. **Skill snapshot paths use profile metadata**
   `RunFolderBootstrapper.snapshot_dir()` resolves the target through adapter profile `attempt_workspace.workspace_subdir` and `skills_subdir`. Interactive resume fallback and harness injection use the same resolver.

## Architecture

### Adapter Profile

The new profile block has this shape:

```json
{
  "launch": {
    "cwd_strategy": "run_dir",
    "config_env_var": "KILO_CONFIG",
    "run_dir_flag": "--dir"
  }
}
```

For engines without explicit config or run-dir flags, `config_env_var` and `run_dir_flag` are `null`.

### Base Adapter Flow

The base run flow carries `config_path` from config composition into process execution. Command construction still uses existing `build_start_command` and `build_resume_command` wrappers, which already pass `ctx` to builders that accept it. Environment construction moves from `build_subprocess_env(os.environ.copy())` to `build_execution_env(os.environ.copy(), ctx, config_path)`.

### Kilo

Kilo command shape becomes:

```text
kilo run --dir <run_dir> --format json --auto --model <runtime_model> <prompt>
kilo run --dir <run_dir> --format json --auto --session <session_id> --model <runtime_model> <prompt>
```

The Kilo adapter sets:

```text
KILO_CONFIG=<run_dir>/.kilo/kilo.jsonc
```

### Materialization And Harness

Run-local skill snapshots are resolved as:

```text
run_dir / profile.attempt_workspace.workspace_subdir / profile.attempt_workspace.skills_subdir / skill_id
```

The harness uses the same profile-derived target root when injecting project and fixture skills, and records the resulting target root in audit metadata.

## Failure Handling

- Missing or invalid launch profile fields fail during adapter profile validation.
- Kilo config path is only injected after config composition; if config composition fails, the engine is not launched.
- Existing engines with `config_env_var=null` and `run_dir_flag=null` retain current command/env behavior.
- If profile loading fails for a run-local snapshot path, the existing runtime error path is used rather than silently falling back to `f".{engine}"`.
