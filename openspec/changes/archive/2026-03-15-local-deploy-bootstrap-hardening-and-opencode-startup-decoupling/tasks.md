## 1. Bootstrap/Ensure Unified Entry

- [x] 1.1 Add `skill-runnerctl bootstrap` and reuse ensure execution path.
- [x] 1.2 Keep ensure-compatible tolerance semantics (`partial_failure` does not block startup).
- [x] 1.3 Update local deploy scripts to invoke bootstrap entry.

## 2. Installer Bootstrap Automation

- [x] 2.1 Run bootstrap automatically after release artifact extraction.
- [x] 2.2 Keep installer completion even when bootstrap command exits non-zero (warning only).

## 3. OpenCode Startup Decoupling

- [x] 3.1 Replace startup `await refresh` with async scheduling.
- [x] 3.2 Keep a unified probe timeout policy based on `ENGINE_MODELS_CATALOG_PROBE_TIMEOUT_SEC`.
- [x] 3.3 Add bootstrap-stage OpenCode warmup (`opencode models`) diagnostics; failures are warning-only.
- [x] 3.4 Preserve stale/seed fallback on probe failures.

## 4. Local Lease First Heartbeat Grace

- [x] 4.1 Add server-side first-heartbeat grace window (default 15s).
- [x] 4.2 Ensure first heartbeat returns to normal TTL semantics.

## 5. UV Runtime Profile Governance

- [x] 5.1 Inject runtime profile env in `skill-runnerctl` wrappers before `uv run`.
- [x] 5.2 Ensure deployment chain uses these injected variables to avoid unpack-dir `.venv`.

## 6. Tests and Validation

- [x] 6.1 Add/update unit tests for bootstrap command behavior.
- [x] 6.2 Update startup test to assert async model refresh scheduling.
- [x] 6.3 Remove cold-start timeout branch tests and keep unified-timeout assertions.
- [x] 6.4 Add unit tests for first-heartbeat grace semantics.
- [x] 6.5 Add UI gating tests for ttyd unavailable (`Start TUI` hidden + start endpoint `503`).
- [x] 6.6 Run targeted pytest + mypy + `openspec validate` (mypy currently reports pre-existing Windows attr-defined issues in trust folder strategies).

## 7. README + UI Home Indicator Alignment

- [x] 7.1 Update `README*.md` docker run snippets to `latest` and compose-equivalent volumes.
- [x] 7.2 Add release compose download/deploy instructions in all README languages.
- [x] 7.3 Rename local section titles to deployment wording and document local dependencies (`uv`, `node/npm`, optional `ttyd`).
- [x] 7.4 Add ttyd dependency hints wherever inline/embedded TUI is described.
- [x] 7.5 Add home-page engine status indicator (cache snapshot based, static render).
- [x] 7.6 Add/update UI unit tests for home indicator rendering and status color mapping.
