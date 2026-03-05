# Design: request-scoped-structured-run-trace-logging

## 1. 总体设计

本 change 采用轻量结构化文本日志方案：

- 日志统一格式：`event=<event_code> key1=... key2=...`
- 由 `log_event(...)` 统一序列化、字段归一与敏感字段脱敏。
- 通过 `run_context` 自动注入 `request_id/run_id/attempt/phase` 上下文，减少业务层重复拼接。

不切换 JSON logging，不改变 handler 拓扑，仅增强可追溯性。

## 2. 组件设计

### 2.1 `structured_trace.py`

新增 `log_event(...)`：

- 必填语义字段：`event`、`phase`、`outcome`
- 条件字段：`request_id/run_id/attempt/error_code/error_type`
- 自动回填：从 context 读取 `request_id/run_id/attempt`
- 脱敏：`api_key/token/authorization_code/callback_url/credential` 等敏感键以 `<redacted:...>` 输出

### 2.2 `run_context.py`

在原有 `run_id/request_id/attempt` 基础上新增：

- `phase` contextvar
- `bind_request_logging_context(...)`（无 run_id 场景）
- `get_logging_context()`（供 structured_trace 读取）

## 3. 链路埋点策略

### 3.1 Upload（最高优先）

落点：`server/routers/jobs.py` `POST /jobs/{request_id}/upload`

事件覆盖：

- `upload.request.received`
- `upload.request.loaded`
- `upload.payload.validated`
- `upload.temp_staged`
- `upload.manifest.built`
- `upload.request_state.persisted`
- `upload.cache_key.computed`
- `upload.cache.hit` / `upload.cache.miss`
- `upload.run.created`
- `upload.request_run.bound`
- `upload.dispatch.started`
- `upload.dispatch.completed`
- `upload.failed`

### 3.2 Run lifecycle

落点：`run_job_lifecycle_service.py` + `job_orchestrator.py`

事件覆盖：

- `run.lifecycle.queued`
- `run.lifecycle.slot_acquired`
- `run.lifecycle.started`
- `run.lifecycle.resumed`
- `run.lifecycle.waiting_user`
- `run.lifecycle.waiting_auth`
- `run.lifecycle.succeeded`
- `run.lifecycle.failed`
- `run.lifecycle.slot_released`

### 3.3 Interaction/Auth

落点：`run_interaction_service.py`、`run_auth_orchestration_service.py`

事件覆盖：

- `interaction.reply.accepted`
- `interaction.reply.rejected`
- `auth.session.created`
- `auth.challenge.published`
- `auth.input.accepted`
- `auth.completed`
- `auth.failed`

### 3.4 Recovery

落点：`run_recovery_service.py`

事件覆盖：

- `recovery.redrive.requested`
- `recovery.redrive.skipped`
- `recovery.reconciled_terminal`

## 4. 错误与脱敏约束

- HTTP 级失败与异常都必须产出 `upload.failed`（带 `error_code/error_type`）。
- 禁止输出 token/api key/callback url 原文。
- 无 request_id 的日志不视为主链路日志，关键链路必须携带 request_id。

## 5. 测试策略

- 新增 `test_structured_trace_logging.py` 覆盖格式、上下文注入、脱敏行为。
- 保持现有 orchestrator/auth/recovery 相关测试通过，验证埋点未改变业务行为。
- 后续可增补 upload 流程集成日志断言（本 change 先覆盖核心工具与主链路接入）。
