# ui-auth-hardening Specification

## Purpose
TBD - created by archiving change ui-skill-browser-and-auth-hardening. Update Purpose after archive.
## Requirements
### Requirement: UI 鉴权状态 MUST 可观测
系统 MUST 在启动时输出 UI 鉴权是否启用及受保护路由范围。

#### Scenario: 启动日志可见
- **WHEN** 服务启动完成
- **THEN** 日志包含 `UI basic auth enabled` 状态
- **AND** 日志包含受保护路径范围说明

### Requirement: 鉴权开启后受保护路由 MUST 返回 401（未认证）
当 `UI_BASIC_AUTH_ENABLED=true` 时，系统 MUST 拒绝未携带正确凭据的受保护路由访问。

#### Scenario: 未认证访问 UI
- **WHEN** 未认证访问 `/ui` 或 `/ui/skills/{skill_id}`
- **THEN** 返回 `401`

#### Scenario: 未认证访问安装接口
- **WHEN** 未认证访问 `/v1/skill-packages/install`
- **THEN** 返回 `401`

### Requirement: 鉴权开启且凭据正确时 MUST 返回 200
当 `UI_BASIC_AUTH_ENABLED=true` 且凭据正确时，系统 MUST 允许访问受保护路由并返回成功状态。

#### Scenario: 认证后访问 UI
- **WHEN** 携带正确 Basic Auth 访问 `/ui`
- **THEN** 返回 `200`

