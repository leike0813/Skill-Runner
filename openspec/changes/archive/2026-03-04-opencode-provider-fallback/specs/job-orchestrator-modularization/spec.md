## ADDED Requirements

### Requirement: opencode auth orchestration MUST derive canonical provider from request model
`opencode` 的 auth orchestration MUST 从 request-side `engine_options.model` 推导 canonical provider，而不是把 detection provider 当作唯一输入。

#### Scenario: canonical provider overrides detection hint for orchestration
- **GIVEN** engine 是 `opencode`
- **AND** request model 解析出的 provider 与 detection hint 不一致或 detection hint 缺失
- **WHEN** orchestration 创建 pending auth
- **THEN** 系统 MUST 以 request model 解析出的 provider 作为 canonical provider

#### Scenario: unresolved model blocks waiting_auth with explicit diagnostic
- **GIVEN** engine 是 `opencode`
- **AND** high-confidence auth detection 已成立
- **AND** request model 无法解析 provider
- **WHEN** orchestration 尝试创建 pending auth
- **THEN** 系统 MUST NOT 静默跳过 waiting_auth
- **AND** 系统 MUST 记录 provider unresolved 的诊断
