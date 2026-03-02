## 1. Baseline and Hotspot Freeze

- [x] 1.1 固定 wave4 起点基线（`server/` broad catch total=134）并记录分类分布
- [x] 1.2 标记 wave4 优先热点：`routers/engines.py`、`routers/ui.py`、`job_orchestrator.py`
- [x] 1.3 对目标文件逐条标注“可收窄”与“需保留 broad catch（含兼容理由）”

## 2. Wave A — Router Engines Boundary

- [x] 2.1 收窄 `server/routers/engines.py` 中可判定 validation/parse/convert broad catch
- [x] 2.2 对需保留的边界 broad catch 统一走 internal-error helper 并补齐结构化日志语义
- [x] 2.3 运行 engines router 相关回归测试确认状态码与错误映射兼容

## 3. Wave B — Router UI Boundary

- [x] 3.1 收窄 `server/routers/ui.py` 中可判定 broad catch 分支
- [x] 3.2 保留必要 boundary catch 并补充策略注释与诊断上下文
- [x] 3.3 运行 UI router 相关回归测试确认兼容

## 4. Wave C — Orchestrator Residual and Guardrail

- [x] 4.1 审查并收窄 `server/services/orchestration/job_orchestrator.py` 中可判定 broad catch
- [x] 4.2 更新 `docs/contracts/exception_handling_allowlist.yaml` 到 wave4 新低基线
- [x] 4.3 验证 `tests/unit/test_no_unapproved_broad_exception.py` 通过且无未授权新增

## 5. Validation Gate

- [x] 5.1 `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_no_unapproved_broad_exception.py`
- [x] 5.2 `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_runtime_observability_port_injection.py tests/unit/test_bundle_manifest.py tests/unit/test_job_orchestrator.py tests/unit/test_ui_shell_manager.py`
- [x] 5.3 `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_session_invariant_contract.py tests/unit/test_session_state_model_properties.py tests/unit/test_fcmp_mapping_properties.py tests/unit/test_protocol_state_alignment.py tests/unit/test_protocol_schema_registry.py tests/unit/test_runtime_event_protocol.py tests/unit/test_run_observability.py`
