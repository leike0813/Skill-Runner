## ADDED Requirements

### Requirement: Engine 管理页 MUST 在高风险鉴权选项上显示醒目风险标记
系统 MUST 在 `/ui/engines` 的鉴权方式菜单中，为高风险方法显示简短风险标记，且该标记来源于策略文件。

#### Scenario: OpenCode Google in oauth_proxy
- **GIVEN** 用户在管理页选择 `transport=oauth_proxy`
- **AND** 选择 OpenCode provider `google`
- **WHEN** 页面渲染鉴权方式菜单
- **THEN** `callback` / `auth_code_or_url` 选项 MUST 显示 `(High risk!)` 标记

#### Scenario: OpenCode Google in cli_delegate
- **GIVEN** 用户在管理页选择 `transport=cli_delegate`
- **AND** 选择 OpenCode provider `google`
- **WHEN** 页面渲染鉴权方式菜单
- **THEN** `auth_code_or_url` 选项 MUST 显示 `(High risk!)` 标记

### Requirement: 管理页鉴权方法菜单 MUST 仅使用策略能力矩阵
系统 MUST 从后端策略能力矩阵渲染 OpenCode 方法菜单，禁止前端本地 fallback 硬编码。

#### Scenario: provider transport method resolution
- **WHEN** 页面根据 provider + transport 渲染方法菜单
- **THEN** 方法列表 MUST 仅来自后端注入的 capability payload
- **AND** 当 capability 为空时 MUST 显示“无可用方式”错误，不进行本地推断
