## Why

`server/services/orchestration/job_orchestrator.py` 当前仍有约 1299 行，`run_job` 主流程聚合了 preflight、执行编排、结果归一化、状态更新、审计落盘、auto-decide 触发与 finally 清理等多重职责。  
尽管上一波已抽出 bundle/snapshot/audit/interaction/recovery 组件，`run_job` 仍是主要复杂度热点，测试和后续演进成本高。

## What Changes

- 新增 `RunJobLifecycleService`，承接 `run_job` 主生命周期逻辑。
- `JobOrchestrator.run_job` 下沉为薄委派入口，只负责构造请求并调用生命周期服务。
- 保留 `JobOrchestrator` 对外入口和现有兼容 helper/wrapper（如 `_build_run_bundle`、`_extract_pending_interaction*` 等）。
- 保持路由层调用方式和 runtime 合同语义不变。

## Capabilities

### Modified Capabilities
- `job-orchestrator-modularization`:
  - 继续推进 God Object 拆分，wave2 聚焦 `run_job` 主流程下沉。
  - 采用 delta spec，仅定义相对上一波的新增约束。

## Impact

- Affected code:
  - `server/services/orchestration/job_orchestrator.py`
  - `server/services/orchestration/run_job_lifecycle_service.py` (new)
- Affected tests/docs:
  - `tests/unit/test_job_orchestrator.py`
  - `docs/core_components.md`
  - `docs/project_structure.md`
- Public API:
  - HTTP API: 无变化
  - Runtime schema/invariants: 无变化
