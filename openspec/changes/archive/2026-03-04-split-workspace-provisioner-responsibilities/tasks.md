# Tasks: split-workspace-provisioner-responsibilities

- [x] Draft proposal describing why `workspace provisioner` must be replaced by create-run bootstrap plus per-attempt validation
- [x] Update runtime and orchestration specs to separate run-scope materialization from attempt-scope config/validation
- [x] Extract create-run skill materialization into canonical `RunFolderBootstrapper` code paths
- [x] Replace adapter-side `WorkspaceProvisioner` contract with `AttemptRunFolderValidator`-based per-attempt checks and keep config composition separate
- [x] Migrate adapter profiles and loader schema away from `workspace_provisioner` without compatibility aliases
- [x] Add regression coverage for create-run bootstrap, auth-completed resume validation, and validator hard-fail on corrupted run-local snapshots
