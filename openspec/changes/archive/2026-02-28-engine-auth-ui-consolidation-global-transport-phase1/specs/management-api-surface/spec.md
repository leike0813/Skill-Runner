## ADDED Requirements

### Requirement: 管理 UI 鉴权入口 MUST 由全局 transport 统一驱动
系统 MUST 允许管理 UI 先选择全局 transport，再发起引擎鉴权会话；请求契约仍保持 `engine/transport/auth_method/provider_id`。

#### Scenario: 先选 transport 再发起鉴权
- **WHEN** 用户在 `/ui/engines` 将全局鉴权后台切换为 `cli_delegate`
- **AND** 从引擎入口菜单选择某个鉴权方式
- **THEN** UI 请求体中的 `transport` 必须为 `cli_delegate`
- **AND** 不需要在按钮层面硬编码 transport

### Requirement: 管理 UI MUST 对 OpenCode 使用 provider->auth_method 组合
系统 MUST 在 OpenCode 鉴权发起时显式提交 `provider_id` 与 `auth_method` 组合，且二者来源于当前 transport 的能力过滤结果。

#### Scenario: OpenCode 发起鉴权
- **WHEN** 用户在 OpenCode 入口中先选择 provider，再选择 auth_method
- **THEN** UI 请求体包含 `engine=opencode`、`provider_id=<selected>`、`transport=<global>`、`auth_method=<selected>`
