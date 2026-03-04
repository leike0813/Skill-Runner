## Why

当前 auth orchestrator event 的实现、JSON Schema 和文档已经发生漂移。最新事故中，callback URL 提交路径写出了 `auth.input.accepted.accepted_at`，但协议 schema 不允许该字段，直接导致提交鉴权输入时抛出 `Internal Server Error` 并中断 `waiting_auth` 闭环。现在需要把整组 auth orchestrator event 合同一次对齐，避免继续靠单点补丁追 schema 漂移。

## What Changes

- 对齐 auth orchestrator event 的协议合同，覆盖 `auth.session.created`、`auth.method.selected`、`auth.session.busy`、`auth.input.accepted`、`auth.session.completed`、`auth.session.failed`、`auth.session.timed_out` 的字段边界与命名。
- 更新 runtime protocol schema，使其允许当前 canonical auth submit/complete/fail 路径真实产出的字段，并继续对非法额外字段保持严格校验。
- 收敛 auth orchestrator event 的实现，避免同类事件在不同调用点各自拼装略有差异的 payload。
- 更新 runtime schema 文档与交互/编排主 spec，明确 auth orchestrator event 的 contract、写入语义以及 callback URL 提交闭环。
- 增加 schema、orchestration 和 integration 回归，锁住“提交 callback URL 不因协议漂移而 500”以及“auth event payload 与 schema 一致”。

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `runtime-event-command-schema`: auth orchestrator event 的 JSON Schema requirement 将收紧为“覆盖 canonical 实现且保持严格校验”。
- `interactive-job-api`: auth input submit 的 requirement 将明确要求 callback/code 提交路径可成功记录 `auth.input.accepted` 并继续后续 auth 流程。
- `job-orchestrator-modularization`: orchestration service 的 requirement 将明确要求 auth orchestrator event 通过统一 contract 写入，避免 payload 漂移。

## Impact

- Affected code:
  - `server/assets/schemas/protocol/runtime_contract.schema.json`
  - `server/services/orchestration/run_auth_orchestration_service.py`
  - `server/services/orchestration/run_audit_service.py`
- Affected docs/specs:
  - `docs/runtime_event_schema_contract.md`
  - `openspec/specs/runtime-event-command-schema/spec.md`
  - `openspec/specs/interactive-job-api/spec.md`
  - `openspec/specs/job-orchestrator-modularization/spec.md`
- Affected tests:
  - `tests/unit/test_protocol_schema_registry.py`
  - `tests/unit/test_run_auth_orchestration_service.py`
  - potentially auth submit integration coverage under `tests/api_integration/`
- Public API impact:
  - 无新增路由，但 auth submit 路径的错误模式会从 `500` 收敛为 schema-aligned 正常闭环。
