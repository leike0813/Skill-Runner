## 1. Baseline and Hotspot Freeze

- [x] 1.1 固定 wave3 起点基线（`server/` broad catch total=162）并记录分类分布
- [x] 1.2 标记 wave3 优先清理文件：`engine_auth_flow_manager` + `engine/*/auth/runtime_handler`
- [x] 1.3 对目标文件逐条标注“可收窄”与“需保留 broad catch（含理由）”

## 2. Wave A — Orchestration Auth Manager

- [x] 2.1 收窄 `server/services/orchestration/engine_auth_flow_manager.py` 中可判定异常域
- [x] 2.2 清理 `pass/silent return` 吞没分支，改为 typed fallback 或明确保留注释
- [x] 2.3 对保留 broad catch 的分支补充结构化诊断语义（component/action/error_type/fallback）

## 3. Wave B — Engine Auth Runtime Handlers

- [x] 3.1 收窄 `server/engines/opencode/auth/runtime_handler.py` 高风险 broad catch
- [x] 3.2 收窄 `server/engines/codex/auth/runtime_handler.py` 高风险 broad catch
- [x] 3.3 收窄 `server/engines/gemini/auth/runtime_handler.py` 与 `server/engines/iflow/auth/runtime_handler.py` 可判定 broad catch
- [x] 3.4 审查并保留必要 boundary/best-effort 分支，补齐兼容语义注释

## 4. Wave C — Residual and Guardrail

- [x] 4.1 审查 `server/services/ui/ui_shell_manager.py` 中可安全收窄分支
- [x] 4.2 更新 `docs/contracts/exception_handling_allowlist.yaml` 到 wave3 新低基线
- [x] 4.3 验证 `tests/unit/test_no_unapproved_broad_exception.py` 通过且无未授权新增

## 5. Validation Gate

- [x] 5.1 `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_no_unapproved_broad_exception.py`
- [x] 5.2 `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_engine_auth_flow_manager.py tests/unit/test_auth_session_starter.py tests/unit/test_runtime_auth_no_engine_coupling.py tests/unit/test_ui_shell_manager.py`
- [x] 5.3 `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_session_invariant_contract.py tests/unit/test_session_state_model_properties.py tests/unit/test_fcmp_mapping_properties.py tests/unit/test_protocol_state_alignment.py tests/unit/test_protocol_schema_registry.py tests/unit/test_runtime_event_protocol.py tests/unit/test_run_observability.py`
