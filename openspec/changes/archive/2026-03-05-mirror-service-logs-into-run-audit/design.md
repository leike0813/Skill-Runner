## Context

需要在不改变现有协议流（FCMP/RASP）和全局日志行为的前提下，为每个 run 生成全生命周期服务日志全集，同时保留 attempt 维度的分片日志。关键约束是并发 run 不能互串、无 run 上下文日志必须丢弃。

## Goals / Non-Goals

**Goals**
- run 级服务日志全集镜像：`.audit/service.run.log`
- attempt 级服务日志分片：`.audit/service.<attempt>.log`
- 严格 run 过滤：只允许 `record.run_id == 当前 run_id`
- 生命周期闭环：run 创建/交互/auth 轮询/attempt 执行均可进入 run-scope 镜像；attempt 期间额外写 attempt 分片
- 有界落盘：`8MB + 3` 轮转

**Non-Goals**
- 不采集 engine 子进程 stdout/stderr
- 不替代全局 `skill_runner.log`
- 不引入新的 FCMP/RASP 事件类型

## Decisions

### 1) 上下文注入采用 `contextvars + LogRecordFactory`

- 在 `setup_logging()` 期间安装一次 record factory。
- 每条日志若未显式携带 `run_id/request_id/attempt_number`，自动从 contextvars 注入。
- 若调用点显式传了 `extra`，不覆盖原值。

### 2) 镜像器采用 root logger 动态 handler（双会话）

- run-scope：写 `.audit/service.run.log`，仅按 `run_id` 过滤，作为该 run 全集。
- attempt-scope：写 `.audit/service.<attempt>.log`，按 `run_id + attempt_number` 过滤，作为 attempt 子集。
- 两类 handler 都在各自上下文退出时移除并关闭。

### 3) 生命周期接入点采用 run-scope + attempt-scope 组合

- create-run、upload-run、reply/auth 提交、auth status 轮询等 attempt 外编排路径：绑定 run context + run-scope 镜像。
- `run_job` 中 `attempt_number` 决定后：同时开启 run-scope 与 attempt-scope。
- attempt 所有路径（成功、失败、取消、异常、早退）由外层 `finally` 统一关闭会话，避免句柄泄漏。

### 4) 审计合同新增 run/attempt 两条日志路径

- contract 增加 `run_service_log_path`（`service.run.log`）与 `service_log_path`（`service.<attempt>.log`）。
- `initialize_run_audit()` 预创建 `service.run.log`。
- `initialize_attempt_audit()` 预创建 `service.<attempt>.log`。

### 5) attempt 成功路径补结构化 info

- 在 `run_job` 关键节点写结构化 `logger.info`（attempt begin、adapter run begin/end、waiting_user/waiting_auth/terminal）。
- 保证即便无 warning/error，也能在镜像日志中看到主流程轨迹。

## Risks / Trade-offs

- [异步任务跨 attempt 继续打日志] run-scope 保留全集，attempt-scope 用 attempt 过滤避免串写。
- [日志上下文缺失导致镜像为空] 这是有意策略：无 `run_id` 记录必须丢弃，优先隔离正确性。
- [额外 handler 性能开销] run-scope 会覆盖更多路径，仍是单 run 两个 file handler，开销可控。
