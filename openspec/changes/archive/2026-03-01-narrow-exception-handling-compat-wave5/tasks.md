## 1. Baseline Freeze and Target Confirmation

- [x] 1.1 固定 wave5 起点基线（`server/` broad catch total=97）并记录目标文件的分类分布
- [x] 1.2 逐条标注 `schema_validator`、`agent_cli_manager`、`run_audit_service` 中“可收窄”与“保留 broad catch（含兼容理由）”分支
- [x] 1.3 预先确认保留 broad catch 的结构化日志字段（`component/action/error_type/fallback`）落点

## 2. Wave A — Platform Schema Validator Narrowing

- [x] 2.1 在 `server/services/platform/schema_validator.py` 将 schema 读取/JSON 解析 broad catch 收窄为 typed exceptions
- [x] 2.2 保持 `jsonschema.ValidationError` 映射与返回错误文案语义不变，避免行为回归
- [x] 2.3 运行 `tests/unit/test_schema_validator.py` 验证兼容性

## 3. Wave B — Orchestration Bootstrap/Settings Narrowing

- [x] 3.1 在 `server/services/orchestration/agent_cli_manager.py` 收窄 bootstrap 配置读取和 settings 解析 broad catch
- [x] 3.2 在路径解析与 best-effort 分支中保留必要兼容 fallback，并补齐结构化诊断信息
- [x] 3.3 运行 `tests/unit/test_agent_cli_manager.py` 与相关路由/编排回归测试验证兼容

## 4. Wave C — Run Audit Sequence Compatibility Narrowing

- [x] 4.1 在 `server/services/orchestration/run_audit_service.py` 收窄 JSONL 解析与文件读取 broad catch
- [x] 4.2 对 adapter 边界无法细化场景保留受控 broad catch，并明确 non-blocking fallback 语义
- [x] 4.3 运行 `tests/unit/test_job_orchestrator.py`、`tests/unit/test_orchestrator_history_seq_backfill.py` 验证 history/seq 兼容

## 5. Allowlist Ratchet and Guardrail Validation

- [x] 5.1 更新 `docs/contracts/exception_handling_allowlist.yaml` 到 wave5 新基线（只降不升）
- [x] 5.2 运行 `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_no_unapproved_broad_exception.py`
- [x] 5.3 运行 `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_schema_validator.py tests/unit/test_agent_cli_manager.py tests/unit/test_job_orchestrator.py tests/unit/test_orchestrator_history_seq_backfill.py`
- [x] 5.4 若触达 runtime 协议/状态行为，运行 AGENTS.md 必跑清单并追加 `tests/unit/test_fcmp_cursor_global_seq.py`
