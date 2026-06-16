# Tasks

- [x] Create OpenSpec proposal/design/spec/tasks artifacts.
- [x] Audit run lifecycle from request creation through workspace allocation, queued initialization, attempt execution, terminal projection, observability reads, bundle/result/log reads, cancel, reply, and auth routes.
- [x] Route execution-time live FCMP/RASP mirror writes through the run-owned audit directory.
- [x] Route chat replay mirror writes and bootstrap reads through the run-owned audit directory with legacy fallback.
- [x] Route adapter stdout/stderr/io_chunks and overflow sidecars through injected `__audit_dir`.
- [x] Ensure request-bound running/canceled/terminal projections write namespaced state/result instead of legacy root state/result.
- [x] Ensure queued initialization refetches bound request layout before writing state/dispatch files.
- [x] Ensure target output schema contracts and Codex compat schema artifacts are written under the run-owned audit namespace.
- [x] Ensure bundle zip files, bundle manifests, and bundle collection are run-owned namespace aware.
- [x] Ensure run list, detail, result, logs, cancel, management error, protocol history, chat history, and file-state reads prefer namespaced state/audit/result.
- [x] Route interaction reply accepted events through the request layout audit directory.
- [x] Route auth interaction callbacks through layout-aware audit and state wrappers.
- [x] Add or update regression tests for namespaced live publish, chat replay, observability, read facade, adapter overflow, management error, interaction reply, and auth callback paths.
- [x] Run targeted lifecycle/observability/orchestration pytest validation.
- [x] Run `openspec validate harden-run-owned-namespace-lifecycle --strict`.
