## Why

`opencode` 的 interactive auth 目前把 provider 归因错误地绑定到了 `auth_detection.provider_id`。当 runtime 已经高置信度识别出 `auth_required`，但 detection 没有抽取出 provider 时，orchestration 无法创建 pending auth，最终 run 直接以 `AUTH_REQUIRED` 失败，而不是进入 `waiting_auth`。现场 run `85f83d2d-e9d2-4d6d-ad70-18bc760b2c45` 已经证明 request 侧的 `engine_options.model` 提供了更稳定的 provider 来源，例如 `deepseek/deepseek-reasoner`。

## What Changes

- 对 `opencode` 增加 engine-specific provider fallback：canonical provider 由 orchestration 从 `engine_options.model` 前缀解析。
- `auth_detection.provider_id` 在 `opencode` 场景中降级为证据字段，不再阻断 `waiting_auth` 创建。
- 让 pending auth、auth session、FCMP challenge payload 和审计中的 provider 一致使用 canonical provider。
- 当 request model 缺失或格式非法时，保留 `AUTH_REQUIRED` 失败，但必须留下明确的 unresolved-provider 诊断。

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `interactive-job-api`: `opencode` 高置信度 `auth_required` 在 request model 可解析 provider 时必须进入 `waiting_auth`。
- `job-orchestrator-modularization`: `opencode` auth orchestration 的 provider 归因改为 request-side model，而不是 detection-side provider hint。

## Impact

- Affected code:
  - `server/services/orchestration/run_job_lifecycle_service.py`
  - `server/services/orchestration/run_auth_orchestration_service.py`
  - `server/runtime/protocol/event_protocol.py`
- Affected tests:
  - `tests/unit/test_auth_detection_lifecycle_integration.py`
  - `tests/unit/test_run_auth_orchestration_service.py`
  - `tests/unit/test_runtime_event_protocol.py`
- Public API impact:
  - 无新增 API；只修正 `opencode` high-confidence auth 的 waiting_auth 进入行为。
