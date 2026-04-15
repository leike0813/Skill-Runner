## MODIFIED Requirements

### Requirement: 输出 schema 注入 MUST 动态可选
When output schema guidance is injected, the patching model MUST describe the JSON-only runtime contract rather than a YAML-side-channel interaction protocol.

#### Scenario: output schema guidance includes explicit final marker rule
- **WHEN** a valid output schema is available
- **THEN** the injected guidance MUST describe the final JSON object contract
- **AND** it MUST require `__SKILL_DONE__ = true` for final output

#### Scenario: interactive guidance describes pending branch
- **WHEN** execution_mode=`interactive`
- **THEN** the injected guidance MUST describe the pending branch with `__SKILL_DONE__ = false`
- **AND** it MUST describe required `message` and `ui_hints` fields

### Requirement: 注入 MUST 保持幂等
Patch composition MUST remain modular and idempotent while retiring `<ASK_USER_YAML>` as a normative instruction surface.

#### Scenario: legacy YAML protocol is not reintroduced by patching
- **WHEN** runtime patch content is generated for a compliant implementation
- **THEN** it MUST NOT define `<ASK_USER_YAML>` as the primary interactive output contract
- **AND** any mention of that wrapper MUST be explicitly framed as legacy deprecated semantics
