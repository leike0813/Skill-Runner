## ADDED Requirements

### Requirement: 系统 MUST 在活跃态执行可控终止
系统 MUST 对活跃 run（`queued/running/waiting_user`）执行统一的取消生命周期。

#### Scenario: queued 任务取消
- **GIVEN** run 状态为 `queued`
- **WHEN** 客户端调用 cancel
- **THEN** run 最终进入 `canceled`
- **AND** 不会继续进入正常执行阶段

#### Scenario: running 任务取消
- **GIVEN** run 状态为 `running`
- **WHEN** 客户端调用 cancel
- **THEN** 系统向对应 CLI 进程发送终止信号
- **AND** run 最终进入 `canceled`

#### Scenario: waiting_user 任务取消
- **GIVEN** run 状态为 `waiting_user`
- **WHEN** 客户端调用 cancel
- **THEN** 系统终止对应执行链路
- **AND** run 最终进入 `canceled`

### Requirement: 取消路径 MUST 完成收尾资源回收
系统 MUST 在取消完成后执行与终态一致的资源回收动作。

#### Scenario: 取消后的资源回收
- **WHEN** run 进入 `canceled`
- **THEN** 并发槽位被释放
- **AND** run folder trust 被清理
- **AND** run/request 状态存储被更新
