## Why

`server/services/orchestration/job_orchestrator.py` 同时承担执行编排、交互恢复、审计落盘、打包、文件系统快照、重启恢复等多重职责，已经形成典型 God Object。该结构使得任何改动都容易引发跨职责回归，且测试高度依赖模块级 patch，维护成本持续上升。

## What Changes

- 将 `JobOrchestrator` 重构为薄协调器，仅保留生命周期编排与组件编排逻辑。
- 新增独立组件承载 bundle、filesystem snapshot、audit、interaction lifecycle、restart recovery 职责。
- 新增内部端口接口 `JobControlPort`，让 runtime observability 依赖稳定接口（`build_run_bundle` + `cancel_run`），同时兼容旧 `_build_run_bundle`。
- 保持 `run_job` / `cancel_run` / `recover_incomplete_runs_on_startup` 的外部行为和产物语义不变。

## Capabilities

### New Capabilities
- `job-orchestrator-modularization`: 将作业编排能力重构为可组合服务，确保行为兼容并降低耦合。

### Modified Capabilities
- _None._

## Impact

- Affected code:
  - `server/services/orchestration/job_orchestrator.py`
  - `server/services/orchestration/`（新增多个组件文件）
  - `server/runtime/observability/run_read_facade.py`
  - `server/services/orchestration/runtime_observability_ports.py`
  - `tests/unit/test_job_orchestrator.py`
  - `tests/unit/test_bundle_manifest.py`
  - `tests/unit/test_fs_diff_ignore_rules.py`
  - `tests/unit/test_runtime_observability_port_injection.py`
- Public API: 无变化。
- Runtime schema / invariants: 无变化。
- Dependency impact: 无新增外部依赖。
