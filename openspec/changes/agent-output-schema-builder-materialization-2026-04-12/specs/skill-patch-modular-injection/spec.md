## MODIFIED Requirements

### Requirement: 输出 schema 注入 MUST 来自 run-scoped materialization
Runtime patching MUST consume the run-scoped materialized schema summary instead of deriving patch text directly from raw `output.schema.json`.

#### Scenario: auto patch uses materialized markdown
- **WHEN** execution mode is `auto`
- **AND** a run-scoped schema summary artifact exists
- **THEN** the injected output schema section MUST come from the materialized markdown projection

#### Scenario: interactive patch keeps legacy ask-user compatibility in this phase
- **WHEN** execution mode is `interactive`
- **AND** a run-scoped schema summary artifact exists
- **THEN** the injected output schema section MUST come from the materialized markdown projection
- **AND** the interactive mode patch MUST still preserve current ask-user compatibility instructions for pending turns
- **AND** it MUST NOT yet require the pending JSON branch as the live prompt protocol

### Requirement: 注入 MUST 保持模块化与幂等
Patch composition MUST remain modular and idempotent after switching output schema injection to precomputed materialized markdown.

#### Scenario: repeated patching does not duplicate materialized schema section
- **WHEN** the same skill snapshot is patched multiple times
- **THEN** the materialized schema section MUST NOT be duplicated
