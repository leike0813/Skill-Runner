## MODIFIED Requirements

### Requirement: Public auth API contract remains compatible through internal verticalization
系统在 phase2 重构后 MUST 保持 `/v1/engines/auth/*` 路径与核心请求字段语义兼容。

#### Scenario: Start/query/input/cancel sessions
- **WHEN** 客户端调用 oauth_proxy 或 cli_delegate 相关端点
- **THEN** `engine/transport/auth_method/provider_id` 语义保持不变
- **AND** 内部实现可切换到新的 runtime/auth + engine driver 结构

### Requirement: Legacy sessions compatibility endpoint remains functional
兼容层 `/v1/engines/auth/sessions*` MUST 继续可用，用于过渡期间的旧调用。

#### Scenario: Client uses legacy sessions endpoint
- **WHEN** 客户端请求旧 sessions 接口
- **THEN** 请求仍可被正确路由并返回兼容快照
- **AND** 不要求客户端升级请求路径
