## ADDED Requirements

### Requirement: run_job attempt lifecycle MUST manage run-scoped service log mirroring

`run_job` 在 attempt 执行期间 MUST 绑定 run logging 上下文并启用双镜像会话（run-scope 全集 + attempt-scope 分片），确保并发 run 日志不互串且资源正确释放。

#### Scenario: attempt execution opens and closes mirror session
- **WHEN** `run_job` 解析出 `run_id` 与 `attempt_number` 后进入 attempt 执行
- **THEN** 系统 MUST 开启 run-scope 与 attempt-scope 服务日志镜像会话
- **AND** 在 attempt 任意退出路径（success/failure/cancel/exception）MUST 关闭会话并卸载 handler

#### Scenario: mirror writes only records bound to the target run
- **GIVEN** 多个 run 并发执行
- **WHEN** 服务进程产生日志
- **THEN** 每个 run 的 `service.run.log` MUST 只包含自身 `run_id` 的记录
- **AND** 每个 attempt 的 `service.<attempt>.log` MUST 只包含自身 `run_id + attempt` 的记录
- **AND** 缺少 `run_id` 的记录 MUST 被丢弃

### Requirement: run lifecycle orchestration MUST mirror service logs outside attempt windows

create-run、upload-run、reply/auth 提交与 auth 状态轮询等 attempt 外编排路径 MUST 进入 run-scope 镜像，确保 run 全生命周期日志完整。

#### Scenario: create-run orchestration contributes to run-scope service log
- **WHEN** run 在 router/orchestration 路径被创建并完成 bootstrap/dispatch 准备
- **THEN** 这些服务日志 MUST 写入 `.audit/service.run.log`
- **AND** 这些记录 MAY 不出现在任何 `service.<attempt>.log`
