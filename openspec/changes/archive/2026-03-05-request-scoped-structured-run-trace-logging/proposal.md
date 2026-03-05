# Proposal: request-scoped-structured-run-trace-logging

## Why

当前上传与运行主链路在关键阶段缺少统一的结构化日志，导致 request 丢失 run 绑定、run 卡住、鉴权恢复异常时难以快速定位问题阶段与失败原因。需要把 request_id 贯穿到关键事件日志中，并统一事件码语义，降低排障成本。

## What Changes

- 为 upload、run lifecycle、interaction/auth、recovery 四条关键链路增加统一结构化日志能力（`event + key/value`）。
- 新增统一日志工具 `log_event(...)`，支持上下文补全（request_id/run_id/attempt）与敏感字段脱敏。
- 扩展 run logging context，支持 `phase` 字段注入并供结构化日志自动读取。
- 在 upload 关键段补齐里程碑日志：请求读取、校验、manifest/cache、cache hit/miss、run 创建绑定、dispatch。
- 在 run lifecycle 补齐运行里程碑日志：queued/slot acquire/start/waiting/terminal/slot release。
- 在 interaction/auth/recovery 补齐关键日志：reply accepted/rejected、auth challenge/completed/failed、redrive/reconcile。

## Capabilities

### New Capabilities

- `request-scoped-structured-trace-logging`: 定义 request 级结构化追踪日志能力与事件码约束。

### Modified Capabilities

- `job-orchestrator-modularization`: 运行编排链路需输出稳定结构化里程碑日志。
- `interactive-job-api`: upload 与会话交互相关后端链路需保证 request 级可追踪性日志。

## Impact

- 受影响代码：
  - `server/runtime/logging/*`
  - `server/routers/jobs.py`
  - `server/services/orchestration/run_job_lifecycle_service.py`
  - `server/services/orchestration/job_orchestrator.py`
  - `server/services/orchestration/run_interaction_service.py`
  - `server/services/orchestration/run_auth_orchestration_service.py`
  - `server/services/orchestration/run_recovery_service.py`
  - 新增测试 `tests/unit/test_structured_trace_logging.py`
- 对外 API/协议无变更。
