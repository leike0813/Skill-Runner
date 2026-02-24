## Why

`interactive-45` 已完成 FCMP 单流收敛，但事件与命令载荷仍存在大量自由字典拼装，缺少统一 JSON Schema 约束，导致：

- 协议 payload 漂移风险高；
- 读写路径校验策略不一致；
- 历史脏数据与新写入缺少明确边界。

需要新增独立变更，为核心协议面建立 Schema SSOT 与运行时校验闭环。

## Dependencies

- 依赖 `interactive-45-fcmp-single-stream-event-architecture` 的 FCMP 单流决策与状态机映射。
- 不变更现有 API 路径与事件名，仅增强契约稳定性。

## What Changes

1. 新增统一协议 Schema：`server/assets/schemas/protocol/runtime_contract.schema.json`。
2. 新增统一校验入口：`protocol_schema_registry`。
3. 新增统一事件/命令构造工厂：`protocol_factories`。
4. 写入路径严格校验（FCMP/RASP/orchestrator/pending/history/resume-command）。
5. 读取路径兼容旧数据（过滤不合规行并记录诊断）。
6. 补充 `PROTOCOL_SCHEMA_VIOLATION` 错误码与相关测试。

## Capabilities

### Modified
- `interactive-log-sse-api`
- `interactive-run-observability`
- `session-runtime-statechart-ssot`

### Added
- `runtime-event-command-schema`

## Impact

- 代码：`server/services/runtime_event_protocol.py`, `server/services/run_store.py`, `server/services/job_orchestrator.py`, `server/services/run_interaction_service.py`, `server/services/run_observability.py`
- 模型：`server/models.py`
- 文档：`docs/runtime_stream_protocol.md`, `docs/runtime_event_schema_contract.md`
- 测试：新增 schema registry 测试与既有单测更新

## Follow-up

- `interactive-47-session-invariants-property-model-tests`：将 session+FCMP 关键不变量合同化，并由属性/模型测试守护文档与实现一致性。
