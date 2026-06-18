# Design: harden run-owned namespace lifecycle

## Lifecycle Rule

For any request-bound run with layout metadata, the backend resolves a `RunWorkspaceLayout` from the request or run record before touching runner-owned files. The layout supplies:

- `result/<namespace>/result.json`
- `.audit/<namespace>/input_manifest.json`
- `.state/<namespace>/state.json`
- `.state/<namespace>/dispatch.json`
- `.audit/<namespace>/...`

Legacy root files remain read-compatible fallback targets only when layout metadata is missing or a namespaced historical file is absent.

## Write Path Hardening

Request creation and temp-upload dispatch persist `workspace_id`, `workspace_dir`, `workspace_namespace`, `result_path`, and `input_manifest_path` before initializing queued state. Later lifecycle stages must consume those persisted fields instead of recomputing root paths.

Execution preparation injects internal paths into run options:

- `__audit_dir`
- `__input_manifest_path`
- `__result_json_path`

Adapters, live runtime emitters, audit services, service log mirrors, and overflow sidecar recorders use `__audit_dir` for attempt-scoped files. If `__audit_dir` is absent, they may continue using root `.audit` for legacy/no-layout runs.

Interaction and auth routes are request-bound even though they execute outside the main attempt loop. They therefore wrap orchestrator callbacks before passing them into auth orchestration:

- `append_orchestrator_event` injects the layout audit directory.
- `update_status` writes the layout state file, falling back to the legacy orchestrator helper only when no layout exists.

## Read Path Hardening

Status, run list, detail, result, logs, protocol history, chat history, timeline, management diagnostics, and cancel checks resolve layout first. Root `.state`, `.audit`, and `result/result.json` are fallback inputs for historical records, not preferred current truth.

Protocol/chat history has an extra compatibility rule: if a namespaced mirror is empty for a previously split run, readers may include legacy root audit rows so existing in-flight runs remain observable after deployment.

## Bundle and Result Behavior

Terminal finalization writes the terminal payload to actual `resultJsonPath` and updates run-store metadata with that path and a workspace output token. Bundle generation for layout-aware runs writes request-owned zip and manifest files under `bundle/<namespace>/` and collects only the current run's result directory, optional result-local feedback sidecar, and artifacts referenced by that result. Legacy `result/result.json` and root `bundle/run_bundle*.zip` remain readable only when no layout metadata is recorded.

## Regression Strategy

Coverage focuses on stable observable behavior rather than internal implementation order:

- live FCMP/RASP and chat replay mirror files are written under namespaced audit directories;
- run list and result/status facades prefer namespaced state/result;
- adapter overflow sidecars use namespaced audit directories;
- management error extraction prefers namespaced state;
- interaction reply/auth callback paths write namespaced audit/state;
- existing orchestrator, finalizer, preparation, execution, and outcome tests remain green.
