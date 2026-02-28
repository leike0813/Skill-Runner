## ADDED Requirements

### Requirement: Auth runtime observability MUST remain transport-consistent after modularization
auth runtime 模块化后，状态与审计语义 MUST 维持现有 transport 约束。

#### Scenario: oauth_proxy session refresh
- **WHEN** oauth_proxy 会话刷新
- **THEN** 状态机不应出现 `waiting_orchestrator`
- **AND** callback/input 事件仍按既有字段写入会话审计

#### Scenario: cli_delegate session refresh
- **WHEN** cli_delegate 会话刷新
- **THEN** 可进入 `waiting_orchestrator`
- **AND** 终态后必须释放全局交互锁

## MODIFIED Requirements

### Requirement: Session finalization logic is delegated to engine runtime handlers
终态清理（listener 停止、state 清理、provider-specific rollback）MUST 由 engine runtime handler 承担，manager 仅负责统一调度与会话收口。

#### Scenario: session reaches terminal state
- **WHEN** 任一引擎会话进入 terminal
- **THEN** manager 调用 handler finalize hook
- **AND** manager 统一执行 session store 清理、gate release 与 trust cleanup
