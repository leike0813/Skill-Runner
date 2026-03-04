## ADDED Requirements

### Requirement: Runtime auth session snapshots MUST distinguish credential observability from completion
runtime auth session snapshot MUST 将静态凭据观测与 auth session completion 彻底解耦。

#### Scenario: credential presence does not imply completed session
- **WHEN** engine 本地凭据已经存在
- **AND** auth session 仍在 challenge-active
- **THEN** runtime auth snapshot MUST NOT 被视为 completed
- **AND** MUST NOT 触发 `auth.completed`

### Requirement: Runtime auth handlers MUST not expose readiness as completion semantics
adapter/runtime auth handlers MUST NOT 再以 readiness-like 字段表达 session completion。

#### Scenario: terminal success is explicit
- **WHEN** auth session 被标记为 `succeeded` 或 `completed`
- **THEN** 该状态 MUST 来自显式 completion path
- **AND** MUST NOT 来自凭据存在性推断
