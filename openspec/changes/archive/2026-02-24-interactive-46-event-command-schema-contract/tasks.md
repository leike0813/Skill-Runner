## 1. Schema SSOT

- [ ] 1.1 新增 `server/assets/schemas/protocol/runtime_contract.schema.json`
- [ ] 1.2 定义 `fcmp_event_envelope` / `rasp_event_envelope` / `orchestrator_event`
- [ ] 1.3 定义 `pending_interaction` / `interaction_history_entry` / `interactive_resume_command`

## 2. Runtime Validation

- [ ] 2.1 新增 `server/services/protocol_schema_registry.py`
- [ ] 2.2 新增 `server/services/protocol_factories.py`
- [ ] 2.3 `runtime_event_protocol` 写入前强校验
- [ ] 2.4 `run_store` pending/history 写入强校验，读取兼容过滤
- [ ] 2.5 `job_orchestrator` 与 `run_interaction_service` 接入 resume command 校验与降级
- [ ] 2.6 `run_observability` 接入 FCMP/RASP/orchestrator 校验与 history 过滤

## 3. Spec & Docs

- [ ] 3.1 新增 capability `runtime-event-command-schema`
- [ ] 3.2 修改 `interactive-log-sse-api`，补 schema 强约束
- [ ] 3.3 修改 `interactive-run-observability`，补历史兼容读取规则
- [ ] 3.4 修改 `session-runtime-statechart-ssot`，补 state payload 字段约束
- [ ] 3.5 更新 `docs/runtime_stream_protocol.md`
- [ ] 3.6 新增 `docs/runtime_event_schema_contract.md`

## 4. Tests

- [ ] 4.1 新增 `tests/unit/test_protocol_schema_registry.py`
- [ ] 4.2 修改 `tests/unit/test_runtime_event_protocol.py`
- [ ] 4.3 修改 `tests/unit/test_run_store.py`
- [ ] 4.4 修改 `tests/unit/test_run_observability.py`
- [ ] 4.5 修改 `tests/unit/test_job_orchestrator.py`
