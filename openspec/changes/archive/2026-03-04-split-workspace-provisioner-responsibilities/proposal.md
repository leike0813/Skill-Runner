# Proposal: split-workspace-provisioner-responsibilities

## Why

The current runtime still treats `workspace provisioner` as a mixed-responsibility component:

- create-run materializes a skill into the run-local snapshot
- later attempts still enter adapter-side workspace preparation
- the adapter-side helper still owns skill copy/install semantics

That boundary is wrong. The problem is not that resume creates a new attempt; the problem is that an attempt-stage hook still owns run-scope materialization behavior.

This leaks run-folder mutation into non-reply resumed attempts, especially the `waiting_auth -> auth_completed -> resumed attempt` path, and allows a later attempt to delete or overwrite the already-materialized run-local skill snapshot.

## What Changes

This change replaces the mixed `workspace provisioner` concept with three explicit responsibilities:

1. `RunFolderBootstrapper`
   - create-run only
   - materializes installed or temporary skills into the run-local snapshot and patches the snapshot once
2. `AttemptConfigComposer`
   - per-attempt
   - generates or confirms the engine config for the current attempt
3. `AttemptRunFolderValidator`
   - per-attempt
   - validates the run-local snapshot and required config before starting the engine process

The adapter-side per-attempt path will keep config composition and add hard-fail validation, but it will no longer own skill installation, copying, unpacking, or patching.

## Impact

- affects adapter runtime contracts, adapter profile schema, prompt-builder path resolution, and orchestration skill materialization ownership
- keeps external HTTP APIs and runtime event payloads unchanged
- hard-fails resumed attempts when the run folder drifts from the minimal execution contract
- removes the canonical `WorkspaceProvisioner` / `ProfiledWorkspaceProvisioner` concept from runtime code paths
