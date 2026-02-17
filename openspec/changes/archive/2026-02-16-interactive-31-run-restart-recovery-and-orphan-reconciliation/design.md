## Context

interactive 链路存在两类运行档位：
- `resumable`：等待用户时可以结束进程，后续通过会话句柄恢复；
- `sticky_process`：等待用户时依赖驻留进程持续存在。

服务重启后，这两类 run 的可恢复性不同。若不做统一对账：
- 数据层会保留 `running/waiting_user`，但执行上下文可能已经消失；
- 孤儿 agent 进程可能继续运行，造成资源泄漏和状态漂移。

## Goals

1. 定义启动期 run 状态对账与恢复策略。
2. 保证重启后所有非终态 run 在可恢复性上有确定结论。
3. 清理孤儿进程与失效运行时绑定（slot/trust/session）。
4. 向 API 与观测层暴露恢复结果字段。

## Non-Goals

1. 不实现“从中断中的 running 回合继续执行”（无通用引擎能力保证）。
2. 不引入新的执行模式，仅补充重启恢复语义。
3. 不改变已有终态定义（仍使用 `succeeded/failed/canceled`）。

## Prerequisite

- `interactive-05-engine-session-resume-compatibility`
- `interactive-10-orchestrator-waiting-user-and-slot-release`
- `interactive-26-job-termination-api-and-frontend-control`

## Design

### 1) 启动期对账入口

新增启动期恢复流程（示意：`recover_incomplete_runs_on_startup()`）：
1. 扫描 run_store 中非终态 run：`queued/running/waiting_user`。
2. 按 run 的 `execution_mode`、`interactive_profile` 与持久化上下文执行恢复判断。
3. 输出恢复结论并写回状态与观测字段。

### 2) 状态收敛矩阵

1. `waiting_user + resumable`
- 条件：存在有效 `pending_interaction_id` 与 `engine_session_handle`。
- 行为：保持 `waiting_user`，等待客户端 `reply` 后恢复。
- 失败分支：若句柄缺失或损坏，转 `failed`，`error.code=SESSION_RESUME_FAILED`。

2. `waiting_user + sticky_process`
- 行为：重启后原驻留进程不可依赖，直接转 `failed`。
- 错误码：`INTERACTION_PROCESS_LOST`。

3. `queued/running`
- 若无可靠回合恢复点（当前默认）：转 `failed`，`error.code=ORCHESTRATOR_RESTART_INTERRUPTED`。
- 目的：避免“伪 running”长期悬挂。

### 3) 孤儿进程与资源对账

启动期执行 orphan reconciliation：
1. 检测历史记录中的进程绑定信息（如 pid/exec_session_id）。
2. 识别不再对应活跃 run 的进程并终止。
3. 清理 stale trust 目录注入、并发槽位占用计数与临时绑定状态。

要求：
- 终止动作幂等，可重复执行。
- 清理失败需记录告警，不阻断主服务启动。

### 4) 可观测字段

为 run 状态补充恢复信息：
- `recovery_state`: `none|recovered_waiting|failed_reconciled`
- `recovered_at`: ISO 时间
- `recovery_reason`: 简述收敛原因

在状态查询与管理 API 中可见，用于前端提示与运维排障。

### 5) 与取消能力协同

恢复后仍处于 `waiting_user` 的 run，必须继续支持：
- `reply` 恢复执行；
- `cancel` 主动终止（沿用 interactive-26）。

## Risks & Mitigations

1. **风险：误杀活跃进程**
   - 缓解：仅清理“无活跃 run 绑定”或“绑定 run 已终态”的进程，并增加 dry-run 日志验证。
2. **风险：恢复策略过于保守导致失败率升高**
   - 缓解：优先保证状态一致性，后续在引擎支持增强后再扩展 running 续跑能力。
3. **风险：启动恢复耗时影响可用性**
   - 缓解：恢复流程分阶段执行（关键收敛先完成，重清理可异步补偿）。
