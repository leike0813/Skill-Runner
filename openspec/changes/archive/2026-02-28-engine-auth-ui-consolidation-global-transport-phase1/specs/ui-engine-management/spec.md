## ADDED Requirements

### Requirement: Engine 管理页 MUST 使用“单入口 + 分层菜单”鉴权交互
系统 MUST 在引擎表格中为每个引擎仅提供一个鉴权入口按钮，并通过分层菜单选择鉴权方式。

#### Scenario: 非 OpenCode 引擎菜单
- **WHEN** 用户点击 `连接 Codex/Gemini/iFlow`
- **THEN** 页面展示当前全局 transport 下该引擎可用 `auth_method` 列表

#### Scenario: OpenCode 引擎菜单
- **WHEN** 用户点击 `连接 OpenCode`
- **THEN** 页面先展示 provider 列表
- **AND** 选择 provider 后再展示该 provider 的鉴权方式列表

### Requirement: 鉴权状态窗口 MUST 保留状态展示并简化操作按钮
系统 MUST 保留 Engine Auth 状态窗口，但除取消按钮外不再提供启动类按钮。

#### Scenario: 状态窗口按钮集合
- **WHEN** 用户查看 Engine Auth 状态窗口
- **THEN** 窗口仅包含取消按钮
- **AND** 启动鉴权入口只存在于引擎表格

### Requirement: 全局 transport 选择器 MUST 受会话锁控制
系统 MUST 在存在活动 auth 会话或活动 TUI 会话时禁用全局 transport 下拉。

#### Scenario: 鉴权进行中锁定 transport
- **WHEN** 存在活动 auth 会话
- **THEN** transport 下拉禁用
- **AND** 引擎鉴权入口按钮禁用

### Requirement: user_code 复制能力 MUST 在指定场景可用
系统 MUST 在 `codex` 与 `opencode+openai` 的 `auth_code_or_url` 场景显示 user_code 复制按钮。

#### Scenario: 显示复制按钮
- **WHEN** 会话包含 `user_code`
- **AND** `auth_method=auth_code_or_url`
- **AND** `(engine=codex) OR (engine=opencode AND provider_id=openai)`
- **THEN** 页面显示复制按钮并支持复制 user_code
