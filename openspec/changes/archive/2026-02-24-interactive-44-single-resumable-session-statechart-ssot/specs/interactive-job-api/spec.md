## MODIFIED Requirements

### Requirement: 系统 MUST 提供交互回复接口
reply 成功后 MUST 统一回到 `queued`，不再存在 sticky 专属 `running` 直连。

#### Scenario: reply 后统一 queued
- **WHEN** 客户端提交合法 reply
- **THEN** 接口返回 `status=queued`

## ADDED Requirements

### Requirement: 对外响应 MUST 移除 interactive_profile.kind
系统 MUST 不再对外返回 `interactive_profile.kind`。

#### Scenario: 状态/结果读取不含 kind
- **WHEN** 客户端读取状态或结果
- **THEN** 响应不包含 `interactive_profile.kind`
- **AND** `pending_interaction` 与 history 契约保持不变
