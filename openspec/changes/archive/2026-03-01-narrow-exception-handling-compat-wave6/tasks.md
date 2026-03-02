## 1. Baseline Freeze and Target Classification

- [x] 1.1 固定 wave6 起点基线（`server/` broad catch total=84）并记录目标文件分类分布
- [x] 1.2 逐条标注 `run_observability`、`skill_patcher`、`trust_folder_strategy` 中可收窄与需保留分支（含兼容理由）
- [x] 1.3 确认保留 broad catch 的结构化诊断字段落点（`component/action/error_type/fallback`）

## 2. Wave A — Runtime Observability Narrowing

- [x] 2.1 在 `server/runtime/observability/run_observability.py` 收窄 deterministic 文件读取/解析/转换 broad catch
- [x] 2.2 对必须保留的兼容 fallback broad catch 补充注释与结构化诊断
- [x] 2.3 运行 `tests/unit/test_run_observability.py tests/unit/test_runtime_observability_port_injection.py` 验证兼容

## 3. Wave B — Skill Patch Pipeline Narrowing

- [x] 3.1 在 `server/services/skill/skill_patcher.py` 收窄 deterministic broad catch
- [x] 3.2 保持 patch 结果/错误返回语义不变并补齐必要诊断信息
- [x] 3.3 运行 `tests/unit/test_skill_patcher.py tests/unit/test_skill_patcher_pipeline.py` 验证兼容

## 4. Wave C — Trust Folder Strategy Narrowing

- [x] 4.1 在 `server/engines/gemini/adapter/trust_folder_strategy.py` 收窄 path/fs 相关 broad catch
- [x] 4.2 在 `server/engines/codex/adapter/trust_folder_strategy.py` 收窄 path/fs 相关 broad catch
- [x] 4.3 运行 `tests/unit/test_gemini_adapter.py tests/unit/test_codex_adapter.py` 验证行为兼容

## 5. Allowlist Ratchet and Validation Gate

- [x] 5.1 更新 `docs/contracts/exception_handling_allowlist.yaml` 到 wave6 新基线（只降不升）
- [x] 5.2 运行 `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_no_unapproved_broad_exception.py`
- [x] 5.3 运行 `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_run_observability.py tests/unit/test_runtime_observability_port_injection.py tests/unit/test_skill_patcher.py tests/unit/test_skill_patcher_pipeline.py tests/unit/test_gemini_adapter.py tests/unit/test_codex_adapter.py`
- [x] 5.4 运行 `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_session_invariant_contract.py tests/unit/test_session_state_model_properties.py tests/unit/test_fcmp_mapping_properties.py tests/unit/test_protocol_state_alignment.py tests/unit/test_protocol_schema_registry.py tests/unit/test_runtime_event_protocol.py tests/unit/test_run_observability.py tests/unit/test_fcmp_cursor_global_seq.py`
