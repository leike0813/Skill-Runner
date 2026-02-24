## MODIFIED Requirements

### Requirement: waiting_user 的恢复行为 MUST 按 interactive_profile 分流
系统 MUST 改为基于 `pending + session handle` 有效性分流，不再区分 sticky 路径。

#### Scenario: 有效上下文保留 waiting
- **GIVEN** run 为 `waiting_user`
- **AND** pending 与 session handle 有效
- **WHEN** 服务重启恢复
- **THEN** run 保持 `waiting_user`

#### Scenario: 无效上下文失败收敛
- **GIVEN** run 为 `waiting_user`
- **AND** pending 或 session handle 缺失/无效
- **WHEN** 服务重启恢复
- **THEN** run 进入 `failed`
- **AND** `error.code=SESSION_RESUME_FAILED`
