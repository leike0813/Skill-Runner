# interactive-run-restart-recovery Specification

## Purpose
定义 orchestrator 重启后的 interactive run 启动恢复与状态收敛语义，确保非终态 run 不会长期处于“假活跃”状态，并且恢复结果可被外部系统观测。
## Requirements
### Requirement: 系统 MUST 在启动时对非终态 run 执行恢复对账
系统 MUST 在服务启动阶段扫描并收敛 `queued/running/waiting_user` run，避免状态与执行上下文漂移。

#### Scenario: 启动时扫描非终态 run
- **WHEN** 服务完成基础启动并进入恢复阶段
- **THEN** 系统扫描所有非终态 run
- **AND** 对每个 run 记录恢复决策结果

### Requirement: waiting_user 的恢复行为 MUST 按 interactive_profile 分流
系统 MUST 对 `waiting_user` run 按 `resumable|sticky_process` 执行不同恢复策略。

#### Scenario: resumable waiting_user 恢复
- **GIVEN** run 为 `waiting_user` 且 `interactive_profile.kind=resumable`
- **AND** run 持久化了有效 session handle 与 pending interaction
- **WHEN** 服务重启完成
- **THEN** run 保持 `waiting_user`
- **AND** 后续可继续接受 reply 并恢复执行

#### Scenario: sticky_process waiting_user 收敛
- **GIVEN** run 为 `waiting_user` 且 `interactive_profile.kind=sticky_process`
- **WHEN** 服务重启完成
- **THEN** run 进入 `failed`
- **AND** `error.code=INTERACTION_PROCESS_LOST`

### Requirement: 运行中断状态 MUST 收敛为可解释终态
系统 MUST 对无法恢复的 `queued/running` run 进行确定性终态收敛。

#### Scenario: queued/running 中断收敛
- **GIVEN** run 状态为 `queued` 或 `running`
- **WHEN** 服务重启后无法恢复其执行上下文
- **THEN** run 进入 `failed`
- **AND** `error.code=ORCHESTRATOR_RESTART_INTERRUPTED`
