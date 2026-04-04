## MODIFIED Requirements

### Requirement: provider-aware auth orchestration MUST prefer explicit provider_id

provider-aware engine 的 auth orchestration MUST 优先使用 request-side `provider_id` 作为 canonical provider；`opencode` 的 `provider/model` 仅作为 legacy fallback。

#### Scenario: explicit provider_id overrides detection hint

- **GIVEN** engine 是 provider-aware engine
- **AND** request-side `engine_options.provider_id` 存在
- **WHEN** orchestration 创建 pending auth
- **THEN** 系统 MUST 以显式 `provider_id` 作为 canonical provider

#### Scenario: opencode legacy model syntax remains fallback only

- **GIVEN** engine 是 `opencode`
- **AND** request-side `provider_id` 缺失
- **AND** `model` 可解析为 `provider/model`
- **WHEN** orchestration 创建 pending auth
- **THEN** 系统 MAY 使用该 provider 作为 legacy fallback

#### Scenario: unresolved provider records explicit diagnostic

- **GIVEN** engine 是 provider-aware engine
- **AND** 高置信度 auth detection 已成立
- **AND** 未能解析 canonical provider
- **WHEN** orchestration 处理该回合
- **THEN** 系统 MUST 记录显式 provider unresolved 诊断
- **AND** MUST NOT 创建 provider 为空的 pending auth
