## Why

当前 run 目录虽然有 stdout/stderr、FCMP/RASP 和 orchestrator 审计文件，但缺少服务进程自身的日志镜像。排查复杂问题时只能回看全局 `data/logs/skill_runner.log`，并发 run 场景下噪声很高，定位单个 run 的服务侧行为成本大。

本 change 通过 run/attempt 双层日志镜像补齐审计链路：在 run 生命周期内将服务进程 Python logging 严格按 `run_id` 过滤后写入 `.audit/service.run.log`（全集），并按 attempt 维度写入 `.audit/service.<attempt>.log`（子集）。

## What Changes

- 新增 run logging context 基础设施（`contextvars + LogRecordFactory`），为日志自动注入 `run_id/request_id/attempt_number`。
- 新增 `RunServiceLogMirrorSession`，支持 run-scope 与 attempt-scope 两种会话，均按 `run_id` 严格过滤。
- 在 `run_job` 生命周期中接入“run-scope 全集 + attempt-scope 分片”双镜像，并在 create-run / reply / auth polling 等 attempt 外路径接入 run-scope 镜像。
- 扩展 run audit contract，新增 `run_service_log_path` 与 `service_log_path`，并预创建 `service.run.log` 与 `service.<attempt>.log`。
- 在 attempt 关键路径补充结构化 `logger.info`，确保镜像文件在成功路径下也具备可读审计信号。
- 更新 run artifacts 文档与 OpenSpec delta specs。

## Capabilities

### New Capabilities

- `run-audit-contract`: 新增 run 级全集镜像 `service.run.log` 与 attempt 级分片 `service.<attempt>.log`。

### Modified Capabilities

- `job-orchestrator-modularization`: run 生命周期关键阶段必须绑定 run logging 上下文并管理镜像会话生命周期，确保全集与分片同时可用。

## Impact

- 影响代码：`logging_config`、`jobs/temp_skill_runs`、`run_interaction_service`、`run_job_lifecycle_service`、`run_audit_contract_service`、新增 `run_context` 与 `run_service_log_mirror` 模块。
- 对外 API：无新增路由/字段变更。
- 运行时行为：不改变 FCMP/RASP，只增加 run 审计旁路日志镜像。
