## ADDED Requirements

### Requirement: Engine 管理页 MUST 支持 OpenCode provider 鉴权
系统 MUST 在 `/ui/engines` 提供 OpenCode provider 选择，并通过统一 input 交互完成鉴权。

#### Scenario: 启动 OpenCode provider 会话
- **WHEN** 用户选择 OpenCode provider 并点击连接
- **THEN** UI 调用 start 接口并携带 `provider_id`
- **AND** 页面展示会话状态与可用输入区

#### Scenario: OAuth 会话等待用户输入
- **WHEN** OpenCode OAuth 会话进入 `waiting_user`
- **THEN** UI 展示授权链接与输入框
- **AND** 提交动作调用 `/ui/engines/auth/sessions/{session_id}/input`

#### Scenario: API key 会话等待用户输入
- **WHEN** OpenCode API key 会话进入 `waiting_user`
- **THEN** UI 展示 API key 输入框
- **AND** 提交时以 `kind=api_key` 发送

#### Scenario: 提交后隐藏输入与链接
- **WHEN** 用户提交输入并收到 accepted
- **THEN** 输入区与链接立即隐藏

### Requirement: OpenCode Google OAuth 前 MUST 执行账号清理
系统 MUST 在 OpenCode Google AntiGravity OAuth 前执行账号清理以降低多账号切换风险。

#### Scenario: 清理成功后进入 OAuth 编排
- **WHEN** provider 为 `google`
- **AND** 清理动作成功
- **THEN** 会话继续进入 OAuth 菜单编排

#### Scenario: 清理失败
- **WHEN** provider 为 `google`
- **AND** 清理动作失败
- **THEN** 会话直接进入 `failed` 并展示错误
