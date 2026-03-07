## 1. OpenSpec Artifacts

- [x] 1.1 Finalize proposal/design/tasks for container bootstrap observability.
- [x] 1.2 Add delta specs for `local-deploy-bootstrap` and `logging-persistence-controls`.

## 2. Agent Ensure Logging

- [x] 2.1 Extend `agent_manager.py --ensure` to emit per-engine structured result fields (`engine`, `exit_code`, `duration_ms`, stderr summary).
- [x] 2.2 Preserve current behavior (do not fail container startup) while adding actionable diagnostics.
- [x] 2.3 Add masked/trimmed stderr policy to avoid secret leakage and log flooding.

## 3. Entrypoint Bootstrap Trace

- [x] 3.1 Add startup phase event logs (`bootstrap.start`, `agent.ensure.start`, `bootstrap.done`, etc.).
- [x] 3.2 Add file persistence for startup logs under `${SKILL_RUNNER_DATA_DIR}/logs/bootstrap.log` with rotation.
- [x] 3.3 Write `${SKILL_RUNNER_DATA_DIR}/agent_bootstrap_report.json` containing ensure/install outcomes.

## 4. Catalog Probe Diagnostics

- [x] 4.1 Enhance opencode model catalog failure logs to include bootstrap correlation hints when CLI is missing.
- [x] 4.2 Ensure warnings remain non-fatal for API startup.

## 5. Docs and Validation

- [x] 5.1 Update `docs/containerization.md` with startup log/report locations and troubleshooting flow.
- [x] 5.2 Add/adjust tests for ensure logging payload and bootstrap report generation.
- [x] 5.3 Validate OpenSpec change and run targeted tests.
