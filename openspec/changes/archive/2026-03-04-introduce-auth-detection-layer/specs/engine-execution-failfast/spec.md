## MODIFIED Requirements

### Requirement: 系统 MUST 对超时失败进行 AUTH_REQUIRED/TIMEOUT 分类
系统 MUST 基于已捕获输出进行归类，并将 `failure_reason` 作为终态判定的最高优先级。`AUTH_REQUIRED` 的主来源 MUST 为 `auth_detection` 层，而不是仅靠 `_looks_like_auth_required()`。

#### Scenario: 高置信度 auth detection 触发 AUTH_REQUIRED
- **GIVEN** `auth_detection.confidence=high`
- **WHEN** 输出命中稳定 auth-required 规则
- **THEN** `failure_reason` 必须为 `AUTH_REQUIRED`
- **AND** run 必须进入 `failed`

#### Scenario: medium detection 不自动升级 AUTH_REQUIRED
- **GIVEN** `auth_detection.confidence=medium`
- **WHEN** 输出属于问题样本层
- **THEN** run 不得自动升级为 `AUTH_REQUIRED`
- **AND** detection 结果必须保留到审计中
