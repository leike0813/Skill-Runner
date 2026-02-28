# interactive-10-orchestrator-waiting-user-and-slot-release 实现记录

## 变更范围
- Orchestrator 生命周期强化：
  - `waiting_user` 分支下按 `interactive_profile.kind` 执行不同槽位策略。
  - `resumable`：`waiting_user` 前释放 slot；reply 续跑前重新申请 slot。
  - `sticky_process`：`waiting_user` 期间保持 slot；reply 续跑复用已持有 slot（`__sticky_slot_held`）。
- sticky 超时回收：
  - 新增 sticky watchdog，在 `wait_deadline_at` 超时后将 run 置 `failed`，错误码 `INTERACTION_WAIT_TIMEOUT`，并释放 slot。
- 交互状态与历史持久化增强：
  - 新增 `request_interaction_history` 表。
  - 新增 history append/list 与 answered reply consume。
  - `run_dir/interactions/` 写入 `pending.json`、`history.jsonl`、`runtime_state.json` 镜像文件。
- API reply 路由增强：
  - sticky 路径 reply 进入 `running`，并调度续跑（不走排队占位）。
  - sticky 超时/进程丢失即时映射失败（含错误码）并回收槽位。

## 测试与校验
- 定向单测：
  - `42 passed`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m pytest -q tests/unit/test_run_store.py tests/unit/test_jobs_interaction_routes.py tests/unit/test_job_orchestrator.py tests/unit/test_workspace_manager.py`
- 全量单元测试：
  - `267 passed`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m pytest tests/unit`
- 类型检查：
  - `Success: no issues found in 50 source files`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m mypy server`
- OpenSpec：
  - `openspec validate "interactive-10-orchestrator-waiting-user-and-slot-release" --type change --strict --no-interactive`
  - `openspec archive "interactive-10-orchestrator-waiting-user-and-slot-release" -y`
  - 归档目录：`openspec/changes/archive/2026-02-16-interactive-10-orchestrator-waiting-user-and-slot-release`

