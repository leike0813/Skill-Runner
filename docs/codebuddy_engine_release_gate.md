# CodeBuddy Engine Release Gate

CodeBuddy uses the canonical providers `codebuddy-cn` and `codebuddy-global`. A provider controls the credential, network environment, persistent CLI state, and resume lineage. Models are provider-qualified entries in the engine-local pinned manifest and do not depend on login or runtime probing.

Runs use a generated `CODEBUDDY.md`, system-owned settings, and a strict run-local MCP configuration. The runtime rejects caller overrides for CodeBuddy credential and routing environment variables. Callers retain cache control: replacing an account does not automatically invalidate a matching cached result, so use `no_cache=true` when account identity matters.

Credentials are stored in the service-local vault and management responses expose only `missing`, `present`, or `expired` status projections. Missing, expired, and runtime 401 failures reuse canonical waiting-auth and automatically requeue after successful browser authentication. The inline TUI requires an explicit present provider and uses session-local enforced Plan/deny-all settings plus an empty strict MCP source.

## Archived release record

Automated contract, parser, management, golden, and secret-scan validation passed on 2026-07-11. The operator also confirmed successful manual validation for both `codebuddy-cn` and `codebuddy-global`, covering:

- domestic and international login;
- static manifest visibility, provider/model filtering, and first execution;
- exact session resume, automatic authentication recovery, and single-resume behavior;
- provider-qualified inline TUI startup with managed credentials and strict MCP isolation;
- raw token scan of auth and run evidence.

The canonical machine-readable record is `artifacts/archive/codebuddy_release_gate.json`. It is an immutable historical attestation: the external provider checks and operator evidence cannot be regenerated from the current repository alone, and the archived `passed` values do not describe the current environment. Use `scripts/verify_codebuddy_release_record.sh` when an explicit audit of that record is required.

The archived record intentionally leaves `cli_version` null because no verified version value was supplied with the operator attestation; no version is inferred from the pinned model snapshot.
