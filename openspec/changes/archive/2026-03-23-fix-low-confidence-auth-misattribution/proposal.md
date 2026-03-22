## Why

当前运行时会把 `auth_signal.confidence=low` 的 fallback 诊断与普通非零退出混在一起，直接将 run 归因为 `AUTH_REQUIRED`。这会让真实的未知失败被错误翻译成需要鉴权，污染审计、FCMP 终态和前端排障。

## What Changes

- 修复执行链路对 `AUTH_REQUIRED` 的判定，仅允许高置信度 `auth_signal` 升级最终失败原因。
- 保留低置信度 auth fallback 的审计价值，但不再让其驱动 `waiting_auth`、`AUTH_REQUIRED` 终态或终态错误文案。
- 补齐 adapter、lifecycle、终态翻译的回归测试，覆盖低置信度误报场景。

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `engine-execution-failfast`: 非零退出的 `AUTH_REQUIRED` 失败归因仅允许高置信度鉴权信号触发。
- `auth-detection-layer`: 低置信度 `auth_signal` 继续保留为审计诊断，但不得改写终态失败归因。
- `job-orchestrator-modularization`: lifecycle/terminal 归一化必须拒绝将低置信度鉴权信号翻译成 `AUTH_REQUIRED`。

## Impact

- Affected code: `server/runtime/adapter/base_execution_adapter.py`, `server/runtime/auth_detection/signal.py`, `server/services/orchestration/run_job_lifecycle_service.py`
- Affected tests: adapter failfast, auth lifecycle integration, orchestrator terminal mapping
- No public API changes; observable behavior changes only in failure classification and UI/FCMP surface
