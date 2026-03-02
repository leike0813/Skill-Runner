## 1. OpenSpec Artifacts

- [x] 1.1 创建 `proposal.md` 并明确 wave2 目标与边界
- [x] 1.2 创建 `specs/job-orchestrator-modularization/spec.md`（Delta Spec, MODIFIED Requirements）
- [x] 1.3 创建 `design.md` 并固化迁移决策与风险控制

## 2. Run Lifecycle Extraction

- [x] 2.1 新增 `server/services/orchestration/run_job_lifecycle_service.py`
- [x] 2.2 定义 `RunJobRequest`、`RunJobRuntimeState`、`RunJobOutcome` dataclass
- [x] 2.3 将 `run_job` 主流程（preflight/execute/normalize/finalize）迁移到新服务

## 3. JobOrchestrator Slimming

- [x] 3.1 `OrchestratorDeps` 新增 `run_job_lifecycle_service` 可注入依赖
- [x] 3.2 `JobOrchestrator.run_job` 改为薄委派入口（构造 request + 调用 service）
- [x] 3.3 保留并验证兼容 helper/wrapper（`_build_run_bundle`、`_extract_pending_interaction*`、`_append_orchestrator_event` 等）
- [x] 3.4 确保 `cancel_run` 与 recovery 入口行为不变

## 4. Docs and Verification

- [x] 4.1 更新 `docs/core_components.md`
- [x] 4.2 更新 `docs/project_structure.md`
- [x] 4.3 运行测试：
  - `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_job_orchestrator.py tests/unit/test_bundle_manifest.py tests/unit/test_fs_diff_ignore_rules.py tests/unit/test_runtime_observability_port_injection.py`
  - `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_jobs_interaction_routes.py tests/unit/test_temp_skill_runs_router.py`
  - `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_session_invariant_contract.py tests/unit/test_session_state_model_properties.py tests/unit/test_fcmp_mapping_properties.py tests/unit/test_protocol_state_alignment.py tests/unit/test_protocol_schema_registry.py tests/unit/test_runtime_event_protocol.py tests/unit/test_run_observability.py`
- [x] 4.4 运行类型检查：
  - `conda run --no-capture-output -n DataProcessing python -u -m mypy --follow-imports=skip server/services/orchestration/job_orchestrator.py server/services/orchestration/run_job_lifecycle_service.py`
