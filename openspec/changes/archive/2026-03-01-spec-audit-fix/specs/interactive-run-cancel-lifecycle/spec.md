# interactive-run-cancel-lifecycle Specification

## Purpose
定义活跃 run（`queued/running/waiting_user`）的可控终止生命周期，包括进程信号升级策略和终态资源回收。

## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: 进程终止 MUST 采用信号升级策略
系统 MUST 对活跃子进程执行 SIGTERM → 等待宽限期 → SIGKILL 的分级终止策略。

#### Scenario: 正常 SIGTERM 终止
- **GIVEN** run 状态为 `running` 且子进程存活
- **WHEN** 客户端调用 cancel
- **THEN** 系统先发送 SIGTERM
- **AND** 等待配置的宽限期（grace period）

#### Scenario: SIGKILL 升级
- **GIVEN** 系统已发送 SIGTERM
- **WHEN** 宽限期到达后子进程仍未退出
- **THEN** 系统发送 SIGKILL 强制终止

### Requirement: 取消 MUST 清理 session handle
系统 MUST 在取消流程中清理关联的 session handle，避免资源泄漏。

#### Scenario: waiting_user 取消清理 session
- **GIVEN** run 状态为 `waiting_user` 且持有 session handle
- **WHEN** 客户端调用 cancel
- **THEN** 系统释放 session handle
- **AND** 不再接受后续 interaction reply
