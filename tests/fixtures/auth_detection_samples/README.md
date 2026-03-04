# Auth Detection Samples

This fixture corpus contains backend-oriented authentication failure samples captured on 2026-03-02.

Scope:
- Only samples intended to support non-interactive backend auth detection.
- Excludes user-explicitly-removed runs.
- Does not treat TUI prompts such as "visit URL" or "enter authorization code" as primary backend evidence.

Layout:
- `manifest.json` indexes all included samples.
- Each sample directory contains a trimmed set of audit logs plus `context.json`.
- Config snapshots are only included when they help explain the auth mode in a backend-relevant way.

Redaction:
- Local filesystem paths are rewritten to placeholders such as `$PROJECT_ROOT`, `$AGENT_HOME`, and `$NPM_BIN`.
- Only minimal metadata required for evidence and future detector tests is preserved.

Intended future use:
- Evidence source for `docs/auth_required_detection_evidence_20260302.md`
- Parameterized detector tests
- Regression fixtures for auth-required pattern recognition
