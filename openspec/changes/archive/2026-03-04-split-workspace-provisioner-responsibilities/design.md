# Design: split-workspace-provisioner-responsibilities

## Context

The current execution flow mixes run-scope and attempt-scope work:

- create-run materializes a run-local skill snapshot
- every non-reply attempt still calls adapter-side workspace preparation
- that preparation still performs skill copy/install work

This causes resumed attempts to re-enter a code path that can mutate the run-local snapshot even though the snapshot should already be canonical.

## Goals

- separate one-time run-folder preparation from per-attempt validation
- keep per-attempt config generation independent from run-folder mutation
- hard-fail attempts when the run folder no longer satisfies the minimal execution contract
- remove the canonical `workspace provisioner` naming and replace it with role-accurate components

## Non-Goals

- no external API changes
- no runtime protocol/schema changes
- no automatic repair or fallback-to-registry behavior on run-folder drift

## Decisions

### 1. RunFolderBootstrapper is create-run only

`RunFolderBootstrapper` owns run-scope skill preparation:

- installed skill copy into `data/runs/<run_id>/.<engine>/skills/<skill_id>`
- temporary skill unzip into the same run-local snapshot layout
- one-time `SKILL.md` patching
- snapshot directory shaping so later attempts can consume `assets/runner.json` and schemas in place

It does not run for later attempts.

### 2. AttemptConfigComposer remains per-attempt

Config generation remains per-attempt because it depends on current runtime options, model selection, and adapter profile defaults. The existing `config_composer` concept stays intact and is not folded into bootstrap.

### 3. AttemptRunFolderValidator is per-attempt and non-destructive

Each non-reply attempt validates the minimal execution contract before starting the engine process.

Validation checks:

- run-local skill directory exists
- `SKILL.md` exists
- `assets/runner.json` exists and is valid JSON
- `runner.json.schemas` contains `input`, `parameter`, and `output`
- referenced schema files exist
- the current attempt config file exists

Validation failures hard-fail the attempt. The validator must not repair, reinstall, or re-select the skill source.

### 4. Orchestration owns canonical skill-source resolution

Before adapter execution:

- orchestration resolves the canonical `SkillManifest`
- run-local snapshot remains the preferred source for created runs
- adapter-side runtime common consumes the resolved manifest only

Adapter code must not reopen source selection through registry, temp staging, or `skill_override`.

### 5. Adapter profile workspace metadata remains, but under attempt scope

The profile metadata that describes attempt workspace layout still matters for prompt rendering and validation. The profile section is renamed from `workspace_provisioner` to `attempt_workspace` and continues to describe:

- `workspace_subdir`
- `skills_subdir`
- `use_config_parent_as_workspace`
- `unknown_fallback`

This data now describes attempt workspace layout, not skill installation policy.

## Execution Flow

### Create-run

1. orchestration resolves the incoming skill source
2. `RunFolderBootstrapper` materializes the run-local snapshot
3. run state initialization continues
4. later attempts consume the snapshot in place

### Per-attempt

1. orchestration resolves the canonical `SkillManifest`
2. `AttemptConfigComposer` generates the current config
3. `AttemptRunFolderValidator` validates the minimal execution contract
4. adapter starts the engine process

### waiting_auth resume

1. auth completes and schedules a non-reply resumed attempt
2. the resumed attempt composes config again
3. the resumed attempt validates the existing run-local snapshot
4. execution proceeds without reinstall/copy/unpack/patch

## Migration

- remove `WorkspaceProvisioner` and `ProfiledWorkspaceProvisioner` from runtime adapter contracts and adapters
- move installed-skill materialization helpers into orchestration bootstrap code
- replace adapter imports, tests, and profile fixtures in one change
- do not keep compatibility aliases for the old canonical names
