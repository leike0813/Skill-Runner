## MODIFIED Requirements

### Requirement: 系统 MUST 对超时失败进行 AUTH_REQUIRED/TIMEOUT 分类
系统 MUST 基于已捕获输出进行归类，并将 `failure_reason` 作为终态判定的最高优先级；但会话型 run 中的高置信度 `auth_detection` 若可构造 auth session，MUST 优先进入 `waiting_auth` 而不是立即写 `AUTH_REQUIRED`。

#### Scenario: 会话型高置信度鉴权命中进入 waiting_auth
- **GIVEN** `auth_detection.confidence=high`
- **AND** run 属于会话型客户端场景
- **AND** 系统可构造 auth session
- **WHEN** 输出命中稳定 auth-required 规则
- **THEN** run 必须进入 `waiting_auth`
- **AND** 不得立即写 `failure_reason=AUTH_REQUIRED`

#### Scenario: headless 高置信度鉴权命中维持 AUTH_REQUIRED
- **GIVEN** `auth_detection.confidence=high`
- **AND** run 不属于会话型客户端场景
- **WHEN** 输出命中稳定 auth-required 规则
- **THEN** `failure_reason` 必须为 `AUTH_REQUIRED`
- **AND** run 必须进入 `failed`

#### Scenario: medium detection 不自动进入 waiting_auth
- **GIVEN** `auth_detection.confidence=medium`
- **WHEN** 输出属于问题样本层
- **THEN** run 不得自动进入 `waiting_auth`
- **AND** detection 结果必须保留到审计中
