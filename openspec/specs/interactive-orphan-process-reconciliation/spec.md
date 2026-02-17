# interactive-orphan-process-reconciliation Specification

## Purpose
定义 orchestrator 启动后的孤儿进程与失效运行时绑定清理语义，确保进程、trust/session 绑定与并发槽位状态完成幂等对账并对外提供恢复可观测性。
## Requirements
### Requirement: 系统 MUST 在启动后清理孤儿进程与失效绑定
系统 MUST 对重启后不再对应活跃 run 的 agent 进程与运行时绑定执行清理。

#### Scenario: 孤儿进程识别与终止
- **WHEN** 启动恢复流程执行对账
- **AND** 检测到进程不再绑定任何活跃 run
- **THEN** 系统终止该孤儿进程
- **AND** 记录清理日志

#### Scenario: stale trust 与运行时绑定清理
- **WHEN** 对账流程执行
- **THEN** 系统清理失效 trust 注入与会话绑定
- **AND** 清理动作支持幂等重复执行

### Requirement: 恢复结果 MUST 对外可观测
系统 MUST 向状态接口暴露恢复结果字段，便于前端与运维识别重启影响。

#### Scenario: 查询恢复结果字段
- **WHEN** 客户端查询 run 状态
- **THEN** 响应包含 `recovery_state`
- **AND** 可选包含 `recovered_at` 与 `recovery_reason`
