# interactive-run-restart-recovery Specification

## Purpose
定义 orchestrator 重启后的 interactive 运行恢复语义，确保状态收敛可解释、可追踪。

## Requirements
### Requirement: 系统 MUST 在启动时收敛所有非终态 run
系统 MUST 在服务启动阶段扫描并收敛 `queued/running/waiting_user` run。

#### Scenario: 启动恢复扫描
- **WHEN** 服务进入恢复阶段
- **THEN** 系统扫描全部非终态 run
- **AND** 为每个 run 写入恢复决策结果

### Requirement: waiting_user 恢复 MUST 基于 pending 与 handle 有效性
系统 MUST 对 `waiting_user` run 执行统一有效性校验。

#### Scenario: waiting_user 恢复保留
- **GIVEN** run 为 `waiting_user`
- **AND** run 持久化了有效 pending interaction 与 session handle
- **WHEN** 服务重启完成
- **THEN** run 保持 `waiting_user`
- **AND** `recovery_state=recovered_waiting`

#### Scenario: waiting_user 恢复失败收敛
- **GIVEN** run 为 `waiting_user`
- **AND** pending interaction 或 session handle 缺失/无效
- **WHEN** 服务重启完成
- **THEN** run 进入 `failed`
- **AND** `error.code=SESSION_RESUME_FAILED`
- **AND** `recovery_state=failed_reconciled`

### Requirement: queued/running 中断 MUST 收敛为确定性失败
系统 MUST 对无法恢复上下文的 `queued/running` run 标记确定性失败。

#### Scenario: queued/running 中断收敛
- **GIVEN** run 状态为 `queued` 或 `running`
- **WHEN** 服务重启后无法恢复其执行上下文
- **THEN** run 进入 `failed`
- **AND** `error.code=ORCHESTRATOR_RESTART_INTERRUPTED`
