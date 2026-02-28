## MODIFIED Requirements

### Requirement: Public Management API Compatibility
adapter 内部重构 MUST NOT 改变管理 API 对外契约。

#### Scenario: Existing auth and execution endpoints
- **GIVEN** 客户端继续调用既有 `/v1` 端点
- **WHEN** 服务升级到本 change
- **THEN** 请求与响应语义保持兼容，不要求客户端升级字段
