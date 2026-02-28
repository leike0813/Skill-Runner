## MODIFIED Requirements

### Requirement: UI auth behavior MUST remain compatible during auth runtime modularization
在 auth runtime 内部拆分期间，管理 UI 的鉴权行为 MUST 与当前能力矩阵保持一致。

#### Scenario: UI 发起鉴权不受内部重构影响
- **WHEN** 用户在 `/ui/engines` 发起任意现有鉴权组合
- **THEN** UI 可得到与重构前一致的状态推进与错误语义

#### Scenario: 取消后可继续发起新鉴权
- **WHEN** 用户取消进行中的会话
- **THEN** 全局锁应被释放
- **AND** UI 后续可正常启动新的鉴权会话
