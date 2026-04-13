## MODIFIED Requirements

### Requirement: 输出 schema 注入 MUST 动态可选
When output schema guidance is injected, the target contract MUST describe JSON-only output and a materialized machine schema source.

#### Scenario: injected guidance references materialized schema artifact
- **WHEN** a valid target output schema exists
- **THEN** the injected guidance MUST be a prompt-facing projection of a materialized machine schema artifact
- **AND** it MUST NOT describe itself as a separate protocol

#### Scenario: interactive guidance describes final and pending target branches
- **WHEN** execution mode is `interactive`
- **THEN** target guidance MUST describe the union contract semantics
- **AND** it MUST distinguish final `__SKILL_DONE__ = true` from pending `__SKILL_DONE__ = false`

### Requirement: 注入 MUST 保持幂等
Patch composition remains modular and idempotent while YAML-side-channel wording is retired from the target contract.

#### Scenario: legacy YAML wording is deprecated
- **WHEN** legacy `<ASK_USER_YAML>` wording appears in historical notes
- **THEN** it MUST be labeled deprecated/current-implementation-only
- **AND** it MUST NOT be presented as the target injection contract
