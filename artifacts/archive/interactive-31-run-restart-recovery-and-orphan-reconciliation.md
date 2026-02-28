# interactive-31-run-restart-recovery-and-orphan-reconciliation 实现记录

## 实现范围
- 增加启动期恢复入口与收敛逻辑：
  - `recover_incomplete_runs_on_startup`
  - 非终态扫描：`queued/running/waiting_user`
  - 按 `interactive_profile.kind` 执行恢复矩阵
- 明确重启后状态收敛：
  - `waiting_user + resumable`：保持 `waiting_user` 或失败（`SESSION_RESUME_FAILED`）
  - `waiting_user + sticky_process`：失败收敛（`INTERACTION_PROCESS_LOST`）
  - `queued/running`：失败收敛（`ORCHESTRATOR_RESTART_INTERRUPTED`）
- 补齐孤儿与资源对账：
  - 清理 orphan runtime 绑定
  - 清理 stale trust/session 绑定
  - 复位并发槽位占用状态，确保幂等
- 增加恢复可观测字段并对外暴露：
  - `recovery_state`
  - `recovered_at`
  - `recovery_reason`
- 文档同步：
  - `docs/api_reference.md` 更新恢复字段与状态语义
  - `docs/dev_guide.md` 更新启动对账机制与故障恢复策略

## 关键变更文件
- `server/main.py`
- `server/models.py`
- `server/services/concurrency_manager.py`
- `server/services/job_orchestrator.py`
- `server/services/run_store.py`
- `server/services/run_observability.py`
- `server/routers/jobs.py`
- `server/routers/management.py`
- `server/routers/temp_skill_runs.py`
- `tests/unit/test_job_orchestrator.py`
- `tests/unit/test_run_store.py`
- `tests/unit/test_jobs_interaction_routes.py`
- `tests/unit/test_management_routes.py`
- `tests/integration/test_jobs_interactive_observability.py`
- `docs/api_reference.md`
- `docs/dev_guide.md`

## 回归与验证
- 变更相关单测（阶段内）：
  - `conda run --no-capture-output -n DataProcessing python -m pytest tests/unit/test_job_orchestrator.py tests/unit/test_run_store.py tests/unit/test_jobs_interaction_routes.py tests/unit/test_management_routes.py tests/unit/test_run_observability.py tests/unit/test_temp_skill_runs_router.py -q`
  - 结果：`73 passed`
- 集成测试（复跑）：
  - `conda run --no-capture-output -n DataProcessing python -m pytest tests/integration/test_jobs_interactive_observability.py -q`
  - 结果：`4 passed`
- 类型检查：
  - `conda run --no-capture-output -n DataProcessing python -m mypy server`
  - 结果：`Success: no issues found in 52 source files`
- 全量单元测试门禁：
  - `conda run --no-capture-output -n DataProcessing python -m pytest tests/unit -q`
  - 结果：`337 passed`

## OpenSpec 流程记录
- `openspec validate "interactive-31-run-restart-recovery-and-orphan-reconciliation" --type change --strict`
  - 结果：`valid`
- `openspec archive "interactive-31-run-restart-recovery-and-orphan-reconciliation" -y`
  - 归档目录：`openspec/changes/archive/2026-02-16-interactive-31-run-restart-recovery-and-orphan-reconciliation`
