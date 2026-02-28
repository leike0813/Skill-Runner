## ADDED Requirements

### Requirement: 鉴权公开 API MUST 保持兼容
系统 MUST 在本次内部重构中保持现有 `/v1/engines/auth/*` 公开 API 路径与主要请求/响应语义兼容。

#### Scenario: 兼容 oauth_proxy 与 cli_delegate 接口
- **WHEN** 客户端调用 `/v1/engines/auth/oauth-proxy/sessions*` 或 `/v1/engines/auth/cli-delegate/sessions*`
- **THEN** 接口路径与主要字段语义保持不变

#### Scenario: 兼容旧 sessions 接口
- **WHEN** 客户端调用 `/v1/engines/auth/sessions*` 兼容层
- **THEN** 兼容行为保持可用
- **AND** 内部可转发到重构后的 façade/orchestrator
