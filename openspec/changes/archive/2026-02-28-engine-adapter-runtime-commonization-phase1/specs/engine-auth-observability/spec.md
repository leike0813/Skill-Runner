## MODIFIED Requirements

### Requirement: Adapter Refactor Must Not Alter Auth Observability Semantics
本 change 仅限 adapter 内核重构，MUST NOT 改变 auth 会话状态机与观测语义。

#### Scenario: Auth session observability
- **GIVEN** 任一 auth transport 会话
- **WHEN** adapter 重构完成后观察会话状态
- **THEN** 状态定义、终态与审计字段语义保持一致
