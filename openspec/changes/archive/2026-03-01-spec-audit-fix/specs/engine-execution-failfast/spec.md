# engine-execution-failfast Specification

## Purpose
定义任务执行的硬超时终止和失败分类（AUTH_REQUIRED/TIMEOUT）策略。

## MODIFIED Requirements

### Requirement: 任务执行 MUST 启用硬超时并终止阻塞子进程
系统 MUST 对 Agent 子进程执行施加硬超时，超时后必须终止整个相关进程树并结束任务。

#### Scenario: 进程组超时终止
- **WHEN** 某 run 的引擎进程超过硬超时
- **THEN** 系统必须终止该进程及其子进程
- **AND** run 必须进入 `FAILED` 终态

#### Scenario: 终止后读流收敛
- **WHEN** 系统已触发 timeout 终止
- **THEN** 日志读流任务应在有界时间内收敛
- **AND** 任务状态不应长期停留在 `running`
