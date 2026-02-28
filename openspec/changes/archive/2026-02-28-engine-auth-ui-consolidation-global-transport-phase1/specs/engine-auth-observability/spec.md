## ADDED Requirements

### Requirement: UI MUST 以统一状态窗口展示会话关键字段
系统 MUST 在管理 UI 中统一展示 `engine/transport/auth_method/status/auth_url/user_code/expires_at/error`，并根据状态决定显隐。

#### Scenario: waiting_user 状态展示
- **WHEN** 会话状态为 `waiting_user`
- **THEN** 若存在 `auth_url` 则显示授权链接
- **AND** 若会话要求输入则显示输入框与提示

### Requirement: 输入提示 MUST 与引擎语义匹配
系统 MUST 根据 `transport + engine + provider_id + auth_method + input_kind` 提示正确输入语义，避免误导操作。

#### Scenario: callback 模式提示
- **WHEN** `auth_method=callback`
- **THEN** UI 提示自动回调优先，异机可粘贴回调 URL 兜底

#### Scenario: auth_code_or_url 模式提示
- **WHEN** `auth_method=auth_code_or_url`
- **THEN** UI 对 `gemini/iflow/opencode-google` 显示针对性提示
- **AND** device-code 场景仅在会话声明输入需求时显示输入框

### Requirement: UI 能力矩阵 MUST 由后端上下文注入
系统 MUST 通过后端注入 `auth_ui_capabilities` 驱动菜单渲染，避免前端硬编码能力矩阵漂移。

#### Scenario: 渲染能力矩阵
- **WHEN** `/ui/engines` 页面渲染
- **THEN** 模板上下文包含 `auth_ui_capabilities`
- **AND** 菜单项完全由该对象与 provider 列表计算
