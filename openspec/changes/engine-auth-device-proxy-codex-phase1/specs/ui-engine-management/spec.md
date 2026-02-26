## ADDED Requirements

### Requirement: Engine 管理页 MUST 提供 Codex device-auth 连接入口
系统 MUST 在 `/ui/engines` 提供 Codex 的 device-auth 鉴权入口，并展示会话状态与 challenge 信息。

#### Scenario: 启动 Codex device-auth 会话
- **WHEN** 用户在 Engine 管理页点击“连接 Codex”
- **THEN** UI 调用会话 start 接口并展示当前会话状态
- **AND** 若会话返回 challenge，页面显示 `auth_url` 与 `user_code`

#### Scenario: 查询并轮询鉴权会话状态
- **WHEN** 页面存在活跃鉴权会话
- **THEN** UI 周期查询 status 接口
- **AND** 页面展示 `starting|waiting_user|succeeded|failed|canceled|expired` 之一

#### Scenario: 用户取消鉴权会话
- **WHEN** 用户点击取消按钮
- **THEN** UI 调用 cancel 接口
- **AND** 页面状态切换为 `canceled`

### Requirement: 鉴权会话与内嵌 TUI MUST 全局互斥
系统 MUST 防止鉴权会话与内嵌 TUI 会话并发进行。

#### Scenario: TUI 活跃时启动鉴权
- **WHEN** 内嵌 TUI 会话处于活跃状态
- **AND** 用户尝试启动 Codex device-auth 会话
- **THEN** 系统返回 `409`
- **AND** UI 展示冲突提示

#### Scenario: 鉴权活跃时启动 TUI
- **WHEN** Codex device-auth 会话处于活跃状态
- **AND** 用户尝试启动内嵌 TUI
- **THEN** 系统返回 `409`
- **AND** UI 展示冲突提示
