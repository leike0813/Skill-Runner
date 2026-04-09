## Why

当前主协议、主 specs 与 Claude 已实现的 provider-config waiting_auth 语义发生了漂移：代码与历史变更仍使用 `custom_provider`，但主 schema 和主文档已经不再承认这个合法值，导致第三方 Claude provider 在进入 `waiting_auth` 前就因 `PROTOCOL_SCHEMA_VIOLATION` 失败。现在需要把这条能力重新纳入 shared SSOT，而不是继续依赖 archived change 与局部实现。

## What Changes

- 恢复 `custom_provider` 作为正式合法的会话中鉴权方式，并加回 runtime schema 的 `auth_method` / `challenge_kind` / `input_kind` / `available_methods` / `submission_kind` 合同。
- 将 Claude 历史上已经存在的 `transport=provider_config + auth_method=custom_provider` 语义回并到主 shared specs。
- 保持现有 Claude custom provider waiting_auth 编排逻辑不变，但让其重新与主协议、主文档和测试对齐。
- 更新 API/协议文档，明确 `custom_provider` 是 provider-config 会话的正式语义，而不是 `api_key` 的别名。

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `interactive-job-api`: `interaction/reply` 的 `mode=auth` 需要正式支持 `submission.kind=custom_provider`
- `in-conversation-auth-method-selection`: provider-config waiting_auth 需要以 `custom_provider` 作为正式的 method/challenge/input 语义
- `engine-auth-observability`: auth session snapshot 与 waiting_auth observability 需要承认 `provider_config/custom_provider`
- `runtime-event-command-schema`: runtime schema 需要恢复 `custom_provider` 的合法枚举值
- `management-api-surface`: 统一 auth_method 语义需要包含 `custom_provider`
- `ui-engine-management`: 管理 UI 的 auth method 菜单语义需要承认 `custom_provider`

## Impact

- Affected code:
  - `server/contracts/schemas/runtime_contract.schema.json`
  - `server/services/orchestration/run_auth_orchestration_service.py`
  - `server/runtime/protocol/schema_registry.py`
  - Claude custom provider waiting_auth 相关路由/读模型/事件路径
- Affected tests:
  - `tests/unit/test_protocol_schema_registry.py`
  - `tests/unit/test_runtime_event_protocol.py`
  - `tests/unit/test_run_auth_orchestration_service.py`
- Affected docs/specs:
  - `docs/api_reference.md`
  - shared OpenSpec main specs listed above
