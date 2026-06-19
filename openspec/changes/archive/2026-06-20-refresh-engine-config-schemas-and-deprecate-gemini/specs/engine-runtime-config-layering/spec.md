## MODIFIED Requirements

### Requirement: 运行时配置组装 MUST 采用统一分层优先级

系统 MUST 为活跃引擎 `codex/opencode/qwen/claude` 采用统一配置组装顺序：`engine_default -> skill defaults -> runtime overrides -> enforced`。

#### Scenario: Active engines use refreshed config schemas
- **WHEN** any active engine composes runtime config
- **THEN** validation MUST use that engine's refreshed `settings_schema_path`
- **AND** deprecated Gemini MUST NOT be included in active config composition paths
