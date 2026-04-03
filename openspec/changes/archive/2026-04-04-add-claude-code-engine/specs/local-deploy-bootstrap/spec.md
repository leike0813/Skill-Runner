## MODIFIED Requirements

### Requirement: Local bootstrap and diagnostics include Claude

Local bootstrap and diagnostic commands SHALL recognize `claude` as a managed engine.

#### Scenario: Explicit Claude bootstrap

- **WHEN** a caller runs bootstrap or install with `--engines claude`
- **THEN** the managed engine installer MUST ensure Claude
- **AND** `preflight`, `doctor`, and `status` MUST report Claude consistently as installed or missing
