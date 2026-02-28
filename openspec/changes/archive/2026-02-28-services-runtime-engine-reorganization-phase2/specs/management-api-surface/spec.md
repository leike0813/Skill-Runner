## ADDED Requirements

### Requirement: API compatibility MUST survive phase2 hard cutover
phase2 移除兼容导入层后，`/v1` 对外接口行为 MUST 保持兼容。

#### Scenario: Existing clients after hard cutover
- **WHEN** 现有客户端调用既有 `/v1` 路由
- **THEN** 不出现由内部模块迁移导致的破坏性变化
