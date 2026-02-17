## Why

interactive 模式引入 `waiting_user` 与驻留进程后，服务重启会带来状态与进程一致性问题：  
部分 run 可能停留在非终态但已失去可执行上下文，或者遗留孤儿进程继续占用资源。

如果没有统一的重启恢复与对账机制，前端会看到“假活跃”任务，运维也无法判断哪些 run 可继续、哪些必须失败收敛。

## What Changes

1. 新增服务启动后的 run 恢复与对账流程（startup reconciliation）：
   - 扫描非终态 run（`queued/running/waiting_user`）；
   - 按 `interactive_profile.kind` 执行分流恢复。
2. 明确重启后的状态收敛规则：
   - `resumable + waiting_user`：保留 waiting 状态并允许后续 reply 触发 resume；
   - `sticky_process + waiting_user`：进程上下文不可恢复，标记失败（`INTERACTION_PROCESS_LOST`）；
   - `queued/running` 且缺失有效执行上下文：标记失败（`ORCHESTRATOR_RESTART_INTERRUPTED`）。
3. 增加孤儿进程治理：
   - 清理与当前活跃 run 不匹配的遗留 agent 进程；
   - 清理失效 trust/session 绑定，防止资源泄漏。
4. 增加恢复可观测字段：
   - `recovery_state`、`recovered_at`、`recovery_reason`；
   - 便于前端和运维判断重启影响。
5. 补齐重启场景测试与文档，形成可重复验收标准。

## Capabilities

### New Capabilities
- `interactive-run-restart-recovery`: 定义服务重启后对 interactive run 的恢复与状态收敛规则。
- `interactive-orphan-process-reconciliation`: 定义重启后孤儿进程识别、终止与资源清理规则。

### Modified Capabilities
- `interactive-run-lifecycle`: 增加“重启恢复”分支下的状态机行为。
- `interactive-run-observability`: 增加恢复状态与恢复原因的可观测字段。

## Impact

- `server/services/job_orchestrator.py`
- `server/services/run_store.py`
- `server/services/run_cleanup_manager.py`
- `server/services/run_folder_trust_manager.py`
- `server/services/concurrency_manager.py`
- `server/services/run_observability.py`
- `server/routers/jobs.py`
- `server/routers/temp_skill_runs.py`
- `server/models.py`
- `docs/api_reference.md`
- `docs/dev_guide.md`
- `tests/unit/test_job_orchestrator.py`
- `tests/unit/test_run_observability.py`
- `tests/integration/run_integration_tests.py`
