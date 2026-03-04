## ADDED Requirements

### Requirement: Auth orchestrator events MUST use a unified payload contract
系统 MUST 通过统一的 payload contract 写入 auth orchestrator events，避免不同调用点手工拼装出不一致的字段集合。

#### Scenario: auth lifecycle writes stay schema-aligned
- **WHEN** orchestration 写入 auth lifecycle 相关 orchestrator events
- **THEN** 这些 payload MUST 与 `runtime_contract.schema.json` 中声明的字段集合一致
- **AND** `run_audit_service` MUST 继续执行严格校验而不是做隐式兼容修补

#### Scenario: callback accept path does not drift from auth contract
- **WHEN** `run_auth_orchestration_service` 处理 callback/code 提交
- **THEN** 其写出的 `auth.input.accepted` MUST 复用统一 contract
- **AND** 系统 MUST NOT 在不同 auth provider 或提交路径上产生字段命名漂移
