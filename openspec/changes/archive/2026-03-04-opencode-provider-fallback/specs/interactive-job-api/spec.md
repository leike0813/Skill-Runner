## ADDED Requirements

### Requirement: opencode high-confidence auth detection MUST enter waiting_auth when request model yields a supported provider
当 `opencode` interactive run 命中高置信度 `auth_required` 时，只要 request-side `engine_options.model` 可以解析出受支持 provider，系统 MUST 进入 `waiting_auth`。

#### Scenario: detection provider missing but request model resolves provider
- **GIVEN** engine 是 `opencode`
- **AND** `auth_detection.provider_id` 为空
- **AND** `engine_options.model` 为 `deepseek/deepseek-reasoner`
- **WHEN** 运行命中高置信度 `auth_required`
- **THEN** run MUST 进入 `waiting_auth`
- **AND** pending auth 的 `provider_id` MUST 为 `deepseek`

#### Scenario: unresolved request model remains diagnosable failure
- **GIVEN** engine 是 `opencode`
- **AND** request-side model 缺失或格式非法
- **WHEN** 运行命中高置信度 `auth_required`
- **THEN** run MAY 失败为 `AUTH_REQUIRED`
- **AND** 系统 MUST 写出 provider unresolved 的明确诊断
