## 1. OpenSpec Artifacts

- [x] 1.1 创建 `proposal.md`，明确问题、目标、非目标与影响范围
- [x] 1.2 创建 `specs/job-orchestrator-modularization/spec.md`，定义兼容性要求与场景
- [x] 1.3 创建 `design.md`，固化拆分决策、风险与迁移计划

## 2. Orchestration Service Extraction

- [x] 2.1 新增 `run_bundle_service.py` 并迁移 bundle/hash/candidate 逻辑
- [x] 2.2 新增 `run_filesystem_snapshot_service.py` 并迁移 snapshot/diff 逻辑
- [x] 2.3 新增 `run_audit_service.py` 并迁移 orchestrator event 与 attempt audit 逻辑
- [x] 2.4 新增 `run_interaction_lifecycle_service.py` 并迁移 pending interaction/resume/auto-decide 逻辑
- [x] 2.5 新增 `run_recovery_service.py` 并迁移 startup recovery 逻辑
- [x] 2.6 新增 `orchestrator_ports.py` 定义 `JobControlPort` 与相关接口

## 3. JobOrchestrator Refactor

- [x] 3.1 引入 `OrchestratorDeps` 并在 `JobOrchestrator` 中装配组件服务
- [x] 3.2 将 `run_job` 重构为协调流程，调用组件服务完成职责
- [x] 3.3 保留 `_build_run_bundle` 兼容包装，新增稳定接口 `build_run_bundle`
- [x] 3.4 保持 `cancel_run` 与 `recover_incomplete_runs_on_startup` 外部行为不变

## 4. Integration Updates

- [x] 4.1 更新 `run_read_facade.py`：优先调用 `build_run_bundle`，回退 `_build_run_bundle`
- [x] 4.2 更新 `runtime_observability_ports.py`：注入类型对齐 `JobControlPort`
- [x] 4.3 更新文档 `docs/core_components.md` 与 `docs/project_structure.md`

## 5. Tests and Verification

- [x] 5.1 校验 `tests/unit/test_job_orchestrator.py` 在依赖注入与组件拆分后无需改动且全部通过
- [x] 5.2 更新 `tests/unit/test_bundle_manifest.py` 覆盖新旧 bundle 接口兼容
- [x] 5.3 更新 `tests/unit/test_runtime_observability_port_injection.py` 并校验 `tests/unit/test_fs_diff_ignore_rules.py` 无需改动且通过
- [x] 5.4 运行测试：
  - `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_job_orchestrator.py tests/unit/test_bundle_manifest.py tests/unit/test_fs_diff_ignore_rules.py tests/unit/test_runtime_observability_port_injection.py`
