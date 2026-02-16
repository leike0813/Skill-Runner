## Why

交互执行模式引入后，客户端需要在运行过程中实时看到 stdout/stderr 与状态变化，仅靠轮询全量日志接口会带来延迟与带宽浪费。  
现有 UI 已有日志 tail 机制，但主要面向 HTML partial，不适合作为通用客户端 API 契约。

## What Changes

1. 新增面向 API 客户端的 SSE 日志事件流接口（Jobs 与 Temp Skill Runs 两条链路）。
2. 事件流按增量输出 stdout/stderr，附带可恢复游标（offset）与状态事件。
3. 在 `waiting_user`、终态等关键状态发送状态事件，并定义连接关闭语义。
4. 保留现有 `/logs` 全量接口与 UI tail 接口，SSE 作为新增能力，不替换旧接口。
5. 明确客户端重连与断点续传约定（query offsets / Last-Event-ID）。

## Capabilities

### New Capabilities
- `interactive-log-sse-api`: 为 interactive/auto 运行提供统一的 SSE 日志与状态事件流 API，支持增量消费与重连续传。

### Modified Capabilities
- `interactive-run-observability`: 可观测能力从“轮询日志语义”扩展为“轮询 + SSE 流语义”，并补充客户端消费约定。

## Impact

- `server/routers/jobs.py`
- `server/routers/temp_skill_runs.py`
- `server/models.py`（如需新增 SSE 事件模型）
- `server/services/run_observability.py`（复用/抽象 tail 读取与状态判断）
- `docs/api_reference.md`
- `tests/unit/test_v1_routes.py`
- `tests/unit/test_run_observability.py`
- `tests/integration/run_integration_tests.py`
- `tests/e2e/run_container_e2e_tests.py`
