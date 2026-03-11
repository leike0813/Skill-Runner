## ADDED Requirements

### Requirement: engine skill config resolution MUST be declarative-first with fixed fallback
Engine adapters MUST resolve skill-specific config assets from `runner.json.engine_configs` first, then fall back to the engine's canonical fixed filename.

#### Scenario: declared engine config missing and fallback exists
- **GIVEN** `runner.json.engine_configs.opencode` points to an invalid or missing file
- **AND** `assets/opencode_config.json` exists
- **THEN** runtime MUST use the fallback file
- **AND** runtime MUST log the fallback decision without surfacing a user-facing warning

#### Scenario: declared engine config missing and fallback absent
- **GIVEN** `runner.json.engine_configs.codex` cannot be resolved
- **AND** `assets/codex_config.toml` does not exist
- **THEN** runtime MUST continue without skill-specific engine defaults
